"""
Recording metadata for PersonalTranscribe.
Stores information about the recording for legal and archival purposes.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class RecordingMetadata:
    """Metadata about a recording and its transcription."""
    
    # Recording information
    recording_date: Optional[str] = None  # Date of the recording
    recording_time: Optional[str] = None  # Time of the recording
    recording_location: Optional[str] = None  # Where it was recorded
    recording_source: Optional[str] = None  # Device/source (phone, recorder, etc.)
    
    # Participants
    participants: List[str] = field(default_factory=list)  # List of participant names
    
    # Case/Matter information
    case_number: Optional[str] = None  # Case or matter number
    case_name: Optional[str] = None  # Case or matter name
    client_name: Optional[str] = None  # Client name
    
    # Transcription information
    transcriptionist: Optional[str] = None  # Who transcribed it
    transcription_date: Optional[str] = None  # When it was transcribed
    
    # Additional notes
    notes: Optional[str] = None  # Any additional notes
    
    # Audio file info (auto-populated)
    original_filename: Optional[str] = None
    audio_duration: Optional[float] = None  # In seconds
    
    def __post_init__(self):
        """Set default transcription date if not provided."""
        if self.transcription_date is None:
            self.transcription_date = datetime.now().strftime("%Y-%m-%d")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "recording_date": self.recording_date,
            "recording_time": self.recording_time,
            "recording_location": self.recording_location,
            "recording_source": self.recording_source,
            "participants": self.participants,
            "case_number": self.case_number,
            "case_name": self.case_name,
            "client_name": self.client_name,
            "transcriptionist": self.transcriptionist,
            "transcription_date": self.transcription_date,
            "notes": self.notes,
            "original_filename": self.original_filename,
            "audio_duration": self.audio_duration,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RecordingMetadata":
        """Create from dictionary."""
        return cls(
            recording_date=data.get("recording_date"),
            recording_time=data.get("recording_time"),
            recording_location=data.get("recording_location"),
            recording_source=data.get("recording_source"),
            participants=data.get("participants", []),
            case_number=data.get("case_number"),
            case_name=data.get("case_name"),
            client_name=data.get("client_name"),
            transcriptionist=data.get("transcriptionist"),
            transcription_date=data.get("transcription_date"),
            notes=data.get("notes"),
            original_filename=data.get("original_filename"),
            audio_duration=data.get("audio_duration"),
        )
    
    def format_duration(self) -> str:
        """Format audio duration as HH:MM:SS."""
        if self.audio_duration is None:
            return "Unknown"
        
        hours = int(self.audio_duration // 3600)
        minutes = int((self.audio_duration % 3600) // 60)
        seconds = int(self.audio_duration % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
    
    def format_participants(self) -> str:
        """Format participants list as a string."""
        if not self.participants:
            return "Not specified"
        return ", ".join(self.participants)
    
    def get_header_lines(self) -> List[str]:
        """Get formatted header lines for export."""
        lines = []
        
        lines.append("=" * 60)
        lines.append("TRANSCRIPT INFORMATION")
        lines.append("=" * 60)
        lines.append("")
        
        # Case information
        if self.case_number or self.case_name:
            if self.case_name:
                lines.append(f"Case/Matter: {self.case_name}")
            if self.case_number:
                lines.append(f"Case Number: {self.case_number}")
            if self.client_name:
                lines.append(f"Client: {self.client_name}")
            lines.append("")
        
        # Recording information
        lines.append("RECORDING DETAILS")
        lines.append("-" * 40)
        
        if self.recording_date:
            date_str = self.recording_date
            if self.recording_time:
                date_str += f" at {self.recording_time}"
            lines.append(f"Date/Time: {date_str}")
        
        if self.recording_location:
            lines.append(f"Location: {self.recording_location}")
        
        if self.recording_source:
            lines.append(f"Source: {self.recording_source}")
        
        if self.original_filename:
            lines.append(f"Audio File: {self.original_filename}")
        
        lines.append(f"Duration: {self.format_duration()}")
        lines.append("")
        
        # Participants
        if self.participants:
            lines.append("PARTICIPANTS")
            lines.append("-" * 40)
            for i, participant in enumerate(self.participants, 1):
                lines.append(f"  {i}. {participant}")
            lines.append("")
        
        # Transcription information
        lines.append("TRANSCRIPTION")
        lines.append("-" * 40)
        if self.transcriptionist:
            lines.append(f"Transcribed by: {self.transcriptionist}")
        if self.transcription_date:
            lines.append(f"Transcription Date: {self.transcription_date}")
        lines.append("")
        
        # Notes
        if self.notes:
            lines.append("NOTES")
            lines.append("-" * 40)
            lines.append(self.notes)
            lines.append("")
        
        lines.append("=" * 60)
        lines.append("")
        
        return lines
    
    def is_empty(self) -> bool:
        """Check if metadata is essentially empty (no user-entered data)."""
        return not any([
            self.recording_date,
            self.recording_time,
            self.recording_location,
            self.recording_source,
            self.participants,
            self.case_number,
            self.case_name,
            self.client_name,
            self.transcriptionist,
            self.notes,
        ])
