"""
AI Polish dialog for PersonalTranscribe.
Shows polishing progress and allows reviewing changes.
"""

from typing import Optional, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QCheckBox, QMessageBox, QAbstractItemView,
    QTextEdit, QSplitter, QFormLayout, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

from src.models.transcript import Transcript, Segment
from src.ai.provider_base import PolishResult
from src.ai.ai_manager import get_ai_manager
from src.utils.logger import get_logger

logger = get_logger("ui.ai_polish")


class TimeRangeDialog(QDialog):
    """Dialog for selecting a time range."""
    
    def __init__(self, audio_duration: float = 0.0, parent=None):
        super().__init__(parent)
        self.audio_duration = audio_duration
        
        self.setWindowTitle("Select Time Range")
        self.setMinimumWidth(350)
        self.setModal(True)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(
            "Select the time range of segments to polish.\n"
            "Format: minutes and seconds"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Form layout for times
        form_group = QGroupBox("Time Range")
        form_layout = QFormLayout(form_group)
        
        # Start time
        start_layout = QHBoxLayout()
        self.start_min_spin = QSpinBox()
        self.start_min_spin.setRange(0, 999)
        self.start_min_spin.setSuffix(" min")
        start_layout.addWidget(self.start_min_spin)
        
        self.start_sec_spin = QSpinBox()
        self.start_sec_spin.setRange(0, 59)
        self.start_sec_spin.setSuffix(" sec")
        start_layout.addWidget(self.start_sec_spin)
        form_layout.addRow("Start:", start_layout)
        
        # End time
        end_layout = QHBoxLayout()
        self.end_min_spin = QSpinBox()
        self.end_min_spin.setRange(0, 999)
        self.end_min_spin.setSuffix(" min")
        end_layout.addWidget(self.end_min_spin)
        
        self.end_sec_spin = QSpinBox()
        self.end_sec_spin.setRange(0, 59)
        self.end_sec_spin.setSuffix(" sec")
        end_layout.addWidget(self.end_sec_spin)
        form_layout.addRow("End:", end_layout)
        
        # Set end to audio duration if available
        if self.audio_duration > 0:
            end_min = int(self.audio_duration // 60)
            end_sec = int(self.audio_duration % 60)
            self.end_min_spin.setValue(end_min)
            self.end_sec_spin.setValue(end_sec)
            
            duration_label = QLabel(f"Audio duration: {end_min}:{end_sec:02d}")
            form_layout.addRow("", duration_label)
        
        layout.addWidget(form_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._validate_and_accept)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _validate_and_accept(self):
        """Validate the time range and accept."""
        start_time, end_time = self.get_range()
        
        if end_time <= start_time:
            QMessageBox.warning(
                self, "Invalid Range",
                "End time must be greater than start time."
            )
            return
        
        self.accept()
    
    def get_range(self) -> tuple:
        """Get the selected time range in seconds.
        
        Returns:
            Tuple of (start_seconds, end_seconds)
        """
        start = self.start_min_spin.value() * 60 + self.start_sec_spin.value()
        end = self.end_min_spin.value() * 60 + self.end_sec_spin.value()
        return start, end


class PolishWorker(QThread):
    """Background worker for AI polishing."""
    
    progress = pyqtSignal(int, int)  # current, total
    segment_polished = pyqtSignal(int, object)  # index, PolishResult
    finished = pyqtSignal(list)  # List of PolishResult
    error = pyqtSignal(str)
    token_estimate = pyqtSignal(int, int)  # input_tokens, output_tokens (estimated)
    
    def __init__(self, segments: List[str], segment_indices: List[int]):
        super().__init__()
        self.segments = segments
        self.segment_indices = segment_indices
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        try:
            ai_manager = get_ai_manager()
            provider = ai_manager.get_active_provider()
            
            if not provider:
                self.error.emit("No AI provider configured. Go to AI > AI Settings.")
                return
            
            results = []
            total = len(self.segments)
            total_input_tokens = 0
            total_output_tokens = 0
            
            for i, text in enumerate(self.segments):
                if self._cancelled:
                    break
                
                # Estimate tokens (rough: ~4 chars per token)
                input_tokens = len(text) // 4 + 50  # +50 for prompt overhead
                total_input_tokens += input_tokens
                
                # Use previous segment as context
                context = self.segments[i - 1] if i > 0 else None
                result = provider.polish_text(text, context)
                results.append(result)
                
                # Estimate output tokens
                output_tokens = len(result.polished_text) // 4
                total_output_tokens += output_tokens
                
                self.segment_polished.emit(self.segment_indices[i], result)
                self.progress.emit(i + 1, total)
                self.token_estimate.emit(total_input_tokens, total_output_tokens)
            
            self.finished.emit(results)
            
        except Exception as e:
            logger.error(f"Polish worker error: {e}", exc_info=True)
            self.error.emit(str(e))


class AIPolishDialog(QDialog):
    """Dialog for AI polishing with review capability."""
    
    changes_applied = pyqtSignal()  # Emitted when changes are applied
    
    def __init__(
        self, 
        transcript: Transcript, 
        segments_to_polish: Optional[List[Segment]] = None,
        segment_indices: Optional[List[int]] = None,
        parent=None
    ):
        super().__init__(parent)
        self.transcript = transcript
        self.segments_to_polish = segments_to_polish or transcript.segments
        self.segment_indices = segment_indices or list(range(len(transcript.segments)))
        self.results: List[PolishResult] = []
        self.worker: Optional[PolishWorker] = None
        self.selected_changes: List[bool] = []
        
        self.setWindowTitle("AI Polish Transcript")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Scope info
        scope_group = QGroupBox("Polish Scope")
        scope_layout = QVBoxLayout(scope_group)
        
        segment_count = len(self.segments_to_polish)
        total_count = len(self.transcript.segments)
        
        if segment_count == total_count:
            scope_text = f"Polishing entire transcript ({segment_count} segments)"
        else:
            scope_text = f"Polishing {segment_count} of {total_count} segments"
        
        self.scope_label = QLabel(scope_text)
        scope_layout.addWidget(self.scope_label)
        
        # Token estimate
        total_chars = sum(len(s.text) for s in self.segments_to_polish)
        est_tokens = total_chars // 4 + (50 * segment_count)  # +50 per segment for prompt
        self.token_label = QLabel(f"Estimated tokens: ~{est_tokens:,} input")
        self.token_label.setStyleSheet("color: #666;")
        scope_layout.addWidget(self.token_label)
        
        layout.addWidget(scope_group)
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Ready to polish transcript")
        status_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_group)
        
        # Review table
        review_group = QGroupBox("Review Changes")
        review_layout = QVBoxLayout(review_group)
        
        # Instructions
        instructions = QLabel(
            "Check the boxes next to changes you want to apply. "
            "Double-click a row to see the full comparison."
        )
        instructions.setWordWrap(True)
        review_layout.addWidget(instructions)
        
        # Table
        self.review_table = QTableWidget()
        self.review_table.setColumnCount(5)
        self.review_table.setHorizontalHeaderLabels([
            "Apply", "#", "Original", "Polished", "Changes"
        ])
        self.review_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.review_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.review_table.setColumnWidth(0, 50)
        self.review_table.setColumnWidth(1, 50)
        self.review_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.review_table.itemDoubleClicked.connect(self._show_comparison)
        review_layout.addWidget(self.review_table)
        
        # Select all / none
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_layout.addWidget(select_all_btn)
        
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        select_layout.addWidget(select_none_btn)
        
        select_layout.addStretch()
        
        self.changes_count_label = QLabel("0 changes selected")
        select_layout.addWidget(self.changes_count_label)
        
        review_layout.addLayout(select_layout)
        
        layout.addWidget(review_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Polishing")
        self.start_btn.clicked.connect(self._start_polish)
        button_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_polish)
        self.cancel_btn.setEnabled(False)
        button_layout.addWidget(self.cancel_btn)
        
        button_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply Selected Changes")
        self.apply_btn.clicked.connect(self._apply_changes)
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _start_polish(self):
        """Start the polishing process."""
        ai_manager = get_ai_manager()
        
        if not ai_manager.get_configured_provider():
            QMessageBox.warning(
                self,
                "No AI Provider",
                "Please configure an AI provider first.\n\n"
                "Go to AI > AI Settings to set up OpenAI, Ollama, or another provider."
            )
            return
        
        # Get segment texts
        texts = [seg.text for seg in self.segments_to_polish]
        
        if not texts:
            QMessageBox.warning(self, "No Text", "No segments to polish.")
            return
        
        # Clear previous results
        self.review_table.setRowCount(0)
        self.results = []
        self.selected_changes = []
        
        # Update UI
        self.status_label.setText(f"Polishing {len(texts)} segments...")
        self.progress_bar.setRange(0, len(texts))
        self.progress_bar.setValue(0)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        
        # Start worker
        self.worker = PolishWorker(texts, self.segment_indices)
        self.worker.progress.connect(self._on_progress)
        self.worker.segment_polished.connect(self._on_segment_polished)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.token_estimate.connect(self._on_token_estimate)
        self.worker.start()
    
    def _cancel_polish(self):
        """Cancel the polishing process."""
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")
    
    def _on_progress(self, current: int, total: int):
        """Handle progress update."""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Polishing segment {current}/{total}...")
    
    def _on_token_estimate(self, input_tokens: int, output_tokens: int):
        """Handle token estimate update."""
        self.token_label.setText(
            f"Tokens used: ~{input_tokens:,} input, ~{output_tokens:,} output"
        )
    
    def _on_segment_polished(self, seg_index: int, result: PolishResult):
        """Handle individual segment polished."""
        self.results.append(result)
        
        # Add to table
        row = self.review_table.rowCount()
        self.review_table.insertRow(row)
        
        # Checkbox
        checkbox = QCheckBox()
        has_changes = result.original_text.strip() != result.polished_text.strip()
        checkbox.setChecked(has_changes)
        checkbox.stateChanged.connect(self._update_changes_count)
        self.selected_changes.append(has_changes)
        
        checkbox_widget = QTableWidgetItem()
        self.review_table.setItem(row, 0, checkbox_widget)
        self.review_table.setCellWidget(row, 0, checkbox)
        
        # Segment number
        num_item = QTableWidgetItem(str(seg_index + 1))
        num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.review_table.setItem(row, 1, num_item)
        
        # Original text (truncated)
        orig_text = result.original_text[:100] + "..." if len(result.original_text) > 100 else result.original_text
        orig_item = QTableWidgetItem(orig_text)
        orig_item.setFlags(orig_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.review_table.setItem(row, 2, orig_item)
        
        # Polished text (truncated)
        polish_text = result.polished_text[:100] + "..." if len(result.polished_text) > 100 else result.polished_text
        polish_item = QTableWidgetItem(polish_text)
        polish_item.setFlags(polish_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if has_changes:
            polish_item.setBackground(QBrush(QColor("#e8f5e9")))  # Light green
        self.review_table.setItem(row, 3, polish_item)
        
        # Changes summary
        changes_text = "; ".join(result.changes_made) if result.changes_made else "No changes"
        changes_item = QTableWidgetItem(changes_text)
        changes_item.setFlags(changes_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.review_table.setItem(row, 4, changes_item)
        
        self._update_changes_count()
    
    def _on_finished(self, results: List[PolishResult]):
        """Handle polishing complete."""
        self.results = results
        self.status_label.setText(f"Polishing complete. {len(results)} segments processed.")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.apply_btn.setEnabled(True)
        
        # Count actual changes
        changes_count = sum(
            1 for r in results 
            if r.original_text.strip() != r.polished_text.strip()
        )
        
        if changes_count == 0:
            QMessageBox.information(
                self,
                "No Changes",
                "The AI didn't suggest any changes to the transcript."
            )
    
    def _on_error(self, error_msg: str):
        """Handle error."""
        self.status_label.setText(f"Error: {error_msg}")
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.critical(self, "Error", f"Polishing failed:\n{error_msg}")
    
    def _set_all_checked(self, checked: bool):
        """Set all checkboxes to checked/unchecked."""
        for row in range(self.review_table.rowCount()):
            checkbox = self.review_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)
    
    def _update_changes_count(self):
        """Update the selected changes count label."""
        count = 0
        for row in range(self.review_table.rowCount()):
            checkbox = self.review_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                # Only count if there's an actual change
                if row < len(self.results):
                    result = self.results[row]
                    if result.original_text.strip() != result.polished_text.strip():
                        count += 1
        
        self.changes_count_label.setText(f"{count} changes selected")
    
    def _show_comparison(self, item):
        """Show full comparison dialog for a row."""
        row = item.row()
        if row < len(self.results):
            result = self.results[row]
            seg_idx = self.segment_indices[row] if row < len(self.segment_indices) else row
            
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Comparison - Segment {seg_idx + 1}")
            dialog.setMinimumSize(700, 400)
            
            layout = QVBoxLayout(dialog)
            
            splitter = QSplitter(Qt.Orientation.Horizontal)
            
            # Original
            orig_group = QGroupBox("Original")
            orig_layout = QVBoxLayout(orig_group)
            orig_text = QTextEdit()
            orig_text.setPlainText(result.original_text)
            orig_text.setReadOnly(True)
            orig_layout.addWidget(orig_text)
            splitter.addWidget(orig_group)
            
            # Polished
            polish_group = QGroupBox("Polished")
            polish_layout = QVBoxLayout(polish_group)
            polish_text = QTextEdit()
            polish_text.setPlainText(result.polished_text)
            polish_text.setReadOnly(True)
            polish_layout.addWidget(polish_text)
            splitter.addWidget(polish_group)
            
            layout.addWidget(splitter)
            
            # Changes
            if result.changes_made:
                changes_label = QLabel("Changes: " + "; ".join(result.changes_made))
                changes_label.setWordWrap(True)
                layout.addWidget(changes_label)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec()
    
    def _apply_changes(self):
        """Apply selected changes to the transcript."""
        applied_count = 0
        
        for row in range(self.review_table.rowCount()):
            checkbox = self.review_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                if row < len(self.results) and row < len(self.segment_indices):
                    result = self.results[row]
                    seg_idx = self.segment_indices[row]
                    
                    if seg_idx < len(self.transcript.segments):
                        segment = self.transcript.segments[seg_idx]
                        
                        if result.original_text.strip() != result.polished_text.strip():
                            segment.text = result.polished_text
                            applied_count += 1
        
        if applied_count > 0:
            logger.info(f"Applied {applied_count} AI polish changes")
            self.changes_applied.emit()
            
            QMessageBox.information(
                self,
                "Changes Applied",
                f"Applied {applied_count} changes to the transcript."
            )
            self.accept()
        else:
            QMessageBox.information(
                self,
                "No Changes",
                "No changes were selected to apply."
            )
    
    def closeEvent(self, event):
        """Handle close event."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        event.accept()
