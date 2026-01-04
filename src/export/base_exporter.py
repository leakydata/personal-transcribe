"""
Base exporter class for PersonalTranscribe.
Provides common functionality for all export formats.
"""

from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path

from src.models.transcript import Transcript


class BaseExporter(ABC):
    """Abstract base class for transcript exporters."""
    
    def __init__(self):
        """Initialize the exporter."""
        pass
    
    @abstractmethod
    def export(
        self,
        transcript: Transcript,
        output_path: str,
        **options
    ) -> None:
        """Export transcript to file.
        
        Args:
            transcript: Transcript to export
            output_path: Path for output file
            **options: Format-specific options
        """
        pass
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """Get the human-readable format name."""
        pass
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Get the file extension for this format."""
        pass
    
    def validate_output_path(self, output_path: str) -> str:
        """Validate and fix output path extension.
        
        Args:
            output_path: Proposed output path
            
        Returns:
            Validated output path with correct extension
        """
        path = Path(output_path)
        if path.suffix.lower() != self.file_extension.lower():
            return str(path.with_suffix(self.file_extension))
        return output_path
    
    def ensure_output_directory(self, output_path: str) -> None:
        """Ensure the output directory exists.
        
        Args:
            output_path: Path to output file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
