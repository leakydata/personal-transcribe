"""
Logging utility for PersonalTranscribe.
Provides file and console logging with rotation and clear functionality.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


# Global logger instance
_logger: Optional[logging.Logger] = None
_log_file_path: Optional[Path] = None


def get_log_directory() -> Path:
    """Get the log directory path."""
    # Store logs in user's app data directory
    if sys.platform == "win32":
        app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        log_dir = Path(app_data) / "PersonalTranscribe" / "logs"
    else:
        log_dir = Path.home() / ".personaltranscribe" / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_file_path() -> Path:
    """Get the current log file path."""
    global _log_file_path
    if _log_file_path is None:
        log_dir = get_log_directory()
        _log_file_path = log_dir / "app.log"
    return _log_file_path


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Setup application logging.
    
    Args:
        level: Logging level (default DEBUG for development)
        
    Returns:
        Configured logger instance
    """
    global _logger
    
    if _logger is not None:
        return _logger
    
    # Create logger
    _logger = logging.getLogger("PersonalTranscribe")
    _logger.setLevel(level)
    
    # Prevent duplicate handlers
    if _logger.handlers:
        return _logger
    
    # Log format
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s.%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    _logger.addHandler(console_handler)
    
    # File handler with rotation (5 MB max, keep 3 backups)
    log_file = get_log_file_path()
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    _logger.addHandler(file_handler)
    
    # Log startup
    _logger.info("=" * 60)
    _logger.info(f"PersonalTranscribe started at {datetime.now().isoformat()}")
    _logger.info(f"Log file: {log_file}")
    _logger.info(f"Python: {sys.version}")
    _logger.info(f"Platform: {sys.platform}")
    _logger.info("=" * 60)
    
    return _logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Optional sub-logger name (e.g., "transcription")
        
    Returns:
        Logger instance
    """
    global _logger
    
    if _logger is None:
        setup_logging()
    
    if name:
        return _logger.getChild(name)
    return _logger


def clear_logs() -> tuple:
    """Clear all log files.
    
    Returns:
        Tuple of (files_deleted, bytes_freed)
    """
    log_dir = get_log_directory()
    files_deleted = 0
    bytes_freed = 0
    
    for log_file in log_dir.glob("*.log*"):
        try:
            size = log_file.stat().st_size
            log_file.unlink()
            files_deleted += 1
            bytes_freed += size
        except Exception as e:
            print(f"Could not delete {log_file}: {e}")
    
    # Reinitialize logging after clearing
    global _logger
    if _logger:
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)
        _logger = None
    
    # Setup fresh logger
    setup_logging()
    get_logger().info("Logs cleared by user")
    
    return files_deleted, bytes_freed


def get_log_size() -> int:
    """Get total size of log files in bytes."""
    log_dir = get_log_directory()
    total_size = 0
    
    for log_file in log_dir.glob("*.log*"):
        try:
            total_size += log_file.stat().st_size
        except Exception:
            pass
    
    return total_size


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def log_exception(logger: logging.Logger, message: str, exc: Exception) -> None:
    """Log an exception with full traceback.
    
    Args:
        logger: Logger instance
        message: Context message
        exc: Exception to log
    """
    import traceback
    logger.error(f"{message}: {exc}")
    logger.debug(f"Traceback:\n{traceback.format_exc()}")
