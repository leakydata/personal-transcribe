"""
Transcript data model for PersonalTranscribe.
Contains Word, Segment, and Transcript classes with JSON serialization.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


@dataclass
class Word:
    """Represents a single word with timing and confidence information."""
    
    text: str
    start: float  # Start time in seconds
    end: float    # End time in seconds
    confidence: float  # 0.0 to 1.0
    
    @property
    def duration(self) -> float:
        """Get word duration in seconds."""
        return self.end - self.start
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Word":
        """Create Word from dictionary."""
        return cls(
            text=data["text"],
            start=data["start"],
            end=data["end"],
            confidence=data["confidence"]
        )


@dataclass
class Segment:
    """Represents a segment of transcribed speech."""
    
    id: str
    start_time: float  # Start time in seconds
    end_time: float    # End time in seconds
    text: str
    words: List[Word] = field(default_factory=list)
    speaker_label: str = ""  # Optional speaker prefix (Phase 5)
    is_bookmarked: bool = False  # For flagging (Phase 5)
    
    @property
    def duration(self) -> float:
        """Get segment duration in seconds."""
        return self.end_time - self.start_time
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all words."""
        if not self.words:
            return 1.0
        return sum(w.confidence for w in self.words) / len(self.words)
    
    @property
    def low_confidence_words(self) -> List[Word]:
        """Get words with confidence below 0.8."""
        return [w for w in self.words if w.confidence < 0.8]
    
    @property
    def display_text(self) -> str:
        """Get text with optional speaker label prefix."""
        if self.speaker_label:
            return f"{self.speaker_label}: {self.text}"
        return self.text
    
    def update_text(self, new_text: str) -> None:
        """Update segment text. Note: This doesn't update individual words."""
        self.text = new_text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
            "speaker_label": self.speaker_label,
            "is_bookmarked": self.is_bookmarked
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Segment":
        """Create Segment from dictionary."""
        words = [Word.from_dict(w) for w in data.get("words", [])]
        return cls(
            id=data["id"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            text=data["text"],
            words=words,
            speaker_label=data.get("speaker_label", ""),
            is_bookmarked=data.get("is_bookmarked", False)
        )
    
    @staticmethod
    def generate_id() -> str:
        """Generate a unique segment ID."""
        return f"seg_{uuid.uuid4().hex[:8]}"


@dataclass
class Gap:
    """Represents a gap (silence) between segments."""
    
    start_time: float
    end_time: float
    after_segment_id: str  # ID of segment before the gap
    
    @property
    def duration(self) -> float:
        """Get gap duration in seconds."""
        return self.end_time - self.start_time


class Transcript:
    """Container for a complete transcription with segments and metadata."""
    
    def __init__(
        self,
        segments: Optional[List[Segment]] = None,
        audio_duration: float = 0.0,
        audio_file: str = "",
        created_at: Optional[datetime] = None,
        modified_at: Optional[datetime] = None
    ):
        """Initialize transcript.
        
        Args:
            segments: List of transcript segments
            audio_duration: Total audio duration in seconds
            audio_file: Path to the source audio file
            created_at: When the transcript was created
            modified_at: When the transcript was last modified
        """
        self.segments = segments or []
        self.audio_duration = audio_duration
        self.audio_file = audio_file
        self.created_at = created_at or datetime.now()
        self.modified_at = modified_at or datetime.now()
    
    @property
    def total_speech_duration(self) -> float:
        """Calculate total duration of speech (excluding gaps)."""
        return sum(s.duration for s in self.segments)
    
    @property
    def total_gap_duration(self) -> float:
        """Calculate total duration of gaps."""
        return self.audio_duration - self.total_speech_duration
    
    @property
    def word_count(self) -> int:
        """Count total words in transcript."""
        return sum(len(s.text.split()) for s in self.segments)
    
    @property
    def segment_count(self) -> int:
        """Get number of segments."""
        return len(self.segments)
    
    def get_segment_by_id(self, segment_id: str) -> Optional[Segment]:
        """Find segment by ID."""
        for segment in self.segments:
            if segment.id == segment_id:
                return segment
        return None
    
    def get_segment_at_time(self, time_seconds: float) -> Optional[Segment]:
        """Find segment containing the given time."""
        for segment in self.segments:
            if segment.start_time <= time_seconds <= segment.end_time:
                return segment
        return None
    
    def get_segment_index(self, segment_id: str) -> int:
        """Get index of segment by ID. Returns -1 if not found."""
        for i, segment in enumerate(self.segments):
            if segment.id == segment_id:
                return i
        return -1
    
    def get_gaps(self, threshold: float = 0.5) -> List[Gap]:
        """Find gaps between segments above the threshold duration.
        
        Args:
            threshold: Minimum gap duration in seconds to include
            
        Returns:
            List of Gap objects
        """
        gaps = []
        
        # Check gap at the beginning
        if self.segments and self.segments[0].start_time > threshold:
            gaps.append(Gap(
                start_time=0.0,
                end_time=self.segments[0].start_time,
                after_segment_id=""
            ))
        
        # Check gaps between segments
        for i in range(len(self.segments) - 1):
            current = self.segments[i]
            next_seg = self.segments[i + 1]
            gap_duration = next_seg.start_time - current.end_time
            
            if gap_duration >= threshold:
                gaps.append(Gap(
                    start_time=current.end_time,
                    end_time=next_seg.start_time,
                    after_segment_id=current.id
                ))
        
        # Check gap at the end
        if self.segments and self.audio_duration > 0:
            last_end = self.segments[-1].end_time
            if self.audio_duration - last_end > threshold:
                gaps.append(Gap(
                    start_time=last_end,
                    end_time=self.audio_duration,
                    after_segment_id=self.segments[-1].id
                ))
        
        return gaps
    
    def get_bookmarked_segments(self) -> List[Segment]:
        """Get all bookmarked segments."""
        return [s for s in self.segments if s.is_bookmarked]
    
    def get_low_confidence_segments(self, threshold: float = 0.8) -> List[Segment]:
        """Get segments with average confidence below threshold."""
        return [s for s in self.segments if s.average_confidence < threshold]
    
    def add_segment(self, segment: Segment) -> None:
        """Add a segment to the transcript."""
        self.segments.append(segment)
        self.segments.sort(key=lambda s: s.start_time)
        self.modified_at = datetime.now()
    
    def remove_segment(self, segment_id: str) -> bool:
        """Remove a segment by ID. Returns True if removed."""
        for i, segment in enumerate(self.segments):
            if segment.id == segment_id:
                del self.segments[i]
                self.modified_at = datetime.now()
                return True
        return False
    
    def update_segment(self, segment_id: str, text: str) -> bool:
        """Update segment text by ID. Returns True if updated."""
        segment = self.get_segment_by_id(segment_id)
        if segment:
            segment.update_text(text)
            self.modified_at = datetime.now()
            return True
        return False
    
    def toggle_bookmark(self, segment_id: str) -> bool:
        """Toggle bookmark on a segment. Returns new bookmark state."""
        segment = self.get_segment_by_id(segment_id)
        if segment:
            segment.is_bookmarked = not segment.is_bookmarked
            self.modified_at = datetime.now()
            return segment.is_bookmarked
        return False
    
    def get_full_text(self, include_timestamps: bool = False) -> str:
        """Get the full transcript as plain text.
        
        Args:
            include_timestamps: If True, prefix each line with timestamp
            
        Returns:
            Full transcript text
        """
        lines = []
        for segment in self.segments:
            if include_timestamps:
                timestamp = format_timestamp(segment.start_time)
                lines.append(f"[{timestamp}] {segment.display_text}")
            else:
                lines.append(segment.display_text)
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "segments": [s.to_dict() for s in self.segments],
            "audio_duration": self.audio_duration,
            "audio_file": self.audio_file,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat()
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transcript":
        """Create Transcript from dictionary."""
        segments = [Segment.from_dict(s) for s in data.get("segments", [])]
        
        created_at = None
        if "created_at" in data:
            created_at = datetime.fromisoformat(data["created_at"])
        
        modified_at = None
        if "modified_at" in data:
            modified_at = datetime.fromisoformat(data["modified_at"])
        
        return cls(
            segments=segments,
            audio_duration=data.get("audio_duration", 0.0),
            audio_file=data.get("audio_file", ""),
            created_at=created_at,
            modified_at=modified_at
        )
    
    @classmethod
    def from_json(cls, json_string: str) -> "Transcript":
        """Create Transcript from JSON string."""
        data = json.loads(json_string)
        return cls.from_dict(data)


def format_timestamp(seconds: float, include_ms: bool = False) -> str:
    """Format seconds as HH:MM:SS or HH:MM:SS.mmm timestamp.
    
    Args:
        seconds: Time in seconds
        include_ms: If True, include milliseconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if include_ms:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
    else:
        return f"{hours:02d}:{minutes:02d}:{int(secs):02d}"


def format_timestamp_range(start: float, end: float) -> str:
    """Format a time range as start-end.
    
    Args:
        start: Start time in seconds
        end: End time in seconds
        
    Returns:
        Formatted time range string
    """
    return f"{format_timestamp(start)} - {format_timestamp(end)}"


def parse_timestamp(timestamp: str) -> float:
    """Parse HH:MM:SS or MM:SS timestamp to seconds.
    
    Args:
        timestamp: Timestamp string
        
    Returns:
        Time in seconds
    """
    parts = timestamp.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        return float(timestamp)
