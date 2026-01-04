"""
Metadata dialog for PersonalTranscribe.
Edit recording and transcription metadata for legal/archival purposes.
"""

from typing import Optional
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QTextEdit, QPushButton, QDialogButtonBox,
    QDateEdit, QTimeEdit, QListWidget, QLabel, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt, QDate, QTime

from src.models.metadata import RecordingMetadata


class MetadataDialog(QDialog):
    """Dialog for editing recording metadata."""
    
    def __init__(self, metadata: Optional[RecordingMetadata] = None, parent=None):
        super().__init__(parent)
        
        self.metadata = metadata or RecordingMetadata()
        
        self.setWindowTitle("Recording Metadata")
        self.setMinimumSize(500, 600)
        self.setModal(True)
        
        self._init_ui()
        self._load_metadata()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Create scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # Case/Matter Information
        case_group = QGroupBox("Case/Matter Information")
        case_layout = QFormLayout(case_group)
        
        self.case_name_edit = QLineEdit()
        self.case_name_edit.setPlaceholderText("e.g., Smith v. Jones")
        case_layout.addRow("Case/Matter Name:", self.case_name_edit)
        
        self.case_number_edit = QLineEdit()
        self.case_number_edit.setPlaceholderText("e.g., 2026-CV-12345")
        case_layout.addRow("Case Number:", self.case_number_edit)
        
        self.client_name_edit = QLineEdit()
        case_layout.addRow("Client Name:", self.client_name_edit)
        
        content_layout.addWidget(case_group)
        
        # Recording Information
        recording_group = QGroupBox("Recording Details")
        recording_layout = QFormLayout(recording_group)
        
        # Date/Time row
        datetime_layout = QHBoxLayout()
        self.recording_date_edit = QDateEdit()
        self.recording_date_edit.setCalendarPopup(True)
        self.recording_date_edit.setDisplayFormat("yyyy-MM-dd")
        datetime_layout.addWidget(self.recording_date_edit)
        
        datetime_layout.addWidget(QLabel("at"))
        
        self.recording_time_edit = QTimeEdit()
        self.recording_time_edit.setDisplayFormat("HH:mm")
        datetime_layout.addWidget(self.recording_time_edit)
        
        datetime_layout.addStretch()
        recording_layout.addRow("Recording Date/Time:", datetime_layout)
        
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("e.g., Conference Room A, 123 Main St")
        recording_layout.addRow("Location:", self.location_edit)
        
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("e.g., iPhone voice memo, Zoom recording")
        recording_layout.addRow("Recording Source:", self.source_edit)
        
        content_layout.addWidget(recording_group)
        
        # Participants
        participants_group = QGroupBox("Participants")
        participants_layout = QVBoxLayout(participants_group)
        
        self.participants_list = QListWidget()
        self.participants_list.setMaximumHeight(100)
        participants_layout.addWidget(self.participants_list)
        
        # Add/Remove buttons
        participant_btn_layout = QHBoxLayout()
        
        self.new_participant_edit = QLineEdit()
        self.new_participant_edit.setPlaceholderText("Enter participant name...")
        self.new_participant_edit.returnPressed.connect(self._add_participant)
        participant_btn_layout.addWidget(self.new_participant_edit, 1)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_participant)
        participant_btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_participant)
        participant_btn_layout.addWidget(remove_btn)
        
        participants_layout.addLayout(participant_btn_layout)
        
        content_layout.addWidget(participants_group)
        
        # Transcription Information
        transcription_group = QGroupBox("Transcription")
        transcription_layout = QFormLayout(transcription_group)
        
        self.transcriptionist_edit = QLineEdit()
        self.transcriptionist_edit.setPlaceholderText("Name of person who transcribed")
        transcription_layout.addRow("Transcribed by:", self.transcriptionist_edit)
        
        self.transcription_date_edit = QDateEdit()
        self.transcription_date_edit.setCalendarPopup(True)
        self.transcription_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.transcription_date_edit.setDate(QDate.currentDate())
        transcription_layout.addRow("Transcription Date:", self.transcription_date_edit)
        
        content_layout.addWidget(transcription_group)
        
        # Notes
        notes_group = QGroupBox("Additional Notes")
        notes_layout = QVBoxLayout(notes_group)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText(
            "Any additional notes about the recording or transcription...\n"
            "e.g., 'Recording quality was poor in sections', "
            "'Some portions inaudible due to background noise'"
        )
        self.notes_edit.setMaximumHeight(100)
        notes_layout.addWidget(self.notes_edit)
        
        content_layout.addWidget(notes_group)
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_metadata(self):
        """Load metadata into the form fields."""
        m = self.metadata
        
        # Case info
        if m.case_name:
            self.case_name_edit.setText(m.case_name)
        if m.case_number:
            self.case_number_edit.setText(m.case_number)
        if m.client_name:
            self.client_name_edit.setText(m.client_name)
        
        # Recording info
        if m.recording_date:
            try:
                date = QDate.fromString(m.recording_date, "yyyy-MM-dd")
                if date.isValid():
                    self.recording_date_edit.setDate(date)
            except:
                pass
        else:
            self.recording_date_edit.setDate(QDate.currentDate())
        
        if m.recording_time:
            try:
                time = QTime.fromString(m.recording_time, "HH:mm")
                if time.isValid():
                    self.recording_time_edit.setTime(time)
            except:
                pass
        
        if m.recording_location:
            self.location_edit.setText(m.recording_location)
        if m.recording_source:
            self.source_edit.setText(m.recording_source)
        
        # Participants
        for participant in m.participants:
            self.participants_list.addItem(participant)
        
        # Transcription
        if m.transcriptionist:
            self.transcriptionist_edit.setText(m.transcriptionist)
        if m.transcription_date:
            try:
                date = QDate.fromString(m.transcription_date, "yyyy-MM-dd")
                if date.isValid():
                    self.transcription_date_edit.setDate(date)
            except:
                pass
        
        # Notes
        if m.notes:
            self.notes_edit.setPlainText(m.notes)
    
    def _add_participant(self):
        """Add a participant to the list."""
        name = self.new_participant_edit.text().strip()
        if name:
            self.participants_list.addItem(name)
            self.new_participant_edit.clear()
    
    def _remove_participant(self):
        """Remove the selected participant."""
        current = self.participants_list.currentRow()
        if current >= 0:
            self.participants_list.takeItem(current)
    
    def _save_and_accept(self):
        """Save metadata and close dialog."""
        # Case info
        self.metadata.case_name = self.case_name_edit.text().strip() or None
        self.metadata.case_number = self.case_number_edit.text().strip() or None
        self.metadata.client_name = self.client_name_edit.text().strip() or None
        
        # Recording info
        self.metadata.recording_date = self.recording_date_edit.date().toString("yyyy-MM-dd")
        self.metadata.recording_time = self.recording_time_edit.time().toString("HH:mm")
        self.metadata.recording_location = self.location_edit.text().strip() or None
        self.metadata.recording_source = self.source_edit.text().strip() or None
        
        # Participants
        self.metadata.participants = [
            self.participants_list.item(i).text()
            for i in range(self.participants_list.count())
        ]
        
        # Transcription
        self.metadata.transcriptionist = self.transcriptionist_edit.text().strip() or None
        self.metadata.transcription_date = self.transcription_date_edit.date().toString("yyyy-MM-dd")
        
        # Notes
        self.metadata.notes = self.notes_edit.toPlainText().strip() or None
        
        self.accept()
    
    def get_metadata(self) -> RecordingMetadata:
        """Get the edited metadata."""
        return self.metadata
