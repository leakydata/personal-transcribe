"""
Main window for PersonalTranscribe application.
"""

import os
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QProgressDialog, QLabel, QApplication,
    QDockWidget, QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QUndoStack

from src.config.settings import get_settings, get_settings_manager
from src.config.shortcuts import Shortcuts
from src.models.transcript import Transcript
from src.models.project import Project, ProjectManager
from src.models.undo_commands import EditSegmentTextCommand, ToggleBookmarkCommand
from src.ui.audio_player import AudioPlayer
from src.ui.transcript_editor import TranscriptEditor
from src.ui.vocab_dialog import VocabularyDialog
from src.ui.export_dialog import ExportDialog
from src.ui.find_replace import FindReplaceDialog
from src.ui.statistics_panel import StatisticsPanel
from src.ui.metadata_dialog import MetadataDialog
from src.models.metadata import RecordingMetadata
from src.ui.transcription_dialog import TranscriptionProgressDialog
from src.ui.ai_settings_dialog import AISettingsDialog
from src.ui.ai_polish_dialog import AIPolishDialog
from src.utils.logger import get_logger, get_log_file_path, clear_logs, get_log_size, format_size

# Module logger
logger = get_logger("main_window")


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.settings = get_settings()
        self.settings_manager = get_settings_manager()
        
        self.current_project: Optional[Project] = None
        self.current_audio_path: Optional[str] = None
        self.vocabulary: list = []
        self.metadata: RecordingMetadata = RecordingMetadata()
        self.transcription_dialog: Optional[TranscriptionProgressDialog] = None
        self.is_modified = False
        
        # Undo/Redo stack
        self.undo_stack = QUndoStack(self)
        
        # Find/Replace dialog (persistent)
        self.find_replace_dialog: Optional[FindReplaceDialog] = None
        
        # Auto-save timer
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        
        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()
        self._create_dock_widgets()
        self._connect_signals()
        self._load_vocabulary()
        self._setup_autosave()
        
        # Restore window state
        self.resize(self.settings.window_width, self.settings.window_height)
        if self.settings.window_maximized:
            self.showMaximized()
    
    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("PersonalTranscribe")
        self.setMinimumSize(800, 600)
        
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter (vertical: audio player on top, transcript below)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Audio player
        self.audio_player = AudioPlayer()
        self.main_splitter.addWidget(self.audio_player)
        
        # Transcript editor
        self.transcript_editor = TranscriptEditor()
        self.main_splitter.addWidget(self.transcript_editor)
        
        # Set splitter sizes
        self.main_splitter.setSizes(self.settings.splitter_sizes)
        
        layout.addWidget(self.main_splitter)
    
    def _create_menus(self):
        """Create menu bar and menus."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        self.open_audio_action = QAction("Open &Audio...", self)
        self.open_audio_action.setShortcut(Shortcuts.OPEN_AUDIO.key_sequence)
        self.open_audio_action.triggered.connect(self.open_audio)
        file_menu.addAction(self.open_audio_action)
        
        self.open_project_action = QAction("Open &Project...", self)
        self.open_project_action.setShortcut(Shortcuts.OPEN_PROJECT.key_sequence)
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)
        
        file_menu.addSeparator()
        
        self.save_action = QAction("&Save Project", self)
        self.save_action.setShortcut(Shortcuts.SAVE_PROJECT.key_sequence)
        self.save_action.triggered.connect(self.save_project)
        self.save_action.setEnabled(False)
        file_menu.addAction(self.save_action)
        
        self.save_as_action = QAction("Save Project &As...", self)
        self.save_as_action.setShortcut(Shortcuts.SAVE_PROJECT_AS.key_sequence)
        self.save_as_action.triggered.connect(self.save_project_as)
        self.save_as_action.setEnabled(False)
        file_menu.addAction(self.save_as_action)
        
        file_menu.addSeparator()
        
        self.export_pdf_action = QAction("&Export to PDF...", self)
        self.export_pdf_action.setShortcut(Shortcuts.EXPORT_PDF.key_sequence)
        self.export_pdf_action.triggered.connect(self.export_pdf)
        self.export_pdf_action.setEnabled(False)
        file_menu.addAction(self.export_pdf_action)
        
        file_menu.addSeparator()
        
        self.metadata_action = QAction("Recording &Metadata...", self)
        self.metadata_action.setShortcut("Ctrl+M")
        self.metadata_action.triggered.connect(self.edit_metadata)
        file_menu.addAction(self.metadata_action)
        
        file_menu.addSeparator()
        
        # Recent files submenu
        self.recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_menu()
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        self.undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        self.undo_action.setShortcut(Shortcuts.UNDO.key_sequence)
        edit_menu.addAction(self.undo_action)
        
        self.redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        self.redo_action.setShortcut(Shortcuts.REDO.key_sequence)
        edit_menu.addAction(self.redo_action)
        
        edit_menu.addSeparator()
        
        self.find_action = QAction("&Find...", self)
        self.find_action.setShortcut(Shortcuts.FIND.key_sequence)
        self.find_action.setEnabled(False)
        edit_menu.addAction(self.find_action)
        
        self.find_replace_action = QAction("Find && &Replace...", self)
        self.find_replace_action.setShortcut(Shortcuts.FIND_REPLACE.key_sequence)
        self.find_replace_action.triggered.connect(self.open_find_replace)
        self.find_replace_action.setEnabled(False)
        edit_menu.addAction(self.find_replace_action)
        
        edit_menu.addSeparator()
        
        self.toggle_bookmark_action = QAction("Toggle &Bookmark", self)
        self.toggle_bookmark_action.setShortcut(Shortcuts.TOGGLE_BOOKMARK.key_sequence)
        self.toggle_bookmark_action.triggered.connect(self.toggle_bookmark)
        self.toggle_bookmark_action.setEnabled(False)
        edit_menu.addAction(self.toggle_bookmark_action)
        
        self.next_bookmark_action = QAction("Next Bookmark", self)
        self.next_bookmark_action.setShortcut(Shortcuts.NEXT_BOOKMARK.key_sequence)
        self.next_bookmark_action.triggered.connect(self.jump_to_next_bookmark)
        self.next_bookmark_action.setEnabled(False)
        edit_menu.addAction(self.next_bookmark_action)
        
        self.prev_bookmark_action = QAction("Previous Bookmark", self)
        self.prev_bookmark_action.setShortcut(Shortcuts.PREV_BOOKMARK.key_sequence)
        self.prev_bookmark_action.triggered.connect(self.jump_to_prev_bookmark)
        self.prev_bookmark_action.setEnabled(False)
        edit_menu.addAction(self.prev_bookmark_action)
        
        edit_menu.addSeparator()
        
        self.set_speaker_label_action = QAction("Set &Speaker Label...", self)
        self.set_speaker_label_action.triggered.connect(self.set_speaker_label)
        self.set_speaker_label_action.setEnabled(False)
        edit_menu.addAction(self.set_speaker_label_action)
        
        # Transcription menu
        transcription_menu = menubar.addMenu("&Transcription")
        
        self.transcribe_action = QAction("&Start Transcription", self)
        self.transcribe_action.setShortcut(Shortcuts.START_TRANSCRIPTION.key_sequence)
        self.transcribe_action.triggered.connect(self.start_transcription)
        self.transcribe_action.setEnabled(False)
        transcription_menu.addAction(self.transcribe_action)
        
        transcription_menu.addSeparator()
        
        self.vocabulary_action = QAction("&Vocabulary Manager...", self)
        self.vocabulary_action.triggered.connect(self.open_vocabulary_manager)
        transcription_menu.addAction(self.vocabulary_action)
        
        # Playback menu
        playback_menu = menubar.addMenu("&Playback")
        
        self.play_pause_action = QAction("Play/Pause", self)
        self.play_pause_action.setShortcut(Shortcuts.PLAY_PAUSE.key_sequence)
        self.play_pause_action.triggered.connect(self.audio_player.toggle_play)
        playback_menu.addAction(self.play_pause_action)
        
        self.replay_action = QAction("Replay Last 5 Seconds", self)
        self.replay_action.setShortcut(Shortcuts.REPLAY_5SEC.key_sequence)
        self.replay_action.triggered.connect(lambda: self.audio_player.replay_last_seconds(5))
        playback_menu.addAction(self.replay_action)
        
        playback_menu.addSeparator()
        
        self.skip_back_action = QAction("Skip Back 5s", self)
        self.skip_back_action.setShortcut(Shortcuts.SKIP_BACKWARD.key_sequence)
        self.skip_back_action.triggered.connect(lambda: self.audio_player.skip(-5))
        playback_menu.addAction(self.skip_back_action)
        
        self.skip_forward_action = QAction("Skip Forward 5s", self)
        self.skip_forward_action.setShortcut(Shortcuts.SKIP_FORWARD.key_sequence)
        self.skip_forward_action.triggered.connect(lambda: self.audio_player.skip(5))
        playback_menu.addAction(self.skip_forward_action)
        
        playback_menu.addSeparator()
        
        self.loop_action = QAction("Toggle Loop Mode", self)
        self.loop_action.setShortcut(Shortcuts.LOOP_SEGMENT.key_sequence)
        self.loop_action.triggered.connect(lambda: self.audio_player.loop_button.click())
        playback_menu.addAction(self.loop_action)
        
        playback_menu.addSeparator()
        
        self.jump_to_time_action = QAction("Jump to Time...", self)
        self.jump_to_time_action.setShortcut(Shortcuts.GO_TO_TIME.key_sequence)
        self.jump_to_time_action.triggered.connect(self.jump_to_time)
        playback_menu.addAction(self.jump_to_time_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self.toggle_waveform_action = QAction("Toggle &Waveform", self)
        self.toggle_waveform_action.setShortcut(Shortcuts.TOGGLE_WAVEFORM.key_sequence)
        self.toggle_waveform_action.setCheckable(True)
        self.toggle_waveform_action.setChecked(True)
        self.toggle_waveform_action.triggered.connect(self.toggle_waveform)
        view_menu.addAction(self.toggle_waveform_action)
        
        self.toggle_stats_action = QAction("Toggle &Statistics Panel", self)
        self.toggle_stats_action.setCheckable(True)
        self.toggle_stats_action.setChecked(False)
        self.toggle_stats_action.triggered.connect(self.toggle_statistics_panel)
        view_menu.addAction(self.toggle_stats_action)
        
        view_menu.addSeparator()
        
        self.toggle_confidence_action = QAction("Show &Confidence Highlighting", self)
        self.toggle_confidence_action.setCheckable(True)
        self.toggle_confidence_action.setChecked(True)
        self.toggle_confidence_action.triggered.connect(self.toggle_confidence_highlighting)
        view_menu.addAction(self.toggle_confidence_action)
        
        self.next_low_conf_action = QAction("Next Low Confidence", self)
        self.next_low_conf_action.setShortcut(Shortcuts.NEXT_LOW_CONFIDENCE.key_sequence)
        self.next_low_conf_action.triggered.connect(self.jump_to_next_low_confidence)
        self.next_low_conf_action.setEnabled(False)
        view_menu.addAction(self.next_low_conf_action)
        
        self.prev_low_conf_action = QAction("Previous Low Confidence", self)
        self.prev_low_conf_action.setShortcut(Shortcuts.PREV_LOW_CONFIDENCE.key_sequence)
        self.prev_low_conf_action.triggered.connect(self.jump_to_prev_low_confidence)
        self.prev_low_conf_action.setEnabled(False)
        view_menu.addAction(self.prev_low_conf_action)
        
        view_menu.addSeparator()
        
        self.toggle_dark_mode_action = QAction("&Dark Mode", self)
        self.toggle_dark_mode_action.setShortcut(Shortcuts.TOGGLE_DARK_MODE.key_sequence)
        self.toggle_dark_mode_action.setCheckable(True)
        self.toggle_dark_mode_action.setChecked(self.settings.theme == "dark")
        self.toggle_dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(self.toggle_dark_mode_action)
        
        # AI menu (top-level for visibility)
        ai_menu = menubar.addMenu("&AI")
        
        self.ai_settings_action = QAction("AI &Settings...", self)
        self.ai_settings_action.triggered.connect(self.open_ai_settings)
        ai_menu.addAction(self.ai_settings_action)
        
        ai_menu.addSeparator()
        
        self.ai_polish_all_action = QAction("Polish &Entire Transcript...", self)
        self.ai_polish_all_action.setShortcut("Ctrl+Shift+P")
        self.ai_polish_all_action.triggered.connect(lambda: self.open_ai_polish("all"))
        self.ai_polish_all_action.setEnabled(False)
        ai_menu.addAction(self.ai_polish_all_action)
        
        self.ai_polish_selected_action = QAction("Polish &Selected Lines...", self)
        self.ai_polish_selected_action.triggered.connect(lambda: self.open_ai_polish("selected"))
        self.ai_polish_selected_action.setEnabled(False)
        ai_menu.addAction(self.ai_polish_selected_action)
        
        self.ai_polish_range_action = QAction("Polish Time &Range...", self)
        self.ai_polish_range_action.triggered.connect(lambda: self.open_ai_polish("range"))
        self.ai_polish_range_action.setEnabled(False)
        ai_menu.addAction(self.ai_polish_range_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        # Log management
        view_logs_action = QAction("&View Log File", self)
        view_logs_action.triggered.connect(self.view_logs)
        help_menu.addAction(view_logs_action)
        
        open_log_folder_action = QAction("Open Log &Folder", self)
        open_log_folder_action.triggered.connect(self.open_log_folder)
        help_menu.addAction(open_log_folder_action)
        
        clear_logs_action = QAction("&Clear Logs", self)
        clear_logs_action.triggered.connect(self.clear_application_logs)
        help_menu.addAction(clear_logs_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def _create_toolbar(self):
        """Create main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        toolbar.addAction(self.open_audio_action)
        toolbar.addAction(self.transcribe_action)
        toolbar.addSeparator()
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.export_pdf_action)
    
    def _create_statusbar(self):
        """Create status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        # Status labels
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)
        
        self.position_label = QLabel("")
        self.statusbar.addPermanentWidget(self.position_label)
        
        self.duration_label = QLabel("")
        self.statusbar.addPermanentWidget(self.duration_label)
        
        # Autosave indicator
        self.autosave_label = QLabel("")
        self.statusbar.addPermanentWidget(self.autosave_label)
    
    def _create_dock_widgets(self):
        """Create dock widgets for statistics, etc."""
        # Statistics panel dock
        self.statistics_panel = StatisticsPanel()
        self.stats_dock = QDockWidget("Statistics", self)
        self.stats_dock.setWidget(self.statistics_panel)
        self.stats_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | 
            Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.stats_dock)
        self.stats_dock.hide()  # Hidden by default
    
    def _setup_autosave(self):
        """Configure autosave based on settings."""
        if self.settings.auto_save_enabled:
            interval_ms = self.settings.auto_save_interval * 1000
            self.autosave_timer.start(interval_ms)
            self.autosave_label.setText("Autosave: ON")
        else:
            self.autosave_timer.stop()
            self.autosave_label.setText("")
    
    def _autosave(self):
        """Perform autosave if project has been saved before."""
        if self.is_modified and self.current_project and self.current_project.file_path:
            try:
                self._save_project_to(self.current_project.file_path)
                self.status_label.setText("Auto-saved")
            except Exception as e:
                print(f"Autosave failed: {e}")
    
    def _connect_signals(self):
        """Connect widget signals."""
        # Audio player signals
        self.audio_player.position_changed.connect(self._on_audio_position_changed)
        self.audio_player.duration_changed.connect(self._on_audio_duration_changed)
        
        # Transcript editor signals
        self.transcript_editor.segment_clicked.connect(self._on_segment_clicked)
        self.transcript_editor.segment_edited.connect(self._on_segment_edited)
    
    def _load_vocabulary(self):
        """Load vocabulary from file."""
        vocab_path = Path(self.settings.vocabulary_file)
        if vocab_path.exists():
            try:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self.vocabulary = [
                    line.strip() for line in lines
                    if line.strip() and not line.strip().startswith("#")
                ]
            except Exception as e:
                print(f"Error loading vocabulary: {e}")
    
    def _update_recent_menu(self):
        """Update recent files menu."""
        self.recent_menu.clear()
        recent_files = self.settings_manager.get_recent_files()
        
        if not recent_files:
            action = QAction("(No recent files)", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
        else:
            for path in recent_files:
                action = QAction(os.path.basename(path), self)
                action.setData(path)
                action.triggered.connect(lambda checked, p=path: self._open_recent_file(p))
                self.recent_menu.addAction(action)
    
    def _open_recent_file(self, path: str):
        """Open a file from recent files."""
        if path.endswith(".ptproj"):
            self._load_project(path)
        else:
            self._load_audio(path)
    
    def open_audio(self):
        """Open audio file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg *.wma);;All Files (*)"
        )
        
        if file_path:
            self._load_audio(file_path)
    
    def _load_audio(self, file_path: str):
        """Load an audio file."""
        try:
            self.audio_player.load_audio(file_path)
            self.current_audio_path = file_path
            self.transcribe_action.setEnabled(True)
            self.settings_manager.add_recent_file(file_path)
            self._update_recent_menu()
            self.status_label.setText(f"Loaded: {os.path.basename(file_path)}")
            self.setWindowTitle(f"PersonalTranscribe - {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load audio:\n{e}")
    
    def open_project(self):
        """Open project file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            "",
            "PersonalTranscribe Projects (*.ptproj);;All Files (*)"
        )
        
        if file_path:
            self._load_project(file_path)
    
    def _load_project(self, file_path: str):
        """Load a project file."""
        try:
            project = ProjectManager.load(file_path)
            self.current_project = project
            
            # Load audio if exists
            if project.audio_file and os.path.exists(project.audio_file):
                self.audio_player.load_audio(project.audio_file)
                self.current_audio_path = project.audio_file
            
            # Load transcript
            if project.transcript:
                self.transcript_editor.load_transcript(project.transcript)
                self.statistics_panel.set_transcript(project.transcript)
                self._enable_edit_actions(True)
            
            # Load vocabulary
            self.vocabulary = project.vocabulary.copy()
            
            self.transcribe_action.setEnabled(bool(self.current_audio_path))
            self.save_action.setEnabled(True)
            self.save_as_action.setEnabled(True)
            self.export_pdf_action.setEnabled(bool(project.transcript))
            
            self.settings_manager.add_recent_file(file_path)
            self._update_recent_menu()
            self.status_label.setText(f"Loaded project: {os.path.basename(file_path)}")
            self.setWindowTitle(f"PersonalTranscribe - {os.path.basename(file_path)}")
            self.is_modified = False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load project:\n{e}")
    
    def save_project(self):
        """Save current project."""
        if self.current_project and self.current_project.file_path:
            self._save_project_to(self.current_project.file_path)
        else:
            self.save_project_as()
    
    def save_project_as(self):
        """Save project with new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            "",
            "PersonalTranscribe Projects (*.ptproj)"
        )
        
        if file_path:
            if not file_path.endswith(".ptproj"):
                file_path += ".ptproj"
            self._save_project_to(file_path)
    
    def _save_project_to(self, file_path: str):
        """Save project to file."""
        try:
            transcript = self.transcript_editor.get_transcript()
            
            project = Project(
                audio_file=self.current_audio_path or "",
                transcript=transcript,
                vocabulary=self.vocabulary.copy(),
                file_path=file_path
            )
            
            ProjectManager.save(project, file_path)
            self.current_project = project
            self.save_action.setEnabled(True)
            self.is_modified = False
            self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project:\n{e}")
    
    def start_transcription(self):
        """Start the transcription process."""
        if not self.current_audio_path:
            QMessageBox.warning(self, "Warning", "Please load an audio file first.")
            return
        
        # Create and show detailed progress dialog
        self.transcription_dialog = TranscriptionProgressDialog(
            audio_path=self.current_audio_path,
            vocabulary=self.vocabulary,
            model_size=self.settings.whisper_model,
            device=self.settings.whisper_device,
            parent=self
        )
        
        self.transcription_dialog.transcription_complete.connect(self._on_transcription_finished)
        self.transcription_dialog.start()
        self.transcription_dialog.exec()
    
    def _on_transcription_finished(self, transcript: Transcript):
        """Handle transcription completion."""
        self.transcribe_action.setEnabled(True)
        
        if transcript:
            try:
                logger.info(f"Loading transcript with {transcript.segment_count} segments...")
                
                # Load transcript (may be slow for large files)
                self.transcript_editor.load_transcript(transcript)
                logger.debug("Transcript loaded into editor")
                
                self.save_action.setEnabled(True)
                self.save_as_action.setEnabled(True)
                self.export_pdf_action.setEnabled(True)
                self._enable_edit_actions(True)
                self.is_modified = True
                
                # Update statistics panel
                self.statistics_panel.set_transcript(transcript)
                logger.debug("Statistics panel updated")
                
                self.status_label.setText(
                    f"Transcription complete: {transcript.segment_count} segments, "
                    f"{transcript.word_count} words"
                )
                logger.info("Transcript UI update complete")
                
            except Exception as e:
                logger.error(f"Error loading transcript into UI: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to display transcript:\n{e}\n\n"
                    "The transcription completed but could not be displayed. "
                    "Check Help > View Log File for details."
                )
        else:
            self.status_label.setText("Transcription failed")
    
    
    def export_pdf(self):
        """Export transcript to PDF."""
        transcript = self.transcript_editor.get_transcript()
        if not transcript or not transcript.segments:
            QMessageBox.warning(self, "Warning", "No transcript to export.")
            return
        
        # Pass metadata to export dialog
        dialog = ExportDialog(transcript, self.current_audio_path, self.metadata, self)
        dialog.exec()
    
    def edit_metadata(self):
        """Open metadata editor dialog."""
        # If we have a project, use its metadata
        if self.current_project and self.current_project.metadata:
            self.metadata = self.current_project.metadata
        
        # Pre-populate with audio file info
        if self.current_audio_path:
            import os
            self.metadata.original_filename = os.path.basename(self.current_audio_path)
        
        # Get audio duration from player
        if self.audio_player.duration_seconds > 0:
            self.metadata.audio_duration = self.audio_player.duration_seconds
        
        dialog = MetadataDialog(self.metadata, self)
        if dialog.exec():
            self.metadata = dialog.get_metadata()
            
            # Update project if we have one
            if self.current_project:
                self.current_project.metadata = self.metadata
            
            self.is_modified = True
            self._update_window_title()
            logger.info("Metadata updated")
    
    def open_vocabulary_manager(self):
        """Open vocabulary manager dialog."""
        dialog = VocabularyDialog(self.vocabulary, self)
        if dialog.exec():
            self.vocabulary = dialog.get_vocabulary()
            self._save_vocabulary()
    
    def _save_vocabulary(self):
        """Save vocabulary to file."""
        vocab_path = Path(self.settings.vocabulary_file)
        try:
            vocab_path.parent.mkdir(parents=True, exist_ok=True)
            with open(vocab_path, "w", encoding="utf-8") as f:
                f.write("# Custom Vocabulary for PersonalTranscribe\n")
                for word in self.vocabulary:
                    f.write(f"{word}\n")
        except Exception as e:
            print(f"Error saving vocabulary: {e}")
    
    def jump_to_time(self):
        """Open dialog to jump to a specific time."""
        from src.models.transcript import format_timestamp
        
        current_pos = self.audio_player.get_current_position()
        duration = self.audio_player.duration_seconds
        
        if duration <= 0:
            QMessageBox.information(self, "No Audio", "Please load an audio file first.")
            return
        
        # Format hint
        hint = f"Current: {format_timestamp(current_pos)} / Duration: {format_timestamp(duration)}"
        
        text, ok = QInputDialog.getText(
            self,
            "Jump to Time",
            f"Enter time (MM:SS or HH:MM:SS):\n{hint}",
            text=format_timestamp(current_pos)
        )
        
        if ok and text:
            # Parse time input
            try:
                parts = text.strip().split(":")
                if len(parts) == 2:
                    # MM:SS
                    minutes, seconds = map(float, parts)
                    target_time = minutes * 60 + seconds
                elif len(parts) == 3:
                    # HH:MM:SS
                    hours, minutes, seconds = map(float, parts)
                    target_time = hours * 3600 + minutes * 60 + seconds
                else:
                    # Try as seconds
                    target_time = float(text)
                
                if 0 <= target_time <= duration:
                    self.audio_player.jump_to_time(target_time)
                else:
                    QMessageBox.warning(
                        self,
                        "Invalid Time",
                        f"Time must be between 00:00 and {format_timestamp(duration)}"
                    )
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Format",
                    "Please enter time as MM:SS or HH:MM:SS"
                )
    
    def toggle_waveform(self, checked: bool):
        """Toggle waveform visibility."""
        self.audio_player.set_waveform_visible(checked)
    
    def show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        shortcuts_text = "Keyboard Shortcuts:\n\n"
        
        for category, shortcuts in Shortcuts.by_category().items():
            shortcuts_text += f"{category}:\n"
            for shortcut in shortcuts:
                shortcuts_text += f"  {shortcut.key_sequence}: {shortcut.description}\n"
            shortcuts_text += "\n"
        
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PersonalTranscribe",
            "PersonalTranscribe v0.1.0\n\n"
            "A professional voice transcription application with GPU-accelerated "
            "transcription using OpenAI Whisper.\n\n"
            "Features:\n"
            "- Fast transcription with word-level timestamps\n"
            "- Gap detection for one-sided conversations\n"
            "- Line-by-line editing with audio sync\n"
            "- PDF export for legal use\n"
            "- Custom vocabulary support"
        )
    
    def view_logs(self):
        """Open the log file in the default text editor."""
        import subprocess
        log_file = get_log_file_path()
        
        if log_file.exists():
            log_size = format_size(get_log_size())
            logger.info(f"Opening log file: {log_file}")
            
            # Open with default application
            try:
                os.startfile(str(log_file))
            except Exception as e:
                QMessageBox.warning(
                    self, 
                    "Could not open log file",
                    f"Log file: {log_file}\nSize: {log_size}\n\nError: {e}"
                )
        else:
            QMessageBox.information(
                self,
                "No Logs",
                "No log file exists yet."
            )
    
    def open_log_folder(self):
        """Open the log folder in file explorer."""
        log_file = get_log_file_path()
        log_dir = log_file.parent
        
        if log_dir.exists():
            logger.info(f"Opening log folder: {log_dir}")
            try:
                os.startfile(str(log_dir))
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
        else:
            QMessageBox.information(self, "No Logs", "Log folder does not exist yet.")
    
    def clear_application_logs(self):
        """Clear all log files."""
        log_size = get_log_size()
        
        reply = QMessageBox.question(
            self,
            "Clear Logs",
            f"This will delete all log files ({format_size(log_size)}).\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            files_deleted, bytes_freed = clear_logs()
            logger.info(f"Logs cleared: {files_deleted} files, {format_size(bytes_freed)}")
            QMessageBox.information(
                self,
                "Logs Cleared",
                f"Deleted {files_deleted} file(s), freed {format_size(bytes_freed)}"
            )
    
    def _on_audio_position_changed(self, position_seconds: float):
        """Handle audio position change."""
        from src.models.transcript import format_timestamp
        self.position_label.setText(format_timestamp(position_seconds))
        
        # Highlight corresponding segment
        transcript = self.transcript_editor.get_transcript()
        if transcript:
            segment = transcript.get_segment_at_time(position_seconds)
            if segment:
                self.transcript_editor.highlight_segment(segment.id)
    
    def _on_audio_duration_changed(self, duration_seconds: float):
        """Handle audio duration change."""
        from src.models.transcript import format_timestamp
        self.duration_label.setText(f"/ {format_timestamp(duration_seconds)}")
    
    def _on_segment_clicked(self, segment):
        """Handle segment click - play that segment."""
        self.audio_player.play_segment(segment.start_time, segment.end_time)
    
    def _on_segment_edited(self, segment):
        """Handle segment edit."""
        self.is_modified = True
        if not self.windowTitle().endswith("*"):
            self.setWindowTitle(self.windowTitle() + " *")
        
        # Update statistics panel
        self.statistics_panel.update_statistics()
    
    def _enable_edit_actions(self, enabled: bool):
        """Enable or disable edit-related actions."""
        self.find_action.setEnabled(enabled)
        self.find_replace_action.setEnabled(enabled)
        self.toggle_bookmark_action.setEnabled(enabled)
        self.next_bookmark_action.setEnabled(enabled)
        self.prev_bookmark_action.setEnabled(enabled)
        self.set_speaker_label_action.setEnabled(enabled)
        self.next_low_conf_action.setEnabled(enabled)
        self.prev_low_conf_action.setEnabled(enabled)
        self.ai_polish_all_action.setEnabled(enabled)
        self.ai_polish_selected_action.setEnabled(enabled)
        self.ai_polish_range_action.setEnabled(enabled)
    
    def open_ai_settings(self):
        """Open AI settings dialog."""
        dialog = AISettingsDialog(self)
        dialog.exec()
    
    def open_ai_polish(self, mode: str = "all"):
        """Open AI polish dialog with specified mode.
        
        Args:
            mode: "all" for entire transcript, "selected" for selected lines,
                  "range" for time range selection
        """
        transcript = self.transcript_editor.get_transcript()
        if not transcript:
            QMessageBox.warning(self, "No Transcript", "Please load or create a transcript first.")
            return
        
        if not transcript.segments:
            QMessageBox.warning(self, "Empty Transcript", "The transcript has no segments to polish.")
            return
        
        # Get segments based on mode
        segments_to_polish = []
        segment_indices = []
        
        if mode == "selected":
            # Get selected rows from editor
            selected_indices = self.transcript_editor.get_selected_segment_indices()
            if not selected_indices:
                QMessageBox.information(
                    self, "No Selection", 
                    "Please select one or more lines in the transcript to polish."
                )
                return
            segment_indices = selected_indices
            segments_to_polish = [transcript.segments[i] for i in selected_indices if i < len(transcript.segments)]
            
        elif mode == "range":
            # Show time range dialog
            from src.ui.ai_polish_dialog import TimeRangeDialog
            range_dialog = TimeRangeDialog(
                audio_duration=self.audio_player.get_duration() if self.audio_player else 0,
                parent=self
            )
            if range_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            start_time, end_time = range_dialog.get_range()
            
            # Find segments in range
            for i, seg in enumerate(transcript.segments):
                if seg.start_time >= start_time and seg.end_time <= end_time:
                    segments_to_polish.append(seg)
                    segment_indices.append(i)
                elif seg.start_time < end_time and seg.end_time > start_time:
                    # Partially overlapping - include it
                    segments_to_polish.append(seg)
                    segment_indices.append(i)
            
            if not segments_to_polish:
                QMessageBox.information(
                    self, "No Segments",
                    f"No segments found in the time range {start_time:.1f}s - {end_time:.1f}s"
                )
                return
        else:
            # Polish all
            segments_to_polish = transcript.segments
            segment_indices = list(range(len(transcript.segments)))
        
        dialog = AIPolishDialog(
            transcript=transcript,
            segments_to_polish=segments_to_polish,
            segment_indices=segment_indices,
            parent=self
        )
        dialog.changes_applied.connect(self._on_ai_polish_applied)
        dialog.exec()
    
    def _on_ai_polish_applied(self):
        """Handle AI polish changes applied."""
        # Refresh the editor
        transcript = self.transcript_editor.get_transcript()
        if transcript:
            self.transcript_editor.set_transcript(transcript)
            self.is_modified = True
            self._update_window_title()
            self.stats_panel.update_stats(transcript)
            logger.info("AI polish changes applied to transcript")
    
    def open_find_replace(self):
        """Open find/replace dialog."""
        transcript = self.transcript_editor.get_transcript()
        if not transcript:
            return
        
        if self.find_replace_dialog is None:
            self.find_replace_dialog = FindReplaceDialog(transcript, self)
            self.find_replace_dialog.jump_to_segment.connect(self._on_segment_clicked)
            self.find_replace_dialog.text_replaced.connect(self._on_find_replace_changed)
        else:
            self.find_replace_dialog.set_transcript(transcript)
        
        self.find_replace_dialog.show()
        self.find_replace_dialog.raise_()
        self.find_replace_dialog.activateWindow()
    
    def _on_find_replace_changed(self):
        """Handle changes from find/replace dialog."""
        self.is_modified = True
        if not self.windowTitle().endswith("*"):
            self.setWindowTitle(self.windowTitle() + " *")
        
        # Refresh the table view
        self.transcript_editor.model.layoutChanged.emit()
        self.statistics_panel.update_statistics()
    
    def toggle_bookmark(self):
        """Toggle bookmark on selected segment."""
        segment = self.transcript_editor.get_selected_segment()
        if segment:
            transcript = self.transcript_editor.get_transcript()
            if transcript:
                transcript.toggle_bookmark(segment.id)
                self.transcript_editor.model.layoutChanged.emit()
                self.is_modified = True
                self.statistics_panel.update_statistics()
    
    def jump_to_next_bookmark(self):
        """Jump to next bookmarked segment."""
        transcript = self.transcript_editor.get_transcript()
        if not transcript:
            return
        
        bookmarked = transcript.get_bookmarked_segments()
        if not bookmarked:
            self.status_label.setText("No bookmarks found")
            return
        
        # Get current selection
        current_segment = self.transcript_editor.get_selected_segment()
        current_idx = -1
        if current_segment:
            current_idx = transcript.get_segment_index(current_segment.id)
        
        # Find next bookmark after current position
        for seg in transcript.segments[current_idx + 1:]:
            if seg.is_bookmarked:
                self.transcript_editor.highlight_segment(seg.id)
                row = transcript.get_segment_index(seg.id)
                self.transcript_editor.table_view.selectRow(row)
                self._on_segment_clicked(seg)
                return
        
        # Wrap around
        for seg in transcript.segments[:current_idx + 1]:
            if seg.is_bookmarked:
                self.transcript_editor.highlight_segment(seg.id)
                row = transcript.get_segment_index(seg.id)
                self.transcript_editor.table_view.selectRow(row)
                self._on_segment_clicked(seg)
                return
    
    def jump_to_prev_bookmark(self):
        """Jump to previous bookmarked segment."""
        transcript = self.transcript_editor.get_transcript()
        if not transcript:
            return
        
        bookmarked = transcript.get_bookmarked_segments()
        if not bookmarked:
            self.status_label.setText("No bookmarks found")
            return
        
        # Get current selection
        current_segment = self.transcript_editor.get_selected_segment()
        current_idx = len(transcript.segments)
        if current_segment:
            current_idx = transcript.get_segment_index(current_segment.id)
        
        # Find prev bookmark before current position
        for seg in reversed(transcript.segments[:current_idx]):
            if seg.is_bookmarked:
                self.transcript_editor.highlight_segment(seg.id)
                row = transcript.get_segment_index(seg.id)
                self.transcript_editor.table_view.selectRow(row)
                self._on_segment_clicked(seg)
                return
        
        # Wrap around
        for seg in reversed(transcript.segments[current_idx:]):
            if seg.is_bookmarked:
                self.transcript_editor.highlight_segment(seg.id)
                row = transcript.get_segment_index(seg.id)
                self.transcript_editor.table_view.selectRow(row)
                self._on_segment_clicked(seg)
                return
    
    def set_speaker_label(self):
        """Set speaker label for selected segment."""
        segment = self.transcript_editor.get_selected_segment()
        if not segment:
            QMessageBox.information(self, "Speaker Label", "Please select a segment first.")
            return
        
        label, ok = QInputDialog.getText(
            self,
            "Set Speaker Label",
            "Enter speaker label (e.g., 'ME', 'SPEAKER 1'):",
            text=segment.speaker_label
        )
        
        if ok:
            segment.speaker_label = label.strip()
            self.transcript_editor.model.layoutChanged.emit()
            self.is_modified = True
    
    def toggle_confidence_highlighting(self, checked: bool):
        """Toggle confidence highlighting in transcript."""
        self.transcript_editor.set_show_confidence(checked)
    
    def jump_to_next_low_confidence(self):
        """Jump to next low confidence segment."""
        segment = self.transcript_editor.jump_to_next_low_confidence()
        if segment:
            self.audio_player.play_segment(segment.start_time, segment.end_time)
        else:
            self.status_label.setText("No low confidence segments found")
    
    def jump_to_prev_low_confidence(self):
        """Jump to previous low confidence segment."""
        segment = self.transcript_editor.jump_to_prev_low_confidence()
        if segment:
            self.audio_player.play_segment(segment.start_time, segment.end_time)
        else:
            self.status_label.setText("No low confidence segments found")
    
    def toggle_statistics_panel(self, checked: bool):
        """Show or hide statistics panel."""
        if checked:
            self.stats_dock.show()
            transcript = self.transcript_editor.get_transcript()
            if transcript:
                self.statistics_panel.set_transcript(transcript)
        else:
            self.stats_dock.hide()
    
    def toggle_dark_mode(self, checked: bool):
        """Toggle dark mode theme."""
        theme = "dark" if checked else "light"
        self.settings.theme = theme
        
        try:
            theme_path = f"resources/themes/{theme}.qss"
            with open(theme_path, "r") as f:
                QApplication.instance().setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Theme file not found: {theme_path}")
        
        self.settings_manager.save()
    
    def closeEvent(self, event):
        """Handle window close."""
        if self.is_modified:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Save:
                self.save_project()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        
        # Save window state
        self.settings.window_width = self.width()
        self.settings.window_height = self.height()
        self.settings.window_maximized = self.isMaximized()
        self.settings.splitter_sizes = self.main_splitter.sizes()
        self.settings_manager.save()
        
        event.accept()
