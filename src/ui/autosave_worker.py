"""
Background worker for auto-saving transcripts.
"""

from PyQt6.QtCore import QThread, pyqtSignal
from src.models.project import ProjectManager, Project
from src.utils.logger import logger

class AutosaveWorker(QThread):
    """Worker thread for saving projects in the background."""
    
    finished = pyqtSignal(bool, str)  # success, file_path_or_error
    
    def __init__(self, project: Project, save_path: str):
        super().__init__()
        self.project = project
        self.save_path = save_path
        
    def run(self):
        try:
            logger.info(f"Starting background autosave to: {self.save_path}")
            ProjectManager.save(self.project, self.save_path)
            self.finished.emit(True, self.save_path)
            logger.info("Background autosave complete")
        except Exception as e:
            logger.error(f"Background autosave failed: {e}", exc_info=True)
            self.finished.emit(False, str(e))
