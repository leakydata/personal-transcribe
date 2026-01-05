"""
Batch Transcription Dialog for PersonalTranscribe.
Allows processing multiple files in sequence.
"""

import os
import time
from typing import List, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QPushButton, QProgressBar, 
    QFileDialog, QComboBox, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.ui.transcription_dialog import TranscriptionWorkerV2
from src.utils.logger import logger
from src.transcription.whisper_engine import get_available_models

class BatchDialog(QDialog):
    """Dialog for batch processing audio files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Transcription")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self.files: List[str] = []
        self.worker: Optional[TranscriptionWorkerV2] = None
        self.current_index: int = 0
        self.is_running: bool = False
        
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # File selection
        file_group = QGroupBox("Files to Transcribe")
        file_layout = QVBoxLayout(file_group)
        
        self.file_list = QListWidget()
        file_layout.addWidget(self.file_list)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Files...")
        add_btn.clicked.connect(self._add_files)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_file)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_files)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addWidget(clear_btn)
        file_layout.addLayout(btn_layout)
        
        layout.addWidget(file_group)
        
        # Settings
        settings_group = QGroupBox("Transcription Settings")
        settings_layout = QHBoxLayout(settings_group)
        
        settings_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(get_available_models())
        self.model_combo.setCurrentText("medium")  # Default to medium for batch
        settings_layout.addWidget(self.model_combo)
        
        settings_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto-detect", None)
        self.lang_combo.addItem("English", "en")
        # Add a few common ones
        common_langs = [("Spanish", "es"), ("French", "fr"), ("German", "de")]
        for name, code in common_langs:
            self.lang_combo.addItem(name, code)
        settings_layout.addWidget(self.lang_combo)
        
        settings_layout.addStretch()
        layout.addWidget(settings_group)
        
        # Progress
        self.progress_group = QGroupBox("Progress")
        self.progress_group.setVisible(False)
        prog_layout = QVBoxLayout(self.progress_group)
        
        self.current_file_label = QLabel("Waiting...")
        prog_layout.addWidget(self.current_file_label)
        
        self.file_progress = QProgressBar()
        self.file_progress.setRange(0, 100)
        prog_layout.addWidget(self.file_progress)
        
        self.total_progress = QProgressBar()
        self.total_progress.setFormat("Batch Progress: %p%")
        prog_layout.addWidget(self.total_progress)
        
        layout.addWidget(self.progress_group)
        
        # Main buttons
        main_btns = QHBoxLayout()
        self.start_btn = QPushButton("Start Batch")
        self.start_btn.clicked.connect(self._start_batch)
        self.start_btn.setEnabled(False)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        
        main_btns.addStretch()
        main_btns.addWidget(self.start_btn)
        main_btns.addWidget(self.close_btn)
        layout.addLayout(main_btns)
        
    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "", 
            "Audio Files (*.mp3 *.wav *.m4a *.mp4 *.flac *.ogg)"
        )
        if files:
            for f in files:
                if f not in self.files:
                    self.files.append(f)
                    self.file_list.addItem(os.path.basename(f))
            self.start_btn.setEnabled(bool(self.files))
            
    def _remove_file(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.files.pop(row)
            self.file_list.takeItem(row)
            self.start_btn.setEnabled(bool(self.files))
            
    def _clear_files(self):
        self.files.clear()
        self.file_list.clear()
        self.start_btn.setEnabled(False)
        
    def _start_batch(self):
        if not self.files:
            return
            
        self.is_running = True
        self.current_index = 0
        
        # Lock UI
        self.file_list.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.progress_group.setVisible(True)
        self.total_progress.setRange(0, len(self.files))
        self.total_progress.setValue(0)
        
        self._process_next()
        
    def _process_next(self):
        if self.current_index >= len(self.files):
            self._finish_batch()
            return
            
        file_path = self.files[self.current_index]
        base_name = os.path.basename(file_path)
        self.current_file_label.setText(f"Processing: {base_name}")
        self.file_progress.setValue(0)
        
        # Configure worker
        model_size = self.model_combo.currentText()
        language = self.lang_combo.currentData()
        
        self.worker = TranscriptionWorkerV2(
            audio_path=file_path,
            model_size=model_size,
            language=language,
            device="auto",
            compute_type="int8" # Conservative for batch
        )
        
        self.worker.progress.connect(self.file_progress.setValue)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        
        self.worker.start()
        
    def _on_worker_finished(self, transcript):
        """Handle successful transcription."""
        if not self.is_running:
            return
            
        file_path = self.files[self.current_index]
        
        # Save results
        try:
            # Save JSON
            json_path = os.path.splitext(file_path)[0] + "_transcript.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(transcript.to_json())
                
            # Auto-export text
            txt_path = os.path.splitext(file_path)[0] + ".txt"
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(transcript.get_full_text())
                
            logger.info(f"Batch saved: {json_path}")
            
        except Exception as e:
            logger.error(f"Error saving batch result: {e}")
            
        self.current_index += 1
        self.total_progress.setValue(self.current_index)
        
        # Schedule next
        QTimer.singleShot(1000, self._process_next)
        
    def _on_worker_error(self, error_msg):
        """Handle error, but allow continuing."""
        logger.error(f"Batch error on file {self.current_index}: {error_msg}")
        self.current_file_label.setText(f"Error: {error_msg}")
        
        # Create error log file
        try:
            file_path = self.files[self.current_index]
            err_path = os.path.splitext(file_path)[0] + "_error.txt"
            with open(err_path, 'w') as f:
                f.write(error_msg)
        except:
            pass
            
        # Continue to next
        self.current_index += 1
        self.total_progress.setValue(self.current_index)
        QTimer.singleShot(2000, self._process_next)
        
    def _finish_batch(self):
        self.is_running = False
        self.current_file_label.setText("Batch Complete!")
        self.file_progress.setValue(100)
        self.close_btn.setText("Close")
        self.start_btn.setEnabled(False)
        self.file_list.setEnabled(True)
        
        QMessageBox.information(
            self, "Batch Complete", 
            f"Processed {len(self.files)} files.\nTranscripts saved to source directories."
        )
        
    def closeEvent(self, event):
        if self.is_running:
            reply = QMessageBox.question(
                self, "Stop Batch?", 
                "Batch processing is running. Stop?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.is_running = False
                if self.worker:
                    self.worker.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
