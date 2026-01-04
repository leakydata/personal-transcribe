"""
Find and Replace dialog for PersonalTranscribe.
Provides search and replace functionality for transcript text.
"""

from typing import Optional, List, Tuple
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox, QGroupBox,
    QMessageBox, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal

from src.models.transcript import Transcript, Segment


@dataclass
class SearchResult:
    """Represents a search result."""
    segment_index: int
    segment: Segment
    position: int  # Character position in text
    length: int    # Length of match


class FindReplaceDialog(QDialog):
    """Find and Replace dialog."""
    
    # Signals
    jump_to_segment = pyqtSignal(object)  # Segment
    text_replaced = pyqtSignal()  # Emitted when replacement made
    
    def __init__(self, transcript: Transcript, parent=None):
        super().__init__(parent)
        
        self.transcript = transcript
        self.search_results: List[SearchResult] = []
        self.current_result_index: int = -1
        
        self.setWindowTitle("Find and Replace")
        self.setMinimumWidth(450)
        self.setModal(False)  # Non-modal so user can edit while open
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Find section
        find_group = QGroupBox("Find")
        find_layout = QGridLayout(find_group)
        
        find_label = QLabel("Find:")
        find_layout.addWidget(find_label, 0, 0)
        
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Enter text to find...")
        self.find_input.textChanged.connect(self._on_find_text_changed)
        self.find_input.returnPressed.connect(self.find_next)
        find_layout.addWidget(self.find_input, 0, 1)
        
        # Options
        self.case_sensitive_cb = QCheckBox("Case sensitive")
        self.case_sensitive_cb.stateChanged.connect(self._on_options_changed)
        find_layout.addWidget(self.case_sensitive_cb, 1, 1)
        
        self.whole_word_cb = QCheckBox("Whole word only")
        self.whole_word_cb.stateChanged.connect(self._on_options_changed)
        find_layout.addWidget(self.whole_word_cb, 2, 1)
        
        layout.addWidget(find_group)
        
        # Replace section
        replace_group = QGroupBox("Replace")
        replace_layout = QGridLayout(replace_group)
        
        replace_label = QLabel("Replace with:")
        replace_layout.addWidget(replace_label, 0, 0)
        
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Enter replacement text...")
        replace_layout.addWidget(self.replace_input, 0, 1)
        
        layout.addWidget(replace_group)
        
        # Results info
        self.results_label = QLabel("Enter text to search")
        layout.addWidget(self.results_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.find_next_btn = QPushButton("Find Next")
        self.find_next_btn.clicked.connect(self.find_next)
        self.find_next_btn.setEnabled(False)
        button_layout.addWidget(self.find_next_btn)
        
        self.find_prev_btn = QPushButton("Find Previous")
        self.find_prev_btn.clicked.connect(self.find_previous)
        self.find_prev_btn.setEnabled(False)
        button_layout.addWidget(self.find_prev_btn)
        
        button_layout.addStretch()
        
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self.replace_current)
        self.replace_btn.setEnabled(False)
        button_layout.addWidget(self.replace_btn)
        
        self.replace_all_btn = QPushButton("Replace All")
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.replace_all_btn.setEnabled(False)
        button_layout.addWidget(self.replace_all_btn)
        
        layout.addLayout(button_layout)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
    
    def _on_find_text_changed(self, text: str):
        """Handle find text change."""
        if text:
            self._perform_search()
        else:
            self.search_results = []
            self.current_result_index = -1
            self._update_ui()
    
    def _on_options_changed(self):
        """Handle search options change."""
        if self.find_input.text():
            self._perform_search()
    
    def _perform_search(self):
        """Perform the search."""
        search_text = self.find_input.text()
        if not search_text:
            return
        
        case_sensitive = self.case_sensitive_cb.isChecked()
        whole_word = self.whole_word_cb.isChecked()
        
        self.search_results = []
        
        for i, segment in enumerate(self.transcript.segments):
            text = segment.text
            search_in = text if case_sensitive else text.lower()
            find_text = search_text if case_sensitive else search_text.lower()
            
            # Find all occurrences
            pos = 0
            while True:
                pos = search_in.find(find_text, pos)
                if pos == -1:
                    break
                
                # Check whole word if required
                if whole_word:
                    # Check character before
                    if pos > 0 and search_in[pos - 1].isalnum():
                        pos += 1
                        continue
                    # Check character after
                    end_pos = pos + len(find_text)
                    if end_pos < len(search_in) and search_in[end_pos].isalnum():
                        pos += 1
                        continue
                
                self.search_results.append(SearchResult(
                    segment_index=i,
                    segment=segment,
                    position=pos,
                    length=len(search_text)
                ))
                pos += 1
        
        self.current_result_index = 0 if self.search_results else -1
        self._update_ui()
        
        # Jump to first result
        if self.search_results:
            self._jump_to_current()
    
    def _update_ui(self):
        """Update UI based on search results."""
        has_results = len(self.search_results) > 0
        
        self.find_next_btn.setEnabled(has_results)
        self.find_prev_btn.setEnabled(has_results)
        self.replace_btn.setEnabled(has_results)
        self.replace_all_btn.setEnabled(has_results)
        
        if not self.find_input.text():
            self.results_label.setText("Enter text to search")
        elif has_results:
            current = self.current_result_index + 1
            total = len(self.search_results)
            self.results_label.setText(f"Result {current} of {total}")
        else:
            self.results_label.setText("No matches found")
    
    def _jump_to_current(self):
        """Jump to current search result."""
        if 0 <= self.current_result_index < len(self.search_results):
            result = self.search_results[self.current_result_index]
            self.jump_to_segment.emit(result.segment)
    
    def find_next(self):
        """Find next occurrence."""
        if not self.search_results:
            return
        
        self.current_result_index = (self.current_result_index + 1) % len(self.search_results)
        self._update_ui()
        self._jump_to_current()
    
    def find_previous(self):
        """Find previous occurrence."""
        if not self.search_results:
            return
        
        self.current_result_index = (self.current_result_index - 1) % len(self.search_results)
        self._update_ui()
        self._jump_to_current()
    
    def replace_current(self):
        """Replace current occurrence."""
        if not self.search_results or self.current_result_index < 0:
            return
        
        result = self.search_results[self.current_result_index]
        segment = result.segment
        
        # Perform replacement
        old_text = segment.text
        new_text = (
            old_text[:result.position] +
            self.replace_input.text() +
            old_text[result.position + result.length:]
        )
        segment.update_text(new_text)
        
        self.text_replaced.emit()
        
        # Re-search to update results
        self._perform_search()
    
    def replace_all(self):
        """Replace all occurrences."""
        if not self.search_results:
            return
        
        search_text = self.find_input.text()
        replace_text = self.replace_input.text()
        case_sensitive = self.case_sensitive_cb.isChecked()
        
        count = 0
        
        # Process each segment
        for segment in self.transcript.segments:
            old_text = segment.text
            
            if case_sensitive:
                new_text = old_text.replace(search_text, replace_text)
            else:
                # Case-insensitive replace
                import re
                pattern = re.compile(re.escape(search_text), re.IGNORECASE)
                new_text = pattern.sub(replace_text, old_text)
            
            if new_text != old_text:
                count += old_text.count(search_text) if case_sensitive else len(
                    re.findall(re.escape(search_text), old_text, re.IGNORECASE)
                )
                segment.update_text(new_text)
        
        self.text_replaced.emit()
        
        # Clear results
        self.search_results = []
        self.current_result_index = -1
        self._update_ui()
        
        QMessageBox.information(
            self,
            "Replace All",
            f"Replaced {count} occurrence{'s' if count != 1 else ''}."
        )
    
    def set_transcript(self, transcript: Transcript):
        """Update the transcript reference."""
        self.transcript = transcript
        self.search_results = []
        self.current_result_index = -1
        self._update_ui()
        
        # Re-search if there's text
        if self.find_input.text():
            self._perform_search()
