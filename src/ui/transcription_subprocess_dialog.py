"""
Subprocess-based transcription dialog.

This dialog spawns Whisper in a completely separate process, solving the crash-on-load issue
because GPU resources are NEVER loaded in the main GUI process.
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QTextEdit, QPushButton, QGroupBox, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QProcess, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor

from src.utils.logger import get_logger

logger = get_logger("transcription_subprocess")


class SubprocessTranscriptionDialog(QDialog):
    """Transcription dialog that runs Whisper in a subprocess."""
    
    transcription_complete = pyqtSignal(str)  # Emits file path when done
    
    def __init__(
        self,
        audio_path: str,
        vocabulary: list,
        model_size: str = "large-v3",
        device: str = "auto",
        segment_mode: str = "natural",
        parent=None
    ):
        super().__init__(parent)
        self.audio_path = audio_path
        self.vocabulary = vocabulary
        self.model_size = model_size
        self.device = device
        self.segment_mode = segment_mode
        
        self.process: Optional[QProcess] = None
        self.output_path: Optional[str] = None
        self.start_time: Optional[float] = None
        self.segment_count = 0
        self.is_complete = False
        
        self._init_ui()
        self._setup_timer()
    
    def _init_ui(self):
        """Initialize the UI."""
        self.setWindowTitle("Transcription Progress (Subprocess)")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Status header
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QGridLayout(header_frame)
        
        # Stage label
        self.stage_label = QLabel("Initializing subprocess...")
        self.stage_label.setFont(QFont("", 12, QFont.Weight.Bold))
        header_layout.addWidget(self.stage_label, 0, 0, 1, 2)
        
        # Info labels
        header_layout.addWidget(QLabel("Device:"), 1, 0)
        self.device_label = QLabel("Detecting...")
        self.device_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.device_label, 1, 1)
        
        header_layout.addWidget(QLabel("Model:"), 2, 0)
        self.model_label = QLabel(self.model_size)
        header_layout.addWidget(self.model_label, 2, 1)
        
        header_layout.addWidget(QLabel("Time Elapsed:"), 3, 0)
        self.time_label = QLabel("00:00")
        header_layout.addWidget(self.time_label, 3, 1)
        
        header_layout.addWidget(QLabel("Segments:"), 4, 0)
        self.segment_label = QLabel("--")
        header_layout.addWidget(self.segment_label, 4, 1)
        
        # Mode indicator
        header_layout.addWidget(QLabel("Mode:"), 5, 0)
        mode_label = QLabel("SUBPROCESS (isolated GPU process)")
        mode_label.setStyleSheet("color: green; font-weight: bold;")
        header_layout.addWidget(mode_label, 5, 1)
        
        layout.addWidget(header_frame)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Process Output")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(200)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self._on_close)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _setup_timer(self):
        """Setup elapsed time timer."""
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)
    
    def _generate_output_path(self) -> str:
        """Generate output path for the streaming file."""
        stream_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "PersonalTranscribe",
            "streaming"
        )
        os.makedirs(stream_dir, exist_ok=True)
        
        audio_name = Path(self.audio_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(stream_dir, f"{audio_name}_{timestamp}.json")
    
    def start(self):
        """Start the transcription subprocess."""
        self.start_time = time.time()
        self.elapsed_timer.start(1000)
        
        self.output_path = self._generate_output_path()
        
        self._log("Starting transcription subprocess...", "info")
        self._log(f"Audio: {Path(self.audio_path).name}", "info")
        self._log(f"Output: {Path(self.output_path).name}", "info")
        self._log("-" * 40, "info")
        
        # Build command
        # Use sys.executable to get the current Python interpreter
        python_exe = sys.executable
        
        # Build vocabulary string
        vocab_str = ",".join(self.vocabulary) if self.vocabulary else ""
        
        # Create the process
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)
        
        # Build arguments
        args = [
            "-m", "src.transcription.transcribe_process",
            self.audio_path,
            self.output_path,
            "--model", self.model_size,
            "--device", self.device,
            "--segment-mode", self.segment_mode,
        ]
        if vocab_str:
            args.extend(["--vocabulary", vocab_str])
        
        logger.info(f"Starting subprocess: {python_exe} {' '.join(args)}")
        self._log(f"Command: python -m src.transcription.transcribe_process", "info")
        
        # Start the process
        self.process.start(python_exe, args)
        
        if not self.process.waitForStarted(5000):
            self._log("ERROR: Failed to start subprocess!", "error")
            self.stage_label.setText("Failed to start")
            self.close_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
    
    def _on_process_output(self):
        """Handle subprocess output."""
        if not self.process:
            return
        
        data = self.process.readAllStandardOutput().data().decode('utf-8', errors='replace')
        
        for line in data.strip().split('\n'):
            if not line.strip():
                continue
            
            try:
                msg = json.loads(line)
                self._handle_message(msg)
            except json.JSONDecodeError:
                # Not JSON, just log it
                self._log(line, "info")
    
    def _handle_message(self, msg: dict):
        """Handle a message from the subprocess."""
        msg_type = msg.get("type", "")
        
        if msg_type == "progress":
            stage = msg.get("stage", "")
            progress = msg.get("progress", 0)
            message = msg.get("message", "")
            
            self.progress_bar.setValue(int(progress))
            self.stage_label.setText(message or stage)
            
            # Handle device detection
            if stage == "device":
                device = msg.get("device", "")
                compute_type = msg.get("compute_type", "")
                if device == "cuda":
                    self.device_label.setText(f"GPU (CUDA) - {compute_type}")
                    self.device_label.setStyleSheet("font-weight: bold; color: green;")
                else:
                    self.device_label.setText(f"CPU - {compute_type}")
                    self.device_label.setStyleSheet("font-weight: bold; color: orange;")
            
            if message:
                self._log(message, "info")
        
        elif msg_type == "segment":
            self.segment_count = msg.get("segment_num", 0)
            self.segment_label.setText(f"{self.segment_count} processed")
            
            text_preview = msg.get("text_preview", "")
            start = msg.get("start", 0)
            self._log(f"[{self.segment_count}] {self._format_time(start)} - {text_preview}", "info")
        
        elif msg_type == "error":
            error_msg = msg.get("message", "Unknown error")
            self._log(f"ERROR: {error_msg}", "error")
            self.stage_label.setText("Error occurred")
        
        elif msg_type == "complete":
            self.is_complete = True
            segment_count = msg.get("segment_count", 0)
            word_count = msg.get("word_count", 0)
            duration = msg.get("duration", 0)
            
            self._log("-" * 40, "info")
            self._log(f"Transcription complete!", "success")
            self._log(f"Segments: {segment_count}, Words: {word_count}", "success")
            self._log(f"Time: {duration:.1f}s", "success")
            
            self.stage_label.setText("Complete!")
            self.progress_bar.setValue(100)
            self.segment_label.setText(f"{segment_count} segments")
    
    def _on_process_finished(self, exit_code: int, exit_status):
        """Handle subprocess completion."""
        self.elapsed_timer.stop()
        
        logger.info(f"Subprocess finished with exit code {exit_code}")
        
        # Check if output file exists and is complete, even if process crashed
        # The subprocess might crash during cleanup AFTER saving the file
        file_is_complete = self._check_output_file_complete()
        
        if file_is_complete:
            if exit_code != 0:
                self._log(f"Subprocess crashed during cleanup (exit {exit_code}), but transcription completed!", "warning")
                self._log("File was saved before crash - loading anyway.", "success")
            else:
                self._log("Subprocess exited cleanly. GPU resources freed.", "success")
            
            self.stage_label.setText("Complete! Ready to load.")
            self.cancel_button.setEnabled(False)
            self.close_button.setEnabled(True)
            
            # Emit the file path - the file is good!
            self.transcription_complete.emit(self.output_path)
        else:
            self._log(f"Subprocess exited with code {exit_code}", "warning")
            
            # Check if there's a partial file we can still use
            if self.output_path and os.path.exists(self.output_path):
                self._log("Partial transcript may be available in the output file.", "info")
                self._log("You can try File > Recover Transcription.", "info")
            
            self.stage_label.setText("Process ended")
            self.cancel_button.setEnabled(False)
            self.close_button.setEnabled(True)
    
    def _check_output_file_complete(self) -> bool:
        """Check if the output file exists and has status 'complete'."""
        if not self.output_path or not os.path.exists(self.output_path):
            return False
        
        try:
            with open(self.output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            status = data.get("status", "")
            segment_count = len(data.get("segments", []))
            
            if status == "complete" and segment_count > 0:
                self.segment_count = segment_count
                self.segment_label.setText(f"{segment_count} segments")
                self._log(f"File check: status=complete, segments={segment_count}", "success")
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Could not check output file: {e}")
            return False
    
    def _on_process_error(self, error):
        """Handle process error."""
        error_strings = {
            QProcess.ProcessError.FailedToStart: "Failed to start",
            QProcess.ProcessError.Crashed: "Process crashed",
            QProcess.ProcessError.Timedout: "Process timed out",
            QProcess.ProcessError.WriteError: "Write error",
            QProcess.ProcessError.ReadError: "Read error",
            QProcess.ProcessError.UnknownError: "Unknown error",
        }
        error_msg = error_strings.get(error, f"Error {error}")
        self._log(f"Process error: {error_msg}", "error")
        logger.error(f"Subprocess error: {error_msg}")
    
    def _on_cancel(self):
        """Cancel the transcription."""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self._log("Terminating subprocess...", "warning")
            self.process.terminate()
            
            # Wait a bit, then kill if necessary
            if not self.process.waitForFinished(3000):
                self._log("Force killing subprocess...", "warning")
                self.process.kill()
        
        self.stage_label.setText("Cancelled")
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
    
    def _on_close(self):
        """Close the dialog."""
        self.accept()
    
    def _log(self, message: str, level: str = "info"):
        """Add a message to the log."""
        colors = {
            "info": "#000000",
            "warning": "#B8860B",
            "error": "#DC143C",
            "success": "#228B22"
        }
        color = colors.get(level, "#000000")
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        
        if level == "error":
            self.log_text.append(f'<span style="color: {color}; font-weight: bold;">[ERROR] {message}</span>')
        elif level == "warning":
            self.log_text.append(f'<span style="color: {color};">[WARN] {message}</span>')
        elif level == "success":
            self.log_text.append(f'<span style="color: {color}; font-weight: bold;">{message}</span>')
        else:
            self.log_text.append(f'<span style="color: {color};">{message}</span>')
        
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _update_elapsed_time(self):
        """Update elapsed time display."""
        if self.start_time:
            elapsed = time.time() - self.start_time
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            self.time_label.setText(f"{mins:02d}:{secs:02d}")
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
    
    def closeEvent(self, event):
        """Handle close event."""
        self.elapsed_timer.stop()
        
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.terminate()
            self.process.waitForFinished(2000)
        
        event.accept()
