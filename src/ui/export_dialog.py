"""
Export dialog for PersonalTranscribe.
Handles PDF and other export options.
"""

import os
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QDialogButtonBox, QComboBox, QSpinBox, QTextEdit
)
from PyQt6.QtCore import Qt

from src.models.transcript import Transcript
from src.models.metadata import RecordingMetadata
from src.export.pdf_exporter import PDFExporter
from src.export.docx_exporter import DOCXExporter
from src.export.srt_exporter import SRTExporter, VTTExporter


class ExportDialog(QDialog):
    """Dialog for export options."""
    
    def __init__(
        self,
        transcript: Transcript,
        audio_file: Optional[str] = None,
        metadata: Optional[RecordingMetadata] = None,
        parent=None
    ):
        super().__init__(parent)
        
        self.transcript = transcript
        self.audio_file = audio_file
        self.metadata = metadata or RecordingMetadata()
        
        self.setWindowTitle("Export Transcript")
        self.setMinimumSize(500, 450)
        self.setModal(True)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Format selection
        format_group = QGroupBox("Export Format")
        format_layout = QHBoxLayout(format_group)
        
        format_label = QLabel("Format:")
        format_layout.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "PDF", 
            "Word Document (.docx)", 
            "SRT Subtitles (.srt)",
            "WebVTT Subtitles (.vtt)",
            "Plain Text", 
            "Text with Timestamps"
        ])
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        format_layout.addWidget(self.format_combo)
        
        format_layout.addStretch()
        
        layout.addWidget(format_group)
        
        # PDF Options
        self.pdf_options_group = QGroupBox("PDF Options")
        pdf_layout = QVBoxLayout(self.pdf_options_group)
        
        self.include_timestamps_cb = QCheckBox("Include timestamps")
        self.include_timestamps_cb.setChecked(True)
        pdf_layout.addWidget(self.include_timestamps_cb)
        
        self.include_line_numbers_cb = QCheckBox("Include line numbers")
        self.include_line_numbers_cb.setChecked(True)
        pdf_layout.addWidget(self.include_line_numbers_cb)
        
        self.include_gaps_cb = QCheckBox("Show gap indicators")
        self.include_gaps_cb.setChecked(True)
        pdf_layout.addWidget(self.include_gaps_cb)
        
        self.include_header_cb = QCheckBox("Include header (filename, date, duration)")
        self.include_header_cb.setChecked(True)
        pdf_layout.addWidget(self.include_header_cb)
        
        self.include_page_numbers_cb = QCheckBox("Include page numbers")
        self.include_page_numbers_cb.setChecked(True)
        pdf_layout.addWidget(self.include_page_numbers_cb)
        
        self.include_metadata_cb = QCheckBox("Include recording metadata header")
        self.include_metadata_cb.setChecked(True)
        self.include_metadata_cb.setToolTip(
            "Include case info, participants, recording details at the top"
        )
        pdf_layout.addWidget(self.include_metadata_cb)
        
        # Font size
        font_layout = QHBoxLayout()
        font_label = QLabel("Font size:")
        font_layout.addWidget(font_label)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 16)
        self.font_size_spin.setValue(11)
        font_layout.addWidget(self.font_size_spin)
        font_layout.addStretch()
        pdf_layout.addLayout(font_layout)
        
        # Certification text
        cert_layout = QVBoxLayout()
        cert_label = QLabel("Certification text (optional, for legal use):")
        cert_layout.addWidget(cert_label)
        
        self.certification_text = QTextEdit()
        self.certification_text.setPlaceholderText(
            "e.g., 'I certify that this transcript is a true and accurate "
            "representation of the audio recording.'"
        )
        self.certification_text.setMaximumHeight(80)
        cert_layout.addWidget(self.certification_text)
        pdf_layout.addLayout(cert_layout)
        
        layout.addWidget(self.pdf_options_group)
        
        # Output file
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output file...")
        output_layout.addWidget(self.output_path, 1)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_button)
        
        layout.addWidget(output_group)
        
        # Preview info
        info_group = QGroupBox("Transcript Info")
        info_layout = QVBoxLayout(info_group)
        
        from src.models.transcript import format_timestamp
        duration_str = format_timestamp(self.transcript.audio_duration)
        
        info_text = (
            f"Segments: {self.transcript.segment_count}\n"
            f"Words: {self.transcript.word_count}\n"
            f"Duration: {duration_str}\n"
            f"Gaps: {len(self.transcript.get_gaps())}"
        )
        info_label = QLabel(info_text)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._do_export)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Set default output path
        if self.audio_file:
            base_name = os.path.splitext(self.audio_file)[0]
            self.output_path.setText(f"{base_name}_transcript.pdf")
            self.export_button.setEnabled(True)
    
    def _on_format_changed(self, format_text: str):
        """Handle format selection change."""
        is_pdf = format_text == "PDF"
        is_docx = format_text == "Word Document (.docx)"
        is_srt = format_text == "SRT Subtitles (.srt)"
        is_vtt = format_text == "WebVTT Subtitles (.vtt)"
        
        # Enable options for PDF and DOCX
        self.pdf_options_group.setEnabled(is_pdf or is_docx)
        
        # Update file extension
        current_path = self.output_path.text()
        if current_path:
            base = os.path.splitext(current_path)[0]
            if is_pdf:
                self.output_path.setText(f"{base}.pdf")
            elif is_docx:
                self.output_path.setText(f"{base}.docx")
            elif is_srt:
                self.output_path.setText(f"{base}.srt")
            elif is_vtt:
                self.output_path.setText(f"{base}.vtt")
            else:
                self.output_path.setText(f"{base}.txt")
    
    def _browse_output(self):
        """Browse for output file."""
        format_text = self.format_combo.currentText()
        
        if format_text == "PDF":
            filter_str = "PDF Files (*.pdf)"
            default_ext = ".pdf"
        elif format_text == "Word Document (.docx)":
            filter_str = "Word Documents (*.docx)"
            default_ext = ".docx"
        elif format_text == "SRT Subtitles (.srt)":
            filter_str = "SRT Subtitle Files (*.srt)"
            default_ext = ".srt"
        elif format_text == "WebVTT Subtitles (.vtt)":
            filter_str = "WebVTT Subtitle Files (*.vtt)"
            default_ext = ".vtt"
        else:
            filter_str = "Text Files (*.txt)"
            default_ext = ".txt"
        
        # Get default filename
        default_name = ""
        if self.audio_file:
            base_name = os.path.splitext(os.path.basename(self.audio_file))[0]
            default_name = f"{base_name}_transcript{default_ext}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Transcript",
            default_name,
            filter_str
        )
        
        if file_path:
            self.output_path.setText(file_path)
            self.export_button.setEnabled(True)
    
    def _do_export(self):
        """Perform the export."""
        output_path = self.output_path.text()
        if not output_path:
            QMessageBox.warning(self, "Export", "Please select an output file.")
            return
        
        format_text = self.format_combo.currentText()
        
        try:
            if format_text == "PDF":
                self._export_pdf(output_path)
            elif format_text == "Word Document (.docx)":
                self._export_docx(output_path)
            elif format_text == "SRT Subtitles (.srt)":
                self._export_srt(output_path)
            elif format_text == "WebVTT Subtitles (.vtt)":
                self._export_vtt(output_path)
            elif format_text == "Plain Text":
                self._export_text(output_path, include_timestamps=False)
            else:  # Text with Timestamps
                self._export_text(output_path, include_timestamps=True)
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Transcript exported to:\n{output_path}"
            )
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export transcript:\n{e}"
            )
    
    def _export_pdf(self, output_path: str):
        """Export to PDF."""
        exporter = PDFExporter()
        
        exporter.export(
            transcript=self.transcript,
            output_path=output_path,
            audio_file=self.audio_file,
            include_timestamps=self.include_timestamps_cb.isChecked(),
            include_line_numbers=self.include_line_numbers_cb.isChecked(),
            include_gaps=self.include_gaps_cb.isChecked(),
            include_header=self.include_header_cb.isChecked(),
            include_page_numbers=self.include_page_numbers_cb.isChecked(),
            font_size=self.font_size_spin.value(),
            certification_text=self.certification_text.toPlainText().strip(),
            metadata=self.metadata if self.include_metadata_cb.isChecked() else None
        )
    
    def _export_docx(self, output_path: str):
        """Export to Word document."""
        exporter = DOCXExporter()
        
        exporter.export(
            transcript=self.transcript,
            output_path=output_path,
            audio_file=self.audio_file,
            include_timestamps=self.include_timestamps_cb.isChecked(),
            include_line_numbers=self.include_line_numbers_cb.isChecked(),
            include_gaps=self.include_gaps_cb.isChecked(),
            include_header=self.include_header_cb.isChecked(),
            font_size=self.font_size_spin.value(),
            certification_text=self.certification_text.toPlainText().strip(),
            metadata=self.metadata if self.include_metadata_cb.isChecked() else None
        )
    
    def _export_srt(self, output_path: str):
        """Export to SRT subtitle format."""
        exporter = SRTExporter()
        exporter.export(
            transcript=self.transcript,
            output_path=output_path
        )
    
    def _export_vtt(self, output_path: str):
        """Export to WebVTT subtitle format."""
        exporter = VTTExporter()
        exporter.export(
            transcript=self.transcript,
            output_path=output_path
        )
    
    def _export_text(self, output_path: str, include_timestamps: bool):
        """Export to plain text."""
        text = self.transcript.get_full_text(include_timestamps=include_timestamps)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
