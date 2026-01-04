"""
SRT (SubRip) subtitle exporter for PersonalTranscribe.
Generates subtitle files for video captioning.
"""

from typing import Optional

from src.models.transcript import Transcript
from src.export.base_exporter import BaseExporter


def format_srt_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        SRT-formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    milliseconds = int((secs - int(secs)) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{milliseconds:03d}"


class SRTExporter(BaseExporter):
    """Exports transcripts to SRT subtitle format."""
    
    @property
    def format_name(self) -> str:
        return "SRT Subtitles"
    
    @property
    def file_extension(self) -> str:
        return ".srt"
    
    def export(
        self,
        transcript: Transcript,
        output_path: str,
        max_line_length: int = 42,
        max_lines: int = 2,
        **options
    ) -> None:
        """Export transcript to SRT format.
        
        Args:
            transcript: Transcript to export
            output_path: Path for output SRT file
            max_line_length: Maximum characters per line
            max_lines: Maximum lines per subtitle
        """
        output_path = self.validate_output_path(output_path)
        self.ensure_output_directory(output_path)
        
        lines = []
        
        for i, segment in enumerate(transcript.segments):
            # Subtitle number
            lines.append(str(i + 1))
            
            # Timestamp line
            start_ts = format_srt_timestamp(segment.start_time)
            end_ts = format_srt_timestamp(segment.end_time)
            lines.append(f"{start_ts} --> {end_ts}")
            
            # Text (with line wrapping)
            text = segment.display_text
            wrapped_text = self._wrap_text(text, max_line_length, max_lines)
            lines.append(wrapped_text)
            
            # Blank line between subtitles
            lines.append("")
        
        # Write file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _wrap_text(self, text: str, max_length: int, max_lines: int) -> str:
        """Wrap text for subtitle display.
        
        Args:
            text: Text to wrap
            max_length: Maximum characters per line
            max_lines: Maximum number of lines
            
        Returns:
            Wrapped text with newlines
        """
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            if current_length + word_length + (1 if current_line else 0) <= max_length:
                current_line.append(word)
                current_length += word_length + (1 if current_length > 0 else 0)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
                
                if len(lines) >= max_lines:
                    break
        
        if current_line and len(lines) < max_lines:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)


class VTTExporter(BaseExporter):
    """Exports transcripts to WebVTT subtitle format."""
    
    @property
    def format_name(self) -> str:
        return "WebVTT Subtitles"
    
    @property
    def file_extension(self) -> str:
        return ".vtt"
    
    def export(
        self,
        transcript: Transcript,
        output_path: str,
        max_line_length: int = 42,
        max_lines: int = 2,
        **options
    ) -> None:
        """Export transcript to WebVTT format.
        
        Args:
            transcript: Transcript to export
            output_path: Path for output VTT file
            max_line_length: Maximum characters per line
            max_lines: Maximum lines per subtitle
        """
        output_path = self.validate_output_path(output_path)
        self.ensure_output_directory(output_path)
        
        lines = ["WEBVTT", ""]  # VTT header
        
        for i, segment in enumerate(transcript.segments):
            # Optional cue identifier
            lines.append(str(i + 1))
            
            # Timestamp line (VTT uses . instead of , for milliseconds)
            start_ts = format_srt_timestamp(segment.start_time).replace(",", ".")
            end_ts = format_srt_timestamp(segment.end_time).replace(",", ".")
            lines.append(f"{start_ts} --> {end_ts}")
            
            # Text
            text = segment.display_text
            srt_exporter = SRTExporter()
            wrapped_text = srt_exporter._wrap_text(text, max_line_length, max_lines)
            lines.append(wrapped_text)
            
            # Blank line between cues
            lines.append("")
        
        # Write file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
