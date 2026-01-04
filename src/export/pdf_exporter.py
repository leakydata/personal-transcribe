"""
PDF exporter for PersonalTranscribe.
Generates professional timestamped PDF transcripts for legal use.
"""

import os
from datetime import datetime
from typing import Optional

from fpdf import FPDF

from src.models.transcript import Transcript, format_timestamp, format_timestamp_range
from src.export.base_exporter import BaseExporter


class TranscriptPDF(FPDF):
    """Custom PDF class with header and footer."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.include_page_numbers = True
        self.header_text = ""
        self.footer_text = ""
    
    def header(self):
        """Add header to each page."""
        if self.header_text:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, self.header_text, new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(2)
    
    def footer(self):
        """Add footer to each page."""
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(100, 100, 100)
        
        if self.include_page_numbers:
            self.cell(0, 10, f"Page {self.page_no()}", align="C")


class PDFExporter(BaseExporter):
    """Exports transcripts to PDF format."""
    
    @property
    def format_name(self) -> str:
        return "PDF Document"
    
    @property
    def file_extension(self) -> str:
        return ".pdf"
    
    def export(
        self,
        transcript: Transcript,
        output_path: str,
        audio_file: Optional[str] = None,
        include_timestamps: bool = True,
        include_line_numbers: bool = True,
        include_gaps: bool = True,
        include_header: bool = True,
        include_page_numbers: bool = True,
        font_size: int = 11,
        certification_text: str = "",
        metadata = None,
        **options
    ) -> None:
        """Export transcript to PDF.
        
        Args:
            transcript: Transcript to export
            output_path: Path for output PDF
            audio_file: Source audio filename (for header)
            include_timestamps: Include timestamp for each segment
            include_line_numbers: Include line numbers
            include_gaps: Show gap indicators between segments
            include_header: Include document header
            include_page_numbers: Include page numbers
            font_size: Base font size
            certification_text: Optional legal certification text
            metadata: Optional RecordingMetadata for header
        """
        output_path = self.validate_output_path(output_path)
        self.ensure_output_directory(output_path)
        
        # Create PDF
        pdf = TranscriptPDF()
        pdf.include_page_numbers = include_page_numbers
        pdf.set_auto_page_break(auto=True, margin=20)
        
        # Set header text
        if include_header and audio_file:
            pdf.header_text = os.path.basename(audio_file)
        
        pdf.add_page()
        
        # Recording metadata section (if provided)
        if metadata and not metadata.is_empty():
            self._add_metadata_section(pdf, metadata)
            pdf.ln(5)
        
        # Document title
        if include_header:
            pdf.set_font("Helvetica", "B", 16)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(0, 10, "Transcript", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.ln(5)
            
            # Basic metadata (if no full metadata provided)
            if not metadata or metadata.is_empty():
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(80, 80, 80)
                
                if audio_file:
                    pdf.cell(0, 6, f"Source: {os.path.basename(audio_file)}", new_x="LMARGIN", new_y="NEXT")
                
                pdf.cell(0, 6, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", new_x="LMARGIN", new_y="NEXT")
                
                duration_str = format_timestamp(transcript.audio_duration)
                pdf.cell(0, 6, f"Duration: {duration_str}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, f"Segments: {transcript.segment_count} | Words: {transcript.word_count}", new_x="LMARGIN", new_y="NEXT")
            
            pdf.ln(10)
        
        # SRT-like format: cleaner, no table alignment issues
        # Format:
        #   1. 00:00:01 - 00:00:07
        #   Text content here...
        #   (blank line)
        
        pdf.set_font("Helvetica", "", font_size)
        pdf.set_text_color(0, 0, 0)
        
        # Gap threshold for display
        gap_threshold = 2.0  # Show gaps >= 2 seconds
        page_width = pdf.w - 20  # Available width
        line_height = 5  # Line height for text
        
        for i, segment in enumerate(transcript.segments):
            # Calculate gap before this segment
            gap_before = 0.0
            if i == 0:
                gap_before = segment.start_time
            else:
                prev_segment = transcript.segments[i - 1]
                gap_before = segment.start_time - prev_segment.end_time
            
            # Show gap indicator before segment if significant
            if include_gaps and gap_before >= gap_threshold:
                if pdf.get_y() > pdf.h - 40:
                    pdf.add_page()
                
                pdf.set_font("Helvetica", "BI", font_size - 1)
                pdf.set_text_color(70, 130, 180)   # Steel blue text
                
                if gap_before >= 60:
                    mins = int(gap_before // 60)
                    secs = int(gap_before % 60)
                    gap_text = f"[ PAUSE: {mins}m {secs}s - Other party speaking / Silence ]"
                else:
                    gap_text = f"[ PAUSE: {gap_before:.0f} seconds - Other party speaking / Silence ]"
                
                pdf.cell(page_width, 8, gap_text, align="C")
                pdf.ln(10)
                
                pdf.set_text_color(0, 0, 0)
            
            # Check if we need a new page (need room for header + some text)
            if pdf.get_y() > pdf.h - 35:
                pdf.add_page()
            
            # Segment header: line number and timestamp
            header_parts = []
            if include_line_numbers:
                header_parts.append(f"{i + 1}.")
            if include_timestamps:
                time_str = format_timestamp_range(segment.start_time, segment.end_time)
                header_parts.append(time_str)
            
            if header_parts:
                pdf.set_font("Courier", "B", font_size - 1)
                pdf.set_text_color(80, 80, 80)
                header_text = "  ".join(header_parts)
                pdf.cell(page_width, 6, header_text)
                pdf.ln()
            
            # Segment text
            pdf.set_font("Helvetica", "", font_size)
            pdf.set_text_color(0, 0, 0)
            
            text = segment.display_text
            pdf.multi_cell(page_width, line_height, text)
            
            # Add spacing between segments
            pdf.ln(3)
        
        # Certification text
        if certification_text:
            pdf.ln(15)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 8, "Certification", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, certification_text)
            
            # Signature line
            pdf.ln(15)
            pdf.cell(80, 0, "_" * 40, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(80, 8, "Signature", new_x="LMARGIN", new_y="NEXT")
            
            pdf.cell(80, 0, "_" * 40, new_x="LMARGIN", new_y="NEXT")
            pdf.cell(80, 8, "Date", new_x="LMARGIN", new_y="NEXT")
        
        # Save PDF
        pdf.output(output_path)
    
    def _calculate_column_widths(
        self,
        available_width: float,
        include_line_numbers: bool,
        include_timestamps: bool
    ) -> dict:
        """Calculate column widths based on options."""
        widths = {}
        
        # Fixed widths
        if include_line_numbers:
            widths["line"] = 15
            available_width -= 15
        
        if include_timestamps:
            widths["time"] = 55
            available_width -= 55
        
        # Remaining width for text
        widths["text"] = available_width
        
        return widths
    
    def _add_metadata_section(self, pdf: TranscriptPDF, metadata) -> None:
        """Add recording metadata section to PDF.
        
        Args:
            pdf: PDF document
            metadata: RecordingMetadata object
        """
        # Title
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "RECORDING INFORMATION", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(3)
        
        # Draw a box around metadata
        pdf.set_draw_color(150, 150, 150)
        start_y = pdf.get_y()
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(60, 60, 60)
        
        # Case information
        if metadata.case_name or metadata.case_number:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Case/Matter:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            
            if metadata.case_name:
                pdf.cell(0, 5, f"    {metadata.case_name}", new_x="LMARGIN", new_y="NEXT")
            if metadata.case_number:
                pdf.cell(0, 5, f"    Case No: {metadata.case_number}", new_x="LMARGIN", new_y="NEXT")
            if metadata.client_name:
                pdf.cell(0, 5, f"    Client: {metadata.client_name}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        
        # Recording details
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Recording Details:", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        
        if metadata.recording_date:
            date_str = metadata.recording_date
            if metadata.recording_time:
                date_str += f" at {metadata.recording_time}"
            pdf.cell(0, 5, f"    Date/Time: {date_str}", new_x="LMARGIN", new_y="NEXT")
        
        if metadata.recording_location:
            pdf.cell(0, 5, f"    Location: {metadata.recording_location}", new_x="LMARGIN", new_y="NEXT")
        
        if metadata.recording_source:
            pdf.cell(0, 5, f"    Source: {metadata.recording_source}", new_x="LMARGIN", new_y="NEXT")
        
        if metadata.original_filename:
            pdf.cell(0, 5, f"    File: {metadata.original_filename}", new_x="LMARGIN", new_y="NEXT")
        
        if metadata.audio_duration:
            pdf.cell(0, 5, f"    Duration: {metadata.format_duration()}", new_x="LMARGIN", new_y="NEXT")
        
        pdf.ln(2)
        
        # Participants
        if metadata.participants:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Participants:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            
            for i, participant in enumerate(metadata.participants, 1):
                pdf.cell(0, 5, f"    {i}. {participant}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        
        # Transcription info
        if metadata.transcriptionist or metadata.transcription_date:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Transcription:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            
            if metadata.transcriptionist:
                pdf.cell(0, 5, f"    Transcribed by: {metadata.transcriptionist}", new_x="LMARGIN", new_y="NEXT")
            if metadata.transcription_date:
                pdf.cell(0, 5, f"    Date: {metadata.transcription_date}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        
        # Notes
        if metadata.notes:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Notes:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "I", 9)
            pdf.multi_cell(0, 5, f"    {metadata.notes}")
            pdf.ln(2)
        
        # Draw border around metadata section
        end_y = pdf.get_y()
        pdf.set_draw_color(200, 200, 200)
        pdf.rect(10, start_y - 2, 190, end_y - start_y + 4)
        
        pdf.ln(5)