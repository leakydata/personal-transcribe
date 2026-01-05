"""
Background worker for loading transcript JSON files.
"""

import json
import time
from PyQt6.QtCore import QThread, pyqtSignal
from src.utils.logger import get_logger
from src.models.transcript import Transcript, Segment, Word

logger = get_logger("transcript_loader")

class TranscriptLoaderWorker(QThread):
    """Worker thread for loading and parsing transcript files."""
    
    finished = pyqtSignal(object)  # Emits Transcript object or None
    error = pyqtSignal(str)        # Emits error message
    progress = pyqtSignal(str)     # Emits status message
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        
    def run(self):
        try:
            logger.info(f"Background loader starting for: {self.file_path}")
            self.progress.emit("Reading file...")
            
            start_time = time.time()
            
            # 1. Read JSON file
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            read_time = time.time() - start_time
            logger.debug(f"JSON load took {read_time:.2f}s")
            
            # 2. Parse segments
            raw_segments = data.get("segments", [])
            total_segments = len(raw_segments)
            self.progress.emit(f"Parsing {total_segments} segments...")
            
            segments = []
            
            # Optimization: Pre-allocate lists if possible or just efficient iteration
            for i, seg_data in enumerate(raw_segments):
                # Optional: Emit progress for very large files every 1000 segments
                if i % 1000 == 0 and i > 0:
                    self.progress.emit(f"Parsed {i}/{total_segments} segments...")
                
                words = []
                for word_data in seg_data.get("words", []):
                    words.append(Word(
                        text=word_data["text"],
                        start=word_data["start"],
                        end=word_data["end"],
                        confidence=word_data["confidence"]
                    ))
                
                segment = Segment(
                    id=seg_data["id"],
                    start_time=seg_data["start_time"],
                    end_time=seg_data["end_time"],
                    text=seg_data["text"],
                    words=words,
                    # Handle optional fields safely
                    speaker_label=seg_data.get("speaker_label", ""),
                    is_bookmarked=seg_data.get("is_bookmarked", False)
                )
                segments.append(segment)
            
            # 3. Create Transcript object
            self.progress.emit("Finalizing transcript...")
            
            transcript = Transcript(
                segments=segments,
                audio_duration=data.get("audio_duration", 0),
                audio_file=data.get("audio_file", ""),
                # Parse timestamps if available
            )
            
            # Handle timestamps if present in JSON
            # (Transcript.from_dict handles this usually, but we are doing manual parse for control)
            if "created_at" in data:
                from datetime import datetime
                try:
                    transcript.created_at = datetime.fromisoformat(data["created_at"])
                except:
                    pass
            
            if "modified_at" in data:
                from datetime import datetime
                try:
                    transcript.modified_at = datetime.fromisoformat(data["modified_at"])
                except:
                    pass
            
            total_time = time.time() - start_time
            logger.info(f"Background load complete: {len(segments)} segments in {total_time:.2f}s")
            
            self.finished.emit(transcript)
            
        except Exception as e:
            logger.error(f"Background load failed: {e}", exc_info=True)
            self.error.emit(str(e))
