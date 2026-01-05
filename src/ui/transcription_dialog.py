"""
Detailed transcription progress dialog for PersonalTranscribe.
Shows verbose output about model loading, device detection, and transcription progress.
"""

import os
import time
import tempfile
import gc
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QTextEdit, QPushButton, QGroupBox, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor

from src.utils.logger import get_logger

# Formats that benefit from preprocessing (compressed formats)
COMPRESSED_FORMATS = {'.mp3', '.m4a', '.aac', '.ogg', '.wma', '.flac', '.opus'}

# Module logger
logger = get_logger("transcription")


class TranscriptionWorkerV2(QThread):
    """Enhanced transcription worker with detailed progress reporting."""
    
    log_message = pyqtSignal(str, str)  # message, level (info/warning/error/success)
    progress = pyqtSignal(float)  # percent 0-100
    stage_changed = pyqtSignal(str)  # current stage name
    segment_processed = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(object)  # Transcript or None
    error = pyqtSignal(str)
    device_detected = pyqtSignal(str, str)  # device, compute_type
    cancelled = pyqtSignal()  # Emitted when cancellation completes
    
    def __init__(
        self,
        audio_path: str,
        vocabulary: list,
        model_size: str = "large-v3",
        device: str = "auto",
        segment_mode: str = "natural"  # "natural" or "sentence"
    ):
        super().__init__()
        self.audio_path = audio_path
        self.vocabulary = vocabulary
        self.model_size = model_size
        self.device = device
        self.segment_mode = segment_mode
        self._cancelled = False
        self._model = None  # Keep reference for cleanup
        self._temp_audio_path: Optional[str] = None  # For preprocessed audio
        self._stream_file_path: Optional[str] = None  # For streaming transcription to disk
    
    def cancel(self):
        """Request cancellation."""
        self._cancelled = True
        self.log_message.emit("Cancellation requested - stopping after current operation...", "warning")
    
    def _preprocess_audio(self, audio_path: str) -> str:
        """
        Preprocess audio to 16kHz mono WAV for optimal Whisper performance.
        Returns path to preprocessed file (or original if already optimal).
        """
        ext = Path(audio_path).suffix.lower()
        
        # Check if preprocessing would help
        if ext not in COMPRESSED_FORMATS:
            self.log_message.emit(f"Audio format {ext} - no preprocessing needed", "info")
            return audio_path
        
        self.log_message.emit(f"Preprocessing {ext} audio for faster transcription...", "info")
        
        try:
            import soundfile as sf
            import numpy as np
            
            # Read audio file
            self.log_message.emit("Loading audio file...", "info")
            start_time = time.time()
            
            # Use pydub for better format support
            from pydub import AudioSegment
            
            audio = AudioSegment.from_file(audio_path)
            original_duration = len(audio) / 1000.0  # seconds
            original_channels = audio.channels
            original_rate = audio.frame_rate
            
            self.log_message.emit(
                f"Original: {original_rate}Hz, {original_channels} channel(s), {original_duration:.1f}s",
                "info"
            )
            
            # Convert to 16kHz mono (Whisper's native format)
            audio = audio.set_channels(1)  # Mono
            audio = audio.set_frame_rate(16000)  # 16kHz
            
            # Export to temp WAV file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"whisper_preprocessed_{os.getpid()}.wav")
            
            audio.export(temp_path, format="wav")
            self._temp_audio_path = temp_path
            
            elapsed = time.time() - start_time
            file_size_mb = os.path.getsize(temp_path) / (1024 * 1024)
            
            self.log_message.emit(
                f"Preprocessed to 16kHz mono WAV ({file_size_mb:.1f}MB) in {elapsed:.1f}s",
                "success"
            )
            
            return temp_path
            
        except Exception as e:
            self.log_message.emit(f"Preprocessing failed: {e} - using original file", "warning")
            return audio_path
    
    def _cleanup_temp_files(self):
        """Clean up any temporary files created during processing."""
        if self._temp_audio_path and os.path.exists(self._temp_audio_path):
            try:
                os.remove(self._temp_audio_path)
                self.log_message.emit("Cleaned up temporary files", "info")
            except Exception as e:
                self.log_message.emit(f"Could not clean temp file: {e}", "warning")
    
    def _init_stream_file(self) -> str:
        """Initialize streaming JSON file for transcription.
        
        Creates a JSON file that segments will be appended to during transcription.
        This ensures partial work is saved even if the app crashes.
        
        Returns:
            Path to the streaming file
        """
        import json
        from datetime import datetime
        
        # Create streaming directory
        stream_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "PersonalTranscribe",
            "streaming"
        )
        os.makedirs(stream_dir, exist_ok=True)
        
        # Create filename based on audio file and timestamp
        audio_name = Path(self.audio_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stream_filename = f"{audio_name}_{timestamp}.json"
        stream_path = os.path.join(stream_dir, stream_filename)
        
        # Initialize the file with metadata
        initial_data = {
            "version": "1.0",
            "status": "in_progress",
            "audio_file": self.audio_path,
            "model": self.model_size,
            "started_at": datetime.now().isoformat(),
            "audio_duration": 0,
            "segments": []
        }
        
        with open(stream_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2)
        
        self._stream_file_path = stream_path
        self.log_message.emit(f"Streaming to: {stream_filename}", "info")
        logger.info(f"Streaming transcription to: {stream_path}")
        
        return stream_path
    
    def _append_segment_to_stream(self, segment_data: dict):
        """Append a segment to the streaming JSON file.
        
        Args:
            segment_data: Dict with segment info (id, start, end, text, words)
        """
        import json
        
        if not self._stream_file_path:
            return
        
        try:
            # Read current file
            with open(self._stream_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Append segment
            data["segments"].append(segment_data)
            
            # Write back
            with open(self._stream_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.warning(f"Failed to append segment to stream: {e}")
    
    def _finalize_stream_file(self, audio_duration: float, status: str = "complete"):
        """Finalize the streaming file with completion status.
        
        Args:
            audio_duration: Total audio duration
            status: Final status (complete, cancelled, error)
        """
        import json
        from datetime import datetime
        
        if not self._stream_file_path:
            return
        
        try:
            with open(self._stream_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data["status"] = status
            data["audio_duration"] = audio_duration
            data["completed_at"] = datetime.now().isoformat()
            data["segment_count"] = len(data["segments"])
            
            with open(self._stream_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self.log_message.emit(f"Saved {len(data['segments'])} segments to recovery file", "success")
            logger.info(f"Stream file finalized: {self._stream_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to finalize stream file: {e}")
    
    def get_stream_file_path(self) -> Optional[str]:
        """Get the path to the streaming file (for recovery purposes)."""
        return self._stream_file_path
    
    @staticmethod
    def load_from_stream_file(stream_path: str) -> Optional['Transcript']:
        """Load a transcript from a streaming JSON file.
        
        Args:
            stream_path: Path to the streaming JSON file
            
        Returns:
            Transcript object, or None if loading failed
        """
        import json
        from src.models.transcript import Transcript, Segment, Word
        
        try:
            with open(stream_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            segments = []
            for seg_data in data.get("segments", []):
                words = []
                for word_data in seg_data.get("words", []):
                    words.append(Word(
                        text=word_data["text"],
                        start=word_data["start"],
                        end=word_data["end"],
                        confidence=word_data["confidence"]
                    ))
                
                segment = Segment(
                    id=seg_data["id"],
                    start_time=seg_data["start_time"],
                    end_time=seg_data["end_time"],
                    text=seg_data["text"],
                    words=words
                )
                segments.append(segment)
            
            transcript = Transcript(
                segments=segments,
                audio_duration=data.get("audio_duration", 0),
                audio_file=data.get("audio_file", "")
            )
            
            logger.info(f"Loaded {len(segments)} segments from stream file: {stream_path}")
            return transcript
            
        except Exception as e:
            logger.error(f"Failed to load stream file: {e}")
            return None
    
    def run(self):
        try:
            logger.info(f"Starting transcription: {self.audio_path}")
            logger.info(f"Model: {self.model_size}, Device preference: {self.device}")
            
            import os
            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            
            from faster_whisper import WhisperModel
            from src.models.transcript import Transcript, Segment, Word
            
            # Stage 1: Detect device
            self.stage_changed.emit("Detecting GPU/CUDA support...")
            self.log_message.emit("Checking CUDA availability...", "info")
            logger.debug("Checking CUDA availability...")
            
            device, compute_type = self._determine_device()
            self.device_detected.emit(device, compute_type)
            logger.info(f"Device detected: {device}, compute_type: {compute_type}")
            
            if device == "cuda":
                self.log_message.emit(f"CUDA available! Using GPU with {compute_type}", "success")
            else:
                self.log_message.emit("CUDA not available. Using CPU (this will be slower)", "warning")
            
            if self._cancelled:
                return
            
            # Stage 2: Check model cache
            self.stage_changed.emit("Checking model cache...")
            cache_path = self._get_model_cache_path()
            
            if cache_path and cache_path.exists():
                self.log_message.emit(f"Model found in cache: {cache_path}", "info")
            else:
                self.log_message.emit(f"Model not cached. Will download {self.model_size} (~3GB)...", "warning")
            
            if self._cancelled:
                return
            
            # Stage 3: Load model
            self.stage_changed.emit("Loading Whisper model...")
            self.log_message.emit(f"Loading {self.model_size} model on {device.upper()}...", "info")
            self.progress.emit(5)
            
            start_load = time.time()
            
            try:
                model = WhisperModel(
                    self.model_size,
                    device=device,
                    compute_type=compute_type
                )
                load_time = time.time() - start_load
                self.log_message.emit(f"Model loaded in {load_time:.1f} seconds", "success")
            except Exception as e:
                error_msg = str(e)
                if "cudnn" in error_msg.lower() or "cuda" in error_msg.lower():
                    self.log_message.emit(f"GPU failed: {error_msg}", "error")
                    self.log_message.emit("Falling back to CPU...", "warning")
                    device = "cpu"
                    compute_type = "int8"
                    self.device_detected.emit(device, compute_type)
                    model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                    self.log_message.emit("Model loaded on CPU (fallback)", "warning")
                else:
                    raise
            
            if self._cancelled:
                self._cleanup_temp_files()
                return
            
            self.progress.emit(10)
            
            # Stage 4: Preprocess audio (if needed)
            self.stage_changed.emit("Preparing audio...")
            self.log_message.emit(f"Audio file: {Path(self.audio_path).name}", "info")
            
            audio_path_for_transcription = self._preprocess_audio(self.audio_path)
            
            if self._cancelled:
                self._cleanup_temp_files()
                return
            
            self.progress.emit(12)
            
            # Stage 5: Prepare transcription
            self.stage_changed.emit("Starting transcription...")
            
            initial_prompt = None
            if self.vocabulary:
                initial_prompt = " ".join(self.vocabulary)
                self.log_message.emit(f"Using {len(self.vocabulary)} vocabulary words", "info")
            
            # Stage 6: Run transcription
            self.log_message.emit("Detecting language and running VAD...", "info")
            
            # Configure VAD parameters based on segment mode
            if self.segment_mode == "sentence":
                # Sentence mode: longer segments, only split on significant pauses
                vad_params = dict(
                    min_silence_duration_ms=2000,  # Wait 2 seconds of silence before splitting
                    speech_pad_ms=400,  # More padding around speech
                    min_speech_duration_ms=500,  # Minimum speech segment length
                    max_speech_duration_s=60,  # Allow longer segments (up to 60s)
                )
                self.log_message.emit("Using SENTENCE mode - longer, more complete segments", "info")
            else:
                # Natural mode: shorter segments following audio pauses
                vad_params = dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200
                )
                self.log_message.emit("Using NATURAL mode - shorter segments", "info")
            
            start_transcribe = time.time()
            
            segments_generator, info = model.transcribe(
                audio_path_for_transcription,
                beam_size=5,
                word_timestamps=True,
                initial_prompt=initial_prompt,
                language=None,  # Auto-detect
                vad_filter=True,
                vad_parameters=vad_params
            )
            
            audio_duration = info.duration if hasattr(info, 'duration') else 0
            self.log_message.emit(
                f"Language: {info.language} (confidence: {info.language_probability:.1%})", 
                "info"
            )
            self.log_message.emit(f"Audio duration: {audio_duration/60:.1f} minutes", "info")
            
            if device == "cuda":
                expected_rtf = 15.0  # 15x realtime for large-v3 on good GPU
                est_time = audio_duration / expected_rtf
            else:
                expected_rtf = 0.2  # 0.2x realtime (5x slower than realtime) on CPU
                est_time = audio_duration / expected_rtf
            
            self.log_message.emit(f"Estimated time: {est_time/60:.1f} minutes", "info")
            self.log_message.emit("-" * 40, "info")
            
            self.stage_changed.emit("Transcribing audio...")
            self.progress.emit(15)
            
            # Initialize streaming file for crash recovery
            self._init_stream_file()
            
            # Process segments from generator (allows cancellation during transcription)
            transcript_segments = []
            segment_count = 0
            last_end_time = 0.0
            
            self.log_message.emit("Processing audio segments (streaming to disk)...", "info")
            
            for segment in segments_generator:
                try:
                    # Check for cancellation after each segment
                    if self._cancelled:
                        logger.info(f"Transcription cancelled after {segment_count} segments")
                        self.log_message.emit(f"Cancelled after {segment_count} segments", "warning")
                        self._finalize_stream_file(last_end_time, status="cancelled")
                        self._cleanup_temp_files()
                        self.cancelled.emit()
                        return
                    
                    segment_count += 1
                    
                    # Extract word-level data
                    words = []
                    if segment.words:
                        for word_info in segment.words:
                            words.append(Word(
                                text=word_info.word.strip(),
                                start=word_info.start,
                                end=word_info.end,
                                confidence=word_info.probability
                            ))
                    
                    # Create segment
                    transcript_segment = Segment(
                        id=Segment.generate_id(),
                        start_time=segment.start,
                        end_time=segment.end,
                        text=segment.text.strip(),
                        words=words
                    )
                    transcript_segments.append(transcript_segment)
                    last_end_time = segment.end
                    
                    # Stream segment to disk for crash recovery
                    segment_data = {
                        "id": transcript_segment.id,
                        "start_time": transcript_segment.start_time,
                        "end_time": transcript_segment.end_time,
                        "text": transcript_segment.text,
                        "words": [
                            {
                                "text": w.text,
                                "start": w.start,
                                "end": w.end,
                                "confidence": w.confidence
                            }
                            for w in transcript_segment.words
                        ]
                    }
                    self._append_segment_to_stream(segment_data)
                    
                    # Estimate progress based on audio position
                    if audio_duration > 0:
                        progress = 15 + (80 * (segment.end / audio_duration))
                        self.progress.emit(min(progress, 95))
                    
                    self.segment_processed.emit(segment_count, -1)  # -1 = unknown total
                    
                    # Log every 10 segments or first
                    if segment_count == 1 or segment_count % 10 == 0:
                        preview = segment.text[:50] + "..." if len(segment.text) > 50 else segment.text
                        self.log_message.emit(
                            f"[{segment_count}] {self._format_time(segment.start)} - {preview}",
                            "info"
                        )
                        logger.debug(f"Segment {segment_count}: {segment.start:.1f}s - {segment.end:.1f}s")
                    
                    # Periodic garbage collection to prevent memory buildup
                    if segment_count % 50 == 0:
                        gc.collect()
                        logger.debug(f"GC after segment {segment_count}")
                        
                except Exception as seg_error:
                    logger.error(f"Error processing segment {segment_count}: {seg_error}", exc_info=True)
                    self.log_message.emit(f"Warning: Error in segment {segment_count}: {seg_error}", "warning")
                    # Continue with next segment instead of failing completely
            
            # Final segment count
            total_segments = segment_count
            
            # Finalize
            transcribe_time = time.time() - start_transcribe
            actual_rtf = audio_duration / transcribe_time if transcribe_time > 0 else 0
            
            self.log_message.emit("-" * 40, "info")
            self.log_message.emit(f"Transcription completed in {transcribe_time:.1f}s", "success")
            self.log_message.emit(f"Speed: {actual_rtf:.1f}x realtime", "success")
            
            # Post-process: merge sentence fragments in sentence mode
            if self.segment_mode == "sentence" and len(transcript_segments) > 1:
                original_count = len(transcript_segments)
                transcript_segments = self._merge_sentence_fragments(transcript_segments)
                merged_count = original_count - len(transcript_segments)
                if merged_count > 0:
                    self.log_message.emit(
                        f"Merged {merged_count} sentence fragments ({original_count} -> {len(transcript_segments)} segments)",
                        "info"
                    )
            
            # Create transcript
            if not audio_duration and transcript_segments:
                audio_duration = transcript_segments[-1].end_time
            
            transcript = Transcript(
                segments=transcript_segments,
                audio_duration=audio_duration,
                audio_file=self.audio_path
            )
            
            word_count = sum(len(s.words) for s in transcript_segments)
            self.log_message.emit(f"Total: {len(transcript_segments)} segments, {word_count} words", "success")
            logger.info(f"Transcription complete: {total_segments} segments, {word_count} words, {transcribe_time:.1f}s")
            
            # Finalize streaming file
            self._finalize_stream_file(audio_duration, status="complete")
            
            # Cleanup temp files
            self._cleanup_temp_files()
            
            # Final garbage collection
            gc.collect()
            
            self.progress.emit(100)
            self.stage_changed.emit("Complete!")
            self.finished.emit(transcript)
            
        except Exception as e:
            import traceback
            error_tb = traceback.format_exc()
            logger.critical(f"Transcription failed: {e}", exc_info=True)
            
            # Finalize stream file with error status (preserves partial work)
            if self._stream_file_path:
                self._finalize_stream_file(0, status="error")
                self.log_message.emit(f"Partial transcript saved for recovery", "warning")
            
            self._cleanup_temp_files()
            self.log_message.emit(f"ERROR: {str(e)}", "error")
            self.error.emit(f"{str(e)}\n\n{error_tb}")
    
    def _determine_device(self) -> tuple:
        """Determine best device and compute type."""
        try:
            import ctranslate2
            cuda_types = ctranslate2.get_supported_compute_types("cuda")
            if cuda_types:
                compute_type = "float16" if "float16" in cuda_types else "int8"
                return "cuda", compute_type
        except Exception as e:
            self.log_message.emit(f"CUDA check error: {e}", "warning")
        
        return "cpu", "int8"
    
    def _merge_sentence_fragments(self, segments: list) -> list:
        """
        Merge sentence fragments into complete sentences.
        
        A segment is considered a fragment if it doesn't end with
        sentence-ending punctuation (. ! ?) and the next segment
        starts within a short time gap.
        """
        from src.models.transcript import Segment, Word
        import re
        
        if len(segments) <= 1:
            return segments
        
        # Sentence-ending punctuation pattern
        sentence_end_pattern = re.compile(r'[.!?]["\']*$')
        
        merged = []
        i = 0
        
        while i < len(segments):
            current = segments[i]
            
            # Check if this segment ends with sentence-ending punctuation
            text = current.text.strip()
            ends_with_sentence = bool(sentence_end_pattern.search(text))
            
            if ends_with_sentence or i == len(segments) - 1:
                # Complete sentence or last segment - keep as is
                merged.append(current)
                i += 1
            else:
                # Fragment - try to merge with next segments
                merge_count = 0
                merged_text_parts = [current.text.strip()]
                merged_words = list(current.words)
                end_time = current.end_time
                
                j = i + 1
                while j < len(segments):
                    next_seg = segments[j]
                    gap = next_seg.start_time - end_time
                    
                    # Only merge if gap is small (< 3 seconds)
                    if gap > 3.0:
                        break
                    
                    merged_text_parts.append(next_seg.text.strip())
                    merged_words.extend(next_seg.words)
                    end_time = next_seg.end_time
                    merge_count += 1
                    
                    # Check if merged text now ends with sentence punctuation
                    combined_text = " ".join(merged_text_parts)
                    if sentence_end_pattern.search(combined_text):
                        break
                    
                    # Don't merge more than 5 segments at once
                    if merge_count >= 5:
                        break
                    
                    j += 1
                
                # Create merged segment
                merged_text = " ".join(merged_text_parts)
                merged_segment = Segment(
                    id=current.id,
                    start_time=current.start_time,
                    end_time=end_time,
                    text=merged_text,
                    words=merged_words,
                    speaker_label=current.speaker_label,
                    is_bookmarked=current.is_bookmarked
                )
                merged.append(merged_segment)
                i = j + 1
        
        return merged
    
    def _get_model_cache_path(self) -> Optional[Path]:
        """Get the expected model cache path."""
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        model_name = f"models--Systran--faster-whisper-{self.model_size}"
        return cache_dir / model_name
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"


class TranscriptionProgressDialog(QDialog):
    """Detailed progress dialog for transcription."""
    
    transcription_complete = pyqtSignal(str)  # File path to load from
    
    def __init__(
        self,
        audio_path: str,
        vocabulary: list,
        model_size: str = "large-v3",
        device: str = "auto",
        segment_mode: str = "natural",
        parent=None
    ):
        super().__init__(parent)
        self.audio_path = audio_path
        self.vocabulary = vocabulary
        self.model_size = model_size
        self.device = device
        self.segment_mode = segment_mode
        
        self.worker: Optional[TranscriptionWorkerV2] = None
        self.start_time: Optional[float] = None
        
        self._init_ui()
        self._setup_timer()
    
    def _init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("Transcription Progress")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Status header
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QGridLayout(header_frame)
        
        # Stage label
        self.stage_label = QLabel("Initializing...")
        self.stage_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.stage_label, 0, 0, 1, 2)
        
        # Device info
        header_layout.addWidget(QLabel("Device:"), 1, 0)
        self.device_label = QLabel("Detecting...")
        self.device_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.device_label, 1, 1)
        
        # Model info
        header_layout.addWidget(QLabel("Model:"), 2, 0)
        self.model_label = QLabel(self.model_size)
        header_layout.addWidget(self.model_label, 2, 1)
        
        # Time elapsed
        header_layout.addWidget(QLabel("Time Elapsed:"), 3, 0)
        self.time_label = QLabel("00:00")
        header_layout.addWidget(self.time_label, 3, 1)
        
        # Segment progress
        header_layout.addWidget(QLabel("Segments:"), 4, 0)
        self.segment_label = QLabel("--")
        header_layout.addWidget(self.segment_label, 4, 1)
        
        layout.addWidget(header_frame)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Detailed Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(200)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        self.force_close_button = QPushButton("Force Close")
        self.force_close_button.clicked.connect(self._on_force_close)
        self.force_close_button.setVisible(False)
        self.force_close_button.setStyleSheet("background-color: #DC143C; color: white;")
        button_layout.addWidget(self.force_close_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _setup_timer(self):
        """Setup elapsed time timer."""
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)
    
    def start(self):
        """Start the transcription process."""
        self.start_time = time.time()
        self.elapsed_timer.start(1000)
        
        self._log("Starting transcription process...", "info")
        self._log(f"Audio: {Path(self.audio_path).name}", "info")
        self._log("-" * 40, "info")
        
        self.worker = TranscriptionWorkerV2(
            audio_path=self.audio_path,
            vocabulary=self.vocabulary,
            model_size=self.model_size,
            device=self.device,
            segment_mode=self.segment_mode
        )
        
        self.worker.log_message.connect(self._log)
        self.worker.progress.connect(self._on_progress)
        self.worker.stage_changed.connect(self._on_stage_changed)
        self.worker.segment_processed.connect(self._on_segment_processed)
        self.worker.device_detected.connect(self._on_device_detected)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.cancelled.connect(self._on_cancelled)
        
        self.worker.start()
    
    def _log(self, message: str, level: str = "info"):
        """Add a message to the log."""
        colors = {
            "info": "#000000",
            "warning": "#B8860B",
            "error": "#DC143C",
            "success": "#228B22"
        }
        color = colors.get(level, "#000000")
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        
        if level == "error":
            self.log_text.append(f'<span style="color: {color}; font-weight: bold;">[ERROR] {message}</span>')
        elif level == "warning":
            self.log_text.append(f'<span style="color: {color};">[WARN] {message}</span>')
        elif level == "success":
            self.log_text.append(f'<span style="color: {color}; font-weight: bold;">{message}</span>')
        else:
            self.log_text.append(f'<span style="color: {color};">{message}</span>')
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _on_progress(self, percent: float):
        """Handle progress update."""
        self.progress_bar.setValue(int(percent))
    
    def _on_stage_changed(self, stage: str):
        """Handle stage change."""
        self.stage_label.setText(stage)
    
    def _on_segment_processed(self, current: int, total: int):
        """Handle segment processed."""
        if total < 0:
            self.segment_label.setText(f"{current} processed")
        else:
            self.segment_label.setText(f"{current} / {total}")
    
    def _on_device_detected(self, device: str, compute_type: str):
        """Handle device detection."""
        if device == "cuda":
            self.device_label.setText(f"GPU (CUDA) - {compute_type}")
            self.device_label.setStyleSheet("font-weight: bold; color: green;")
        else:
            self.device_label.setText(f"CPU - {compute_type}")
            self.device_label.setStyleSheet("font-weight: bold; color: orange;")
    
    def _on_finished(self, transcript):
        """Handle transcription complete."""
        self.elapsed_timer.stop()
        self.progress_bar.setValue(100)
        self.stage_label.setText("Finalizing...")
        
        # Store results for the delayed handler
        self._result_transcript = transcript
        
        # Schedule cleanup and emission on the next main loop iteration
        # This allows the worker thread signal to complete fully before we do heavy UI work or close
        QTimer.singleShot(200, self._finalize_and_close)

    def _finalize_and_close(self):
        """Safely finalize the dialog and emit results."""
        transcript = getattr(self, '_result_transcript', None)
        
        self.cancel_button.setEnabled(False)
        self.force_close_button.setVisible(False)
        self.close_button.setEnabled(True)
        
        # Get the streaming file path
        file_path = ""
        if self.worker:
            file_path = getattr(self.worker, '_stream_file_path', "") or ""
            
        if transcript and file_path:
            logger.info(f"Transcription dialog emitting file path: {file_path}")
            try:
                self.transcription_complete.emit(file_path)
                logger.debug("File path emitted successfully")
                
                # Auto-close the dialog on success so the main window can proceed
                # Schedule this slightly later to ensure the signal is processed
                self.stage_label.setText("Complete! Closing...")
                QTimer.singleShot(500, self.accept)
                
            except Exception as e:
                logger.error(f"Error emitting file path: {e}", exc_info=True)
                self.stage_label.setText("Error finalizing")
        elif transcript:
            logger.warning("Transcription complete but no streaming file path available")
            self.stage_label.setText("Complete (No saved file)")
    
    def _on_error(self, error_message: str):
        """Handle error."""
        self.elapsed_timer.stop()
        self.cancel_button.setEnabled(False)
        self.force_close_button.setVisible(False)
        self.close_button.setEnabled(True)
        self.stage_label.setText("Error!")
        self._log(error_message, "error")
    
    def _on_cancelled(self):
        """Handle cancellation complete."""
        self.elapsed_timer.stop()
        self.cancel_button.setEnabled(False)
        self.force_close_button.setVisible(False)
        self.close_button.setEnabled(True)
        self.stage_label.setText("Cancelled")
        self._log("Transcription cancelled successfully", "warning")
    
    def _on_cancel(self):
        """Handle cancel button."""
        if self.worker:
            self.worker.cancel()
            self._log("Cancellation requested - waiting for current segment to finish...", "warning")
            self._log("(Click 'Force Close' if it takes too long)", "warning")
            self.cancel_button.setEnabled(False)
            self.force_close_button.setVisible(True)
            self.stage_label.setText("Cancelling (waiting for GPU)...")
    
    def _on_force_close(self):
        """Force close the dialog without waiting for thread."""
        self._log("Force closing - transcription may continue in background briefly", "warning")
        self.elapsed_timer.stop()
        
        # Clean up temp files if possible
        if self.worker:
            self.worker._cleanup_temp_files()
        
        # Don't wait for thread, just close
        self.reject()
    
    def _update_elapsed_time(self):
        """Update elapsed time display."""
        if self.start_time:
            elapsed = time.time() - self.start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            self.time_label.setText(f"{mins:02d}:{secs:02d}")
    
    def closeEvent(self, event):
        """Handle close event."""
        logger.debug("TranscriptionProgressDialog.closeEvent called")
        self.elapsed_timer.stop()
        
        if self.worker:
            if self.worker.isRunning():
                logger.warning("Worker thread is still running during close. requesting cancel...")
                # Request cancellation
                self.worker.cancel()
                
                # Wait for thread to finish gracefully (up to 2s)
                logger.debug("Waiting for worker thread to finish (timeout 2s)...")
                if self.worker.wait(2000):
                    logger.debug("Worker thread finished gracefully")
                else:
                    logger.warning("Worker thread did not finish in time. Detaching.")
                    # We can't terminate() safely in Python usually.
                    # Ideally we would block, but we don't want to freeze UI totally.
            else:
                logger.debug("Worker thread was already finished")
            
            # Unhook signals to prevent post-death calls
            try:
                self.worker.log_message.disconnect()
                self.worker.progress.disconnect()
                self.worker.finished.disconnect()
                self.worker.error.disconnect()
            except:
                pass
        
        logger.debug("Accepting close event")
        event.accept()
