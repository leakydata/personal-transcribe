"""
PersonalTranscribe - Voice Transcription Application
Main entry point for the application.
"""

import sys
import warnings

# Suppress harmless warnings from third-party libraries
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
warnings.filterwarnings("ignore", message=".*invalid escape sequence.*")

from PyQt6.QtWidgets import QApplication
from src.utils.logger import setup_logging, get_logger
from src.ui.main_window import MainWindow


def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception handler to log uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger = get_logger("main")
    logger.critical("Uncaught exception!", exc_info=(exc_type, exc_value, exc_traceback))


def main():
    """Launch the PersonalTranscribe application."""
    # Initialize logging first
    setup_logging()
    logger = get_logger("main")
    
    # Install global exception handler
    sys.excepthook = exception_hook
    
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("PersonalTranscribe")
        app.setOrganizationName("PersonalTranscribe")
        
        logger.info("Application starting...")
        
        # Load stylesheet
        try:
            with open("resources/themes/light.qss", "r") as f:
                app.setStyleSheet(f.read())
                logger.debug("Loaded light theme stylesheet")
        except FileNotFoundError:
            logger.debug("Theme stylesheet not found, using defaults")
        
        window = MainWindow()
        window.show()
        logger.info("Main window displayed")
        
        exit_code = app.exec()
        logger.info(f"Application exiting with code {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
