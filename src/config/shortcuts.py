"""
Keyboard shortcuts configuration for PersonalTranscribe.
Centralized shortcut definitions for easy modification.
"""

from dataclasses import dataclass
from typing import Optional
from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import Qt


@dataclass
class Shortcut:
    """Represents a keyboard shortcut."""
    name: str
    key_sequence: str
    description: str
    category: str = "General"
    
    def to_key_sequence(self) -> QKeySequence:
        """Convert to Qt key sequence."""
        return QKeySequence(self.key_sequence)


class Shortcuts:
    """Central repository of all keyboard shortcuts."""
    
    # File operations
    OPEN_AUDIO = Shortcut("open_audio", "Ctrl+O", "Open audio file", "File")
    OPEN_PROJECT = Shortcut("open_project", "Ctrl+Shift+O", "Open project", "File")
    SAVE_PROJECT = Shortcut("save_project", "Ctrl+S", "Save project", "File")
    SAVE_PROJECT_AS = Shortcut("save_project_as", "Ctrl+Shift+S", "Save project as", "File")
    EXPORT_PDF = Shortcut("export_pdf", "Ctrl+E", "Export to PDF", "File")
    
    # Playback controls
    PLAY_PAUSE = Shortcut("play_pause", "Space", "Play/Pause", "Playback")
    STOP = Shortcut("stop", "Escape", "Stop playback", "Playback")
    SKIP_FORWARD = Shortcut("skip_forward", "Right", "Skip forward 5 seconds", "Playback")
    SKIP_BACKWARD = Shortcut("skip_backward", "Left", "Skip backward 5 seconds", "Playback")
    LOOP_SEGMENT = Shortcut("loop_segment", "L", "Loop current segment", "Playback")
    SPEED_UP = Shortcut("speed_up", "Ctrl+Right", "Increase playback speed", "Playback")
    SPEED_DOWN = Shortcut("speed_down", "Ctrl+Left", "Decrease playback speed", "Playback")
    REPLAY_5SEC = Shortcut("replay_5sec", "R", "Replay last 5 seconds", "Playback")
    
    # Navigation
    NEXT_SEGMENT = Shortcut("next_segment", "Down", "Go to next segment", "Navigation")
    PREV_SEGMENT = Shortcut("prev_segment", "Up", "Go to previous segment", "Navigation")
    NEXT_BOOKMARK = Shortcut("next_bookmark", "Ctrl+Down", "Go to next bookmark", "Navigation")
    PREV_BOOKMARK = Shortcut("prev_bookmark", "Ctrl+Up", "Go to previous bookmark", "Navigation")
    NEXT_LOW_CONFIDENCE = Shortcut("next_low_conf", "Ctrl+.", "Go to next low-confidence word", "Navigation")
    PREV_LOW_CONFIDENCE = Shortcut("prev_low_conf", "Ctrl+,", "Go to previous low-confidence word", "Navigation")
    GO_TO_TIME = Shortcut("go_to_time", "Ctrl+G", "Go to specific time", "Navigation")
    
    # Editing
    UNDO = Shortcut("undo", "Ctrl+Z", "Undo", "Edit")
    REDO = Shortcut("redo", "Ctrl+Y", "Redo", "Edit")
    FIND = Shortcut("find", "Ctrl+F", "Find", "Edit")
    FIND_REPLACE = Shortcut("find_replace", "Ctrl+H", "Find and replace", "Edit")
    TOGGLE_BOOKMARK = Shortcut("toggle_bookmark", "Ctrl+B", "Toggle bookmark on segment", "Edit")
    
    # Transcription
    START_TRANSCRIPTION = Shortcut("start_transcription", "Ctrl+T", "Start transcription", "Transcription")
    OPEN_VOCABULARY = Shortcut("open_vocabulary", "Ctrl+V", "Open vocabulary manager", "Transcription")
    
    # View
    TOGGLE_WAVEFORM = Shortcut("toggle_waveform", "Ctrl+W", "Toggle waveform view", "View")
    ZOOM_IN = Shortcut("zoom_in", "Ctrl+=", "Zoom in waveform", "View")
    ZOOM_OUT = Shortcut("zoom_out", "Ctrl+-", "Zoom out waveform", "View")
    TOGGLE_DARK_MODE = Shortcut("toggle_dark_mode", "Ctrl+D", "Toggle dark mode", "View")
    
    @classmethod
    def all_shortcuts(cls) -> list:
        """Get all defined shortcuts."""
        shortcuts = []
        for name in dir(cls):
            attr = getattr(cls, name)
            if isinstance(attr, Shortcut):
                shortcuts.append(attr)
        return shortcuts
    
    @classmethod
    def by_category(cls) -> dict:
        """Get shortcuts organized by category."""
        categories = {}
        for shortcut in cls.all_shortcuts():
            if shortcut.category not in categories:
                categories[shortcut.category] = []
            categories[shortcut.category].append(shortcut)
        return categories


def get_shortcut_key_sequence(shortcut: Shortcut) -> QKeySequence:
    """Get Qt key sequence for a shortcut."""
    return shortcut.to_key_sequence()
