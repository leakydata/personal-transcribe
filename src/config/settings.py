"""
Settings manager for PersonalTranscribe.
Handles application preferences, theme settings, and persistent configuration.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class Settings:
    """Application settings with defaults."""
    
    # Whisper settings
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"  # auto, cuda, or cpu
    whisper_compute_type: str = "auto"  # auto, float16, int8, int8_float16
    whisper_segment_mode: str = "natural"  # natural (short segments) or sentence (longer, complete sentences)
    
    # Audio settings
    playback_speed: float = 1.0
    skip_seconds: int = 5
    
    # UI settings
    theme: str = "light"
    font_size: int = 14
    show_confidence: bool = True
    gap_threshold: float = 0.5  # seconds
    
    # Editor settings
    auto_save_enabled: bool = False
    auto_save_interval: int = 60  # seconds
    
    # Export settings
    pdf_include_gaps: bool = True
    pdf_include_line_numbers: bool = True
    pdf_certification_text: str = ""
    
    # Window state
    window_width: int = 1400
    window_height: int = 900
    window_maximized: bool = False
    splitter_sizes: list = field(default_factory=lambda: [300, 600])
    
    # Recent files
    recent_files: list = field(default_factory=list)
    max_recent_files: int = 10
    
    # Vocabulary
    vocabulary_file: str = "resources/vocabulary.txt"


class SettingsManager:
    """Manages loading and saving application settings."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize settings manager.
        
        Args:
            config_path: Path to config file. Defaults to user's app data folder.
        """
        if config_path is None:
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            config_dir = Path(app_data) / "PersonalTranscribe"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path = config_dir / "settings.json"
        else:
            self.config_path = Path(config_path)
        
        self.settings = self.load()
    
    def load(self) -> Settings:
        """Load settings from config file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Create settings with loaded values, using defaults for missing keys
                return Settings(**{k: v for k, v in data.items() if hasattr(Settings, k)})
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading settings: {e}. Using defaults.")
                return Settings()
        return Settings()
    
    def save(self) -> None:
        """Save current settings to config file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.settings), f, indent=2)
        except IOError as e:
            print(f"Error saving settings: {e}")
    
    def add_recent_file(self, file_path: str) -> None:
        """Add a file to recent files list."""
        # Remove if already exists
        if file_path in self.settings.recent_files:
            self.settings.recent_files.remove(file_path)
        
        # Add to front
        self.settings.recent_files.insert(0, file_path)
        
        # Trim to max size
        self.settings.recent_files = self.settings.recent_files[:self.settings.max_recent_files]
        
        self.save()
    
    def get_recent_files(self) -> list:
        """Get list of recent files that still exist."""
        existing = [f for f in self.settings.recent_files if os.path.exists(f)]
        if len(existing) != len(self.settings.recent_files):
            self.settings.recent_files = existing
            self.save()
        return existing


# Global settings instance
_settings_manager: Optional[SettingsManager] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager.settings


def get_settings_manager() -> SettingsManager:
    """Get the global settings manager instance."""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager
