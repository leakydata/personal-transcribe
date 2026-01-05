"""
Standalone transcription process - runs Whisper in a completely separate process.

This script is designed to be run as a subprocess:
    python -m src.transcription.transcribe_process <audio_path> <output_path> [options]

It writes progress to stdout as JSON lines, and the final transcript to the output file.
When this process exits, ALL its resources (including GPU memory) are freed by the OS.

This solves the crash-on-load issue because Whisper is NEVER loaded in the main GUI process.
"""

import sys
import os
import json
import time
import gc
import argparse
from pathlib import Path
from datetime import datetime


def emit_progress(stage: str, progress: float = 0, message: str = "", **kwargs):
    """Emit progress as a JSON line to stdout."""
    data = {
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    print(json.dumps(data), flush=True)


def emit_segment(segment_num: int, start: float, end: float, text: str):
    """Emit a segment notification."""
    data = {
        "type": "segment",
        "segment_num": segment_num,
        "start": start,
        "end": end,
        "text_preview": text[:50] + "..." if len(text) > 50 else text
    }
    print(json.dumps(data), flush=True)


def emit_error(message: str):
    """Emit an error."""
    data = {
        "type": "error",
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    print(json.dumps(data), flush=True)


def emit_complete(output_path: str, segment_count: int, word_count: int, duration: float):
    """Emit completion notification."""
    data = {
        "type": "complete",
        "output_path": output_path,
        "segment_count": segment_count,
        "word_count": word_count,
        "duration": duration,
        "timestamp": datetime.now().isoformat()
    }
    print(json.dumps(data), flush=True)


def init_stream_file(output_path: str, audio_path: str, model_size: str) -> None:
    """Initialize the streaming JSON file."""
    initial_data = {
        "version": "1.0",
        "status": "in_progress",
        "audio_file": audio_path,
        "model": model_size,
        "started_at": datetime.now().isoformat(),
        "audio_duration": 0,
        "segments": []
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, indent=2)


def append_segment_to_file(output_path: str, segment_data: dict, segment_buffer: list) -> None:
    """Buffer segment and periodically write to file.
    
    Instead of reading/writing the entire JSON for each segment (O(n^2) I/O),
    we buffer segments and only write every 50 segments.
    This dramatically reduces memory pressure for long transcriptions.
    """
    segment_buffer.append(segment_data)
    
    # Only write to disk every 50 segments to reduce I/O pressure
    if len(segment_buffer) >= 50:
        flush_segments_to_file(output_path, segment_buffer)
        segment_buffer.clear()


def flush_segments_to_file(output_path: str, segment_buffer: list) -> None:
    """Flush buffered segments to the file."""
    if not segment_buffer:
        return
    
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data["segments"].extend(segment_buffer)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        emit_error(f"Failed to flush segments: {e}")


def finalize_stream_file(output_path: str, audio_duration: float, status: str = "complete") -> None:
    """Finalize the streaming file."""
    try:
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data["status"] = status
        data["audio_duration"] = audio_duration
        data["completed_at"] = datetime.now().isoformat()
        data["segment_count"] = len(data["segments"])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        emit_error(f"Failed to finalize file: {e}")


def generate_segment_id() -> str:
    """Generate a unique segment ID."""
    import uuid
    return str(uuid.uuid4())[:8]


def run_transcription(
    audio_path: str,
    output_path: str,
    model_size: str = "large-v3",
    device: str = "auto",
    vocabulary: list = None,
    segment_mode: str = "natural"
) -> bool:
    """Run the transcription process."""
    
    try:
        # Suppress warnings
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        
        emit_progress("init", 0, "Starting transcription process...")
        
        # Stage 1: Detect device
        emit_progress("device", 5, "Detecting GPU/CUDA support...")
        
        try:
            import ctranslate2
            cuda_types = ctranslate2.get_supported_compute_types("cuda")
            if cuda_types:
                compute_type = "float16" if "float16" in cuda_types else "int8"
                device = "cuda"
                emit_progress("device", 5, f"CUDA available - using GPU with {compute_type}", 
                            device=device, compute_type=compute_type)
            else:
                device = "cpu"
                compute_type = "int8"
                emit_progress("device", 5, "CUDA not available - using CPU",
                            device=device, compute_type=compute_type)
        except Exception as e:
            device = "cpu"
            compute_type = "int8"
            emit_progress("device", 5, f"CUDA check failed: {e} - using CPU",
                        device=device, compute_type=compute_type)
        
        # Stage 2: Load model
        emit_progress("model", 10, f"Loading {model_size} model...")
        
        from faster_whisper import WhisperModel
        
        start_load = time.time()
        try:
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
            load_time = time.time() - start_load
            emit_progress("model", 15, f"Model loaded in {load_time:.1f}s")
        except Exception as e:
            if "cuda" in str(e).lower():
                emit_progress("model", 10, f"GPU failed: {e} - falling back to CPU")
                device = "cpu"
                compute_type = "int8"
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
                emit_progress("model", 15, "Model loaded on CPU (fallback)")
            else:
                raise
        
        # Stage 3: Initialize streaming file
        emit_progress("prepare", 18, "Preparing transcription...")
        init_stream_file(output_path, audio_path, model_size)
        
        # Stage 4: Prepare transcription parameters
        initial_prompt = None
        if vocabulary:
            initial_prompt = " ".join(vocabulary)
            emit_progress("prepare", 19, f"Using {len(vocabulary)} vocabulary words")
        
        # Configure VAD parameters
        if segment_mode == "sentence":
            vad_params = dict(
                min_silence_duration_ms=2000,
                speech_pad_ms=400,
                min_speech_duration_ms=500,
                max_speech_duration_s=60,
            )
        else:
            vad_params = dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200
            )
        
        # Stage 5: Run transcription
        emit_progress("transcribe", 20, "Starting transcription...")
        
        start_transcribe = time.time()
        
        segments_generator, info = model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
            initial_prompt=initial_prompt,
            language=None,
            vad_filter=True,
            vad_parameters=vad_params
        )
        
        audio_duration = info.duration if hasattr(info, 'duration') else 0
        emit_progress("transcribe", 22, 
                     f"Language: {info.language} ({info.language_probability:.1%}), Duration: {audio_duration/60:.1f}min")
        
        # Process segments with buffered writes to reduce memory pressure
        segment_count = 0
        word_count = 0
        last_end_time = 0.0
        segment_buffer = []  # Buffer segments to reduce I/O
        
        for segment in segments_generator:
            segment_count += 1
            
            # Extract words - minimize object creation
            words = []
            if segment.words:
                for word_info in segment.words:
                    words.append({
                        "text": word_info.word.strip(),
                        "start": word_info.start,
                        "end": word_info.end,
                        "confidence": word_info.probability
                    })
                    word_count += 1
            
            # Create segment data
            segment_data = {
                "id": generate_segment_id(),
                "start_time": segment.start,
                "end_time": segment.end,
                "text": segment.text.strip(),
                "words": words
            }
            
            # Buffer segment (writes to file every 50 segments)
            append_segment_to_file(output_path, segment_data, segment_buffer)
            last_end_time = segment.end
            
            # Clear local references to help GC
            words = None
            segment_data = None
            
            # Calculate and emit progress
            if audio_duration > 0:
                progress = 20 + (75 * (segment.end / audio_duration))
                progress = min(progress, 95)
            else:
                progress = 50
            
            # Emit segment notification every 10 segments
            if segment_count == 1 or segment_count % 10 == 0:
                emit_segment(segment_count, segment.start, segment.end, segment.text.strip())
                emit_progress("transcribe", progress, 
                            f"Segment {segment_count}: {segment.start:.1f}s - {segment.end:.1f}s")
            
            # More aggressive GC for long transcriptions
            if segment_count % 100 == 0:
                gc.collect()
        
        # Flush any remaining buffered segments
        flush_segments_to_file(output_path, segment_buffer)
        segment_buffer.clear()
        
        # Finalize
        transcribe_time = time.time() - start_transcribe
        
        if not audio_duration and last_end_time > 0:
            audio_duration = last_end_time
        
        finalize_stream_file(output_path, audio_duration, "complete")
        
        emit_progress("complete", 100, "Transcription complete!")
        emit_complete(output_path, segment_count, word_count, transcribe_time)
        
        # DO NOT try to cleanup the model explicitly!
        # The crash-during-cleanup is exactly what we're trying to avoid.
        # Just let the OS reclaim everything when the process exits.
        # This is the whole point of using a subprocess!
        
        # Flush stdout to ensure all messages are sent before exit
        sys.stdout.flush()
        
        return True
        
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        emit_error(error_msg)
        
        # Try to finalize with error status
        try:
            finalize_stream_file(output_path, 0, "error")
        except:
            pass
        
        return False


def main():
    parser = argparse.ArgumentParser(description="Transcribe audio using Whisper")
    parser.add_argument("audio_path", help="Path to audio file")
    parser.add_argument("output_path", help="Path for output JSON file")
    parser.add_argument("--model", default="large-v3", help="Whisper model size")
    parser.add_argument("--device", default="auto", help="Device (cuda/cpu/auto)")
    parser.add_argument("--segment-mode", default="natural", help="Segment mode (natural/sentence)")
    parser.add_argument("--vocabulary", default="", help="Comma-separated vocabulary words")
    
    args = parser.parse_args()
    
    vocabulary = [v.strip() for v in args.vocabulary.split(",") if v.strip()] if args.vocabulary else []
    
    success = run_transcription(
        audio_path=args.audio_path,
        output_path=args.output_path,
        model_size=args.model,
        device=args.device,
        vocabulary=vocabulary,
        segment_mode=args.segment_mode
    )
    
    # Use os._exit() for immediate termination without cleanup
    # This avoids crashes during Python/CUDA cleanup that cause the "Process crashed" error
    # The OS will reclaim all resources (GPU memory, file handles, etc.) anyway
    os._exit(0 if success else 1)


if __name__ == "__main__":
    main()
