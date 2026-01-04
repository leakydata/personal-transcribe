"""
Project management for PersonalTranscribe.
Handles saving and loading project files (.ptproj).
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from src.models.transcript import Transcript
from src.models.metadata import RecordingMetadata


@dataclass
class Project:
    """Represents a PersonalTranscribe project."""
    
    audio_file: str = ""
    transcript: Optional[Transcript] = None
    vocabulary: List[str] = field(default_factory=list)
    file_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)
    version: str = "1.1"  # Updated for metadata support
    
    # Project metadata
    title: str = ""
    notes: str = ""
    
    # Recording metadata for legal/archival purposes
    metadata: RecordingMetadata = field(default_factory=RecordingMetadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "audio_file": self.audio_file,
            "transcript": self.transcript.to_dict() if self.transcript else None,
            "vocabulary": self.vocabulary,
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat(),
            "title": self.title,
            "notes": self.notes,
            "metadata": self.metadata.to_dict() if self.metadata else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], file_path: Optional[str] = None) -> "Project":
        """Create project from dictionary."""
        transcript = None
        if data.get("transcript"):
            transcript = Transcript.from_dict(data["transcript"])
        
        created_at = datetime.now()
        if "created_at" in data:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        
        modified_at = datetime.now()
        if "modified_at" in data:
            try:
                modified_at = datetime.fromisoformat(data["modified_at"])
            except (ValueError, TypeError):
                pass
        
        # Load metadata
        metadata = RecordingMetadata()
        if data.get("metadata"):
            metadata = RecordingMetadata.from_dict(data["metadata"])
        
        return cls(
            audio_file=data.get("audio_file", ""),
            transcript=transcript,
            vocabulary=data.get("vocabulary", []),
            file_path=file_path,
            created_at=created_at,
            modified_at=modified_at,
            version=data.get("version", "1.0"),
            title=data.get("title", ""),
            notes=data.get("notes", ""),
            metadata=metadata
        )
    
    def update_modified(self):
        """Update the modified timestamp."""
        self.modified_at = datetime.now()


class ProjectManager:
    """Manages project file operations."""
    
    PROJECT_EXTENSION = ".ptproj"
    
    @classmethod
    def save(cls, project: Project, file_path: str) -> None:
        """Save project to file.
        
        Args:
            project: Project to save
            file_path: Path to save to
        """
        # Ensure correct extension
        if not file_path.endswith(cls.PROJECT_EXTENSION):
            file_path += cls.PROJECT_EXTENSION
        
        # Update modified time
        project.update_modified()
        project.file_path = file_path
        
        # Convert to JSON
        data = project.to_dict()
        
        # Write file
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, file_path: str) -> Project:
        """Load project from file.
        
        Args:
            file_path: Path to project file
            
        Returns:
            Loaded Project object
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Project.from_dict(data, file_path=file_path)
    
    @classmethod
    def exists(cls, file_path: str) -> bool:
        """Check if project file exists."""
        return os.path.exists(file_path)
    
    @classmethod
    def create_backup(cls, file_path: str) -> str:
        """Create a backup of the project file.
        
        Args:
            file_path: Path to project file
            
        Returns:
            Path to backup file
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Project file not found: {file_path}")
        
        # Create backup filename with timestamp
        base, ext = os.path.splitext(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{base}_backup_{timestamp}{ext}"
        
        # Copy file
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    @classmethod
    def get_project_info(cls, file_path: str) -> Dict[str, Any]:
        """Get basic info about a project without fully loading it.
        
        Args:
            file_path: Path to project file
            
        Returns:
            Dictionary with project info
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return {
            "title": data.get("title", os.path.basename(file_path)),
            "audio_file": data.get("audio_file", ""),
            "version": data.get("version", "1.0"),
            "created_at": data.get("created_at"),
            "modified_at": data.get("modified_at"),
            "has_transcript": data.get("transcript") is not None,
            "vocabulary_count": len(data.get("vocabulary", []))
        }
