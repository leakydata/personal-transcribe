"""
Speaker Editor Dialog for PersonalTranscribe.
Allows bulk renaming of speakers in the transcript.
"""

from typing import Dict, List, Set
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QPushButton, 
    QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt

from src.models.transcript import Transcript

class SpeakerEditor(QDialog):
    """Dialog to edit speaker labels."""
    
    def __init__(self, transcript: Transcript, parent=None):
        super().__init__(parent)
        self.transcript = transcript
        self.setWindowTitle("Edit Speakers")
        self.setMinimumSize(400, 300)
        self.setModal(True)
        
        # Track original speakers to identify changes
        self.speakers: Set[str] = set()
        self._extract_speakers()
        
        self._init_ui()
        
    def _extract_speakers(self):
        """Find all unique speaker labels in transcript."""
        self.speakers = set()
        for segment in self.transcript.segments:
            if segment.speaker_label:
                self.speakers.add(segment.speaker_label)
        
        # If no speakers found, add a generic one so user can start labeling
        if not self.speakers:
            self.speakers.add("Speaker 1")
            
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Rename speakers below. Changes will apply to all segments with that speaker."))
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Original Name", "New Name"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        self._populate_table()
        
        # Buttons
        btn_layout = QHBoxLayout()
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(self._apply_changes)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def _populate_table(self):
        """Fill table with speakers."""
        sorted_speakers = sorted(list(self.speakers))
        self.table.setRowCount(len(sorted_speakers))
        
        for i, speaker in enumerate(sorted_speakers):
            # Original (Read-only)
            item_orig = QTableWidgetItem(speaker)
            item_orig.setFlags(item_orig.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item_orig)
            
            # New (Editable)
            item_new = QTableWidgetItem(speaker)
            self.table.setItem(i, 1, item_new)
            
    def _apply_changes(self):
        """Apply speaker renames to transcript."""
        changes_map = {}
        
        for i in range(self.table.rowCount()):
            original = self.table.item(i, 0).text()
            new_name = self.table.item(i, 1).text().strip()
            
            if original != new_name and new_name:
                changes_map[original] = new_name
        
        if not changes_map:
            self.accept()
            return
            
        count = 0
        for segment in self.transcript.segments:
            # Handle case where segment matches original map
            if segment.speaker_label in changes_map:
                segment.speaker_label = changes_map[segment.speaker_label]
                count += 1
            # Handle empty speakers if mapped
            elif not segment.speaker_label and "Speaker 1" in changes_map and len(self.speakers) == 1:
                 # Special case: initial population of empty speakers
                 segment.speaker_label = changes_map["Speaker 1"]
                 count += 1
                 
        QMessageBox.information(
            self, 
            "Speakers Updated", 
            f"Updated {count} segments with new speaker labels."
        )
        self.accept()
