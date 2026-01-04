"""
Vocabulary manager dialog for PersonalTranscribe.
Allows users to manage custom words for improved transcription accuracy.
"""

from typing import List
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import Qt


class VocabularyDialog(QDialog):
    """Dialog for managing custom vocabulary."""
    
    def __init__(self, vocabulary: List[str], parent=None):
        super().__init__(parent)
        
        self.vocabulary = vocabulary.copy()
        
        self.setWindowTitle("Vocabulary Manager")
        self.setMinimumSize(400, 500)
        self.setModal(True)
        
        self._init_ui()
        self._load_vocabulary()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Add custom words, names, or phrases to improve transcription accuracy.\n"
            "These words will be used to guide the speech recognition."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Word list
        list_group = QGroupBox("Custom Words")
        list_layout = QVBoxLayout(list_group)
        
        self.word_list = QListWidget()
        self.word_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        list_layout.addWidget(self.word_list)
        
        # Add word controls
        add_layout = QHBoxLayout()
        
        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("Enter a word or phrase...")
        self.word_input.returnPressed.connect(self._add_word)
        add_layout.addWidget(self.word_input, 1)
        
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_word)
        add_layout.addWidget(add_button)
        
        list_layout.addLayout(add_layout)
        
        # List action buttons
        action_layout = QHBoxLayout()
        
        remove_button = QPushButton("Remove Selected")
        remove_button.clicked.connect(self._remove_selected)
        action_layout.addWidget(remove_button)
        
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self._clear_all)
        action_layout.addWidget(clear_button)
        
        action_layout.addStretch()
        
        list_layout.addLayout(action_layout)
        
        layout.addWidget(list_group)
        
        # Import/Export group
        io_group = QGroupBox("Import/Export")
        io_layout = QHBoxLayout(io_group)
        
        import_button = QPushButton("Import from File...")
        import_button.clicked.connect(self._import_file)
        io_layout.addWidget(import_button)
        
        export_button = QPushButton("Export to File...")
        export_button.clicked.connect(self._export_file)
        io_layout.addWidget(export_button)
        
        layout.addWidget(io_group)
        
        # Word count
        self.count_label = QLabel("0 words")
        layout.addWidget(self.count_label)
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_vocabulary(self):
        """Load vocabulary into list widget."""
        self.word_list.clear()
        for word in self.vocabulary:
            self.word_list.addItem(word)
        self._update_count()
    
    def _update_count(self):
        """Update word count label."""
        count = self.word_list.count()
        self.count_label.setText(f"{count} word{'s' if count != 1 else ''}")
    
    def _add_word(self):
        """Add a word to the vocabulary."""
        word = self.word_input.text().strip()
        if not word:
            return
        
        # Check for duplicates
        for i in range(self.word_list.count()):
            if self.word_list.item(i).text().lower() == word.lower():
                QMessageBox.warning(
                    self,
                    "Duplicate Word",
                    f"'{word}' is already in the vocabulary."
                )
                return
        
        self.word_list.addItem(word)
        self.word_input.clear()
        self._update_count()
    
    def _remove_selected(self):
        """Remove selected words."""
        selected = self.word_list.selectedItems()
        if not selected:
            return
        
        for item in selected:
            row = self.word_list.row(item)
            self.word_list.takeItem(row)
        
        self._update_count()
    
    def _clear_all(self):
        """Clear all words."""
        if self.word_list.count() == 0:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear All",
            "Are you sure you want to remove all words?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.word_list.clear()
            self._update_count()
    
    def _import_file(self):
        """Import vocabulary from a text file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Vocabulary",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            imported = 0
            existing_words = set(
                self.word_list.item(i).text().lower()
                for i in range(self.word_list.count())
            )
            
            for line in lines:
                word = line.strip()
                if word and not word.startswith("#") and word.lower() not in existing_words:
                    self.word_list.addItem(word)
                    existing_words.add(word.lower())
                    imported += 1
            
            self._update_count()
            QMessageBox.information(
                self,
                "Import Complete",
                f"Imported {imported} new word{'s' if imported != 1 else ''}."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import file:\n{e}"
            )
    
    def _export_file(self):
        """Export vocabulary to a text file."""
        if self.word_list.count() == 0:
            QMessageBox.warning(
                self,
                "Export",
                "No words to export."
            )
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Vocabulary",
            "vocabulary.txt",
            "Text Files (*.txt)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# PersonalTranscribe Custom Vocabulary\n")
                for i in range(self.word_list.count()):
                    f.write(f"{self.word_list.item(i).text()}\n")
            
            QMessageBox.information(
                self,
                "Export Complete",
                f"Exported {self.word_list.count()} words to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export file:\n{e}"
            )
    
    def get_vocabulary(self) -> List[str]:
        """Get the current vocabulary list."""
        words = []
        for i in range(self.word_list.count()):
            words.append(self.word_list.item(i).text())
        return words
