"""
Whisper transcription engine for PersonalTranscribe.
Wraps faster-whisper with word-level timestamps and progress reporting.
"""

import os
import warnings
from typing import Optional, Callable, List
from pathlib import Path

# Suppress HuggingFace symlink warning on Windows
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from faster_whisper import WhisperModel

from src.models.transcript import Transcript, Segment, Word


def check_cuda_available() -> bool:
    """Check if CUDA is available and working for faster-whisper."""
    try:
        import ctranslate2
        # Check if CUDA is supported
        if "cuda" in ctranslate2.get_supported_compute_types("cuda"):
            return True
    except Exception:
        pass
    return False


class WhisperEngine:
    """GPU-accelerated transcription using faster-whisper."""
    
    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto"
    ):
        """Initialize the Whisper engine.
        
        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use (cuda, cpu, auto). Auto will try CUDA first.
            compute_type: Compute type (float16, int8, int8_float16, auto)
        """
        self.model_size = model_size
        self.requested_device = device
        self.requested_compute_type = compute_type
        self.actual_device: str = "cpu"
        self.actual_compute_type: str = "int8"
        self.model: Optional[WhisperModel] = None
        self._is_loaded = False
    
    def _determine_device_and_compute(self) -> tuple:
        """Determine the best device and compute type to use.
        
        Returns:
            Tuple of (device, compute_type)
        """
        device = self.requested_device
        compute_type = self.requested_compute_type
        
        # Auto-detect device
        if device == "auto" or device == "cuda":
            try:
                import ctranslate2
                # Try to check CUDA support
                cuda_types = ctranslate2.get_supported_compute_types("cuda")
                if cuda_types:
                    device = "cuda"
                    if compute_type == "auto":
                        # Prefer float16 for best speed on modern GPUs
                        compute_type = "float16" if "float16" in cuda_types else "int8"
                else:
                    device = "cpu"
            except Exception as e:
                print(f"CUDA check failed: {e}. Falling back to CPU.")
                device = "cpu"
        
        # CPU compute type
        if device == "cpu":
            if compute_type == "auto" or compute_type == "float16":
                compute_type = "int8"  # int8 is faster on CPU
        
        return device, compute_type
    
    def load_model(self, progress_callback: Optional[Callable[[str], None]] = None) -> None:
        """Load the Whisper model.
        
        Args:
            progress_callback: Optional callback for progress updates
        """
        if self._is_loaded:
            return
        
        # Determine device and compute type
        self.actual_device, self.actual_compute_type = self._determine_device_and_compute()
        
        if progress_callback:
            progress_callback(
                f"Loading {self.model_size} model on {self.actual_device.upper()} "
                f"({self.actual_compute_type})..."
            )
        
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.actual_device,
                compute_type=self.actual_compute_type
            )
            self._is_loaded = True
            
            if progress_callback:
                progress_callback(
                    f"Model loaded on {self.actual_device.upper()} successfully"
                )
        except Exception as e:
            # If CUDA fails, fall back to CPU
            if self.actual_device == "cuda":
                if progress_callback:
                    progress_callback(f"CUDA failed ({e}). Falling back to CPU...")
                
                self.actual_device = "cpu"
                self.actual_compute_type = "int8"
                
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
                self._is_loaded = True
                
                if progress_callback:
                    progress_callback("Model loaded on CPU (fallback)")
            else:
                raise
    
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._is_loaded
    
    def transcribe(
        self,
        audio_path: str,
        vocabulary: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        language: Optional[str] = None
    ) -> Transcript:
        """Transcribe an audio file.
        
        Args:
            audio_path: Path to the audio file
            vocabulary: Optional list of custom words/phrases to help recognition
            progress_callback: Optional callback (progress_percent, message)
            language: Optional language code (e.g., "en"). Auto-detected if None.
            
        Returns:
            Transcript object with segments and word-level timestamps
        """
        if not self._is_loaded:
            self.load_model(
                progress_callback=lambda msg: progress_callback(0, msg) if progress_callback else None
            )
        
        # Build initial prompt from vocabulary
        initial_prompt = None
        if vocabulary:
            initial_prompt = " ".join(vocabulary)
        
        if progress_callback:
            progress_callback(5, "Starting transcription...")
        
        # Run transcription with word timestamps
        segments_generator, info = self.model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
            initial_prompt=initial_prompt,
            language=language,
            vad_filter=True,  # Voice activity detection for better accuracy
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=200
            )
        )
        
        if progress_callback:
            progress_callback(10, f"Detected language: {info.language} (probability: {info.language_probability:.2%})")
        
        # Convert generator to list and build Transcript
        transcript_segments = []
        segment_list = list(segments_generator)
        total_segments = len(segment_list)
        
        for i, segment in enumerate(segment_list):
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
            
            # Report progress
            if progress_callback:
                progress = 10 + (85 * (i + 1) / total_segments)
                progress_callback(progress, f"Processing segment {i + 1}/{total_segments}")
        
        # Get audio duration from info
        audio_duration = info.duration if hasattr(info, 'duration') else 0.0
        if not audio_duration and transcript_segments:
            audio_duration = transcript_segments[-1].end_time
        
        # Create transcript
        transcript = Transcript(
            segments=transcript_segments,
            audio_duration=audio_duration,
            audio_file=audio_path
        )
        
        if progress_callback:
            progress_callback(100, f"Transcription complete: {len(transcript_segments)} segments")
        
        return transcript
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        # Common languages supported by Whisper
        return [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr",
            "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi",
            "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no",
            "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk",
            "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk",
            "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw",
            "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc",
            "ka", "be", "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo",
            "ht", "ps", "tk", "nn", "mt", "sa", "lb", "my", "bo", "tl",
            "mg", "as", "tt", "haw", "ln", "ha", "ba", "jw", "su"
        ]


def get_available_models() -> List[str]:
    """Get list of available Whisper model sizes."""
    return [
        "tiny",
        "tiny.en",
        "base",
        "base.en",
        "small",
        "small.en",
        "medium",
        "medium.en",
        "large-v1",
        "large-v2",
        "large-v3"
    ]


def estimate_transcription_time(
    audio_duration_seconds: float,
    model_size: str = "large-v3",
    device: str = "cuda"
) -> float:
    """Estimate transcription time in seconds.
    
    Args:
        audio_duration_seconds: Duration of audio in seconds
        model_size: Whisper model size
        device: Device (cuda or cpu)
        
    Returns:
        Estimated time in seconds
    """
    # Approximate real-time factors (how much faster than real-time)
    # These are rough estimates for RTX 4090
    rtf_cuda = {
        "tiny": 50.0,
        "base": 40.0,
        "small": 30.0,
        "medium": 20.0,
        "large-v2": 15.0,
        "large-v3": 15.0
    }
    
    rtf_cpu = {
        "tiny": 5.0,
        "base": 3.0,
        "small": 1.5,
        "medium": 0.5,
        "large-v2": 0.2,
        "large-v3": 0.2
    }
    
    rtf_table = rtf_cuda if device == "cuda" else rtf_cpu
    rtf = rtf_table.get(model_size.split(".")[0], 10.0)
    
    return audio_duration_seconds / rtf
