"""
Undo/Redo commands for PersonalTranscribe.
Implements QUndoCommand subclasses for transcript editing operations.
"""

from typing import Optional
from PyQt6.QtGui import QUndoCommand

from src.models.transcript import Segment, Transcript


class EditSegmentTextCommand(QUndoCommand):
    """Command for editing segment text."""
    
    def __init__(
        self,
        transcript: Transcript,
        segment_id: str,
        old_text: str,
        new_text: str,
        description: str = "Edit text"
    ):
        super().__init__(description)
        
        self.transcript = transcript
        self.segment_id = segment_id
        self.old_text = old_text
        self.new_text = new_text
    
    def redo(self):
        """Apply the edit."""
        segment = self.transcript.get_segment_by_id(self.segment_id)
        if segment:
            segment.update_text(self.new_text)
    
    def undo(self):
        """Revert the edit."""
        segment = self.transcript.get_segment_by_id(self.segment_id)
        if segment:
            segment.update_text(self.old_text)
    
    def mergeWith(self, other: QUndoCommand) -> bool:
        """Merge with another command if they edit the same segment."""
        if not isinstance(other, EditSegmentTextCommand):
            return False
        
        if other.segment_id != self.segment_id:
            return False
        
        # Merge by updating new_text to the other command's new_text
        self.new_text = other.new_text
        return True
    
    def id(self) -> int:
        """Return command ID for merging."""
        return 1  # All text edits can potentially merge


class ToggleBookmarkCommand(QUndoCommand):
    """Command for toggling segment bookmark."""
    
    def __init__(
        self,
        transcript: Transcript,
        segment_id: str,
        description: str = "Toggle bookmark"
    ):
        super().__init__(description)
        
        self.transcript = transcript
        self.segment_id = segment_id
    
    def redo(self):
        """Toggle the bookmark."""
        self.transcript.toggle_bookmark(self.segment_id)
    
    def undo(self):
        """Toggle back."""
        self.transcript.toggle_bookmark(self.segment_id)


class SetSpeakerLabelCommand(QUndoCommand):
    """Command for setting speaker label on a segment."""
    
    def __init__(
        self,
        transcript: Transcript,
        segment_id: str,
        old_label: str,
        new_label: str,
        description: str = "Set speaker label"
    ):
        super().__init__(description)
        
        self.transcript = transcript
        self.segment_id = segment_id
        self.old_label = old_label
        self.new_label = new_label
    
    def redo(self):
        """Apply the label."""
        segment = self.transcript.get_segment_by_id(self.segment_id)
        if segment:
            segment.speaker_label = self.new_label
    
    def undo(self):
        """Revert the label."""
        segment = self.transcript.get_segment_by_id(self.segment_id)
        if segment:
            segment.speaker_label = self.old_label


class BatchEditCommand(QUndoCommand):
    """Command for batch editing multiple segments."""
    
    def __init__(
        self,
        transcript: Transcript,
        edits: list,  # List of (segment_id, old_text, new_text)
        description: str = "Batch edit"
    ):
        super().__init__(description)
        
        self.transcript = transcript
        self.edits = edits
    
    def redo(self):
        """Apply all edits."""
        for segment_id, old_text, new_text in self.edits:
            segment = self.transcript.get_segment_by_id(segment_id)
            if segment:
                segment.update_text(new_text)
    
    def undo(self):
        """Revert all edits."""
        for segment_id, old_text, new_text in self.edits:
            segment = self.transcript.get_segment_by_id(segment_id)
            if segment:
                segment.update_text(old_text)


class ReplaceAllCommand(QUndoCommand):
    """Command for find/replace all operation."""
    
    def __init__(
        self,
        transcript: Transcript,
        replacements: list,  # List of (segment_id, old_text, new_text)
        search_term: str,
        replace_term: str,
        description: str = "Replace all"
    ):
        super().__init__(f'{description}: "{search_term}" -> "{replace_term}"')
        
        self.transcript = transcript
        self.replacements = replacements
        self.search_term = search_term
        self.replace_term = replace_term
    
    def redo(self):
        """Apply all replacements."""
        for segment_id, old_text, new_text in self.replacements:
            segment = self.transcript.get_segment_by_id(segment_id)
            if segment:
                segment.update_text(new_text)
    
    def undo(self):
        """Revert all replacements."""
        for segment_id, old_text, new_text in self.replacements:
            segment = self.transcript.get_segment_by_id(segment_id)
            if segment:
                segment.update_text(old_text)
