"""
Statistics panel for PersonalTranscribe.
Displays transcript statistics like word count, duration, gaps, etc.
"""

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt

from src.models.transcript import Transcript, format_timestamp
from src.transcription.timestamp_utils import (
    format_duration, get_speaking_ratio, calculate_words_per_minute
)


class StatLabel(QWidget):
    """A label with title and value for displaying statistics."""
    
    def __init__(self, title: str, value: str = "-", parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #757575; font-size: 11px;")
        layout.addWidget(self.title_label)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str):
        """Update the displayed value."""
        self.value_label.setText(value)


class StatisticsPanel(QWidget):
    """Panel displaying transcript statistics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.transcript: Optional[Transcript] = None
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # Title
        title = QLabel("Transcript Statistics")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Main stats grid
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setSpacing(16)
        
        # Row 1: Duration stats
        self.duration_stat = StatLabel("Total Duration")
        stats_layout.addWidget(self.duration_stat, 0, 0)
        
        self.speaking_stat = StatLabel("Speaking Time")
        stats_layout.addWidget(self.speaking_stat, 0, 1)
        
        self.gap_time_stat = StatLabel("Gap Time")
        stats_layout.addWidget(self.gap_time_stat, 0, 2)
        
        # Row 2: Count stats
        self.segment_stat = StatLabel("Segments")
        stats_layout.addWidget(self.segment_stat, 1, 0)
        
        self.word_stat = StatLabel("Words")
        stats_layout.addWidget(self.word_stat, 1, 1)
        
        self.gap_count_stat = StatLabel("Gaps")
        stats_layout.addWidget(self.gap_count_stat, 1, 2)
        
        # Row 3: Rate stats
        self.wpm_stat = StatLabel("Words/Minute")
        stats_layout.addWidget(self.wpm_stat, 2, 0)
        
        self.avg_confidence_stat = StatLabel("Avg. Confidence")
        stats_layout.addWidget(self.avg_confidence_stat, 2, 1)
        
        self.low_confidence_stat = StatLabel("Low Confidence")
        stats_layout.addWidget(self.low_confidence_stat, 2, 2)
        
        layout.addWidget(stats_frame)
        
        # Speaking ratio bar
        ratio_group = QGroupBox("Speaking Ratio")
        ratio_layout = QVBoxLayout(ratio_group)
        
        self.speaking_ratio_bar = QProgressBar()
        self.speaking_ratio_bar.setRange(0, 100)
        self.speaking_ratio_bar.setValue(0)
        self.speaking_ratio_bar.setFormat("%v% speaking")
        self.speaking_ratio_bar.setTextVisible(True)
        ratio_layout.addWidget(self.speaking_ratio_bar)
        
        self.ratio_label = QLabel("Speaking: 0% | Gaps: 0%")
        self.ratio_label.setStyleSheet("color: #757575;")
        ratio_layout.addWidget(self.ratio_label)
        
        layout.addWidget(ratio_group)
        
        # Bookmarks summary
        bookmark_group = QGroupBox("Review Items")
        bookmark_layout = QHBoxLayout(bookmark_group)
        
        self.bookmarked_stat = StatLabel("Bookmarked", "0")
        bookmark_layout.addWidget(self.bookmarked_stat)
        
        self.needs_review_stat = StatLabel("Needs Review", "0")
        bookmark_layout.addWidget(self.needs_review_stat)
        
        layout.addWidget(bookmark_group)
        
        layout.addStretch()
    
    def set_transcript(self, transcript: Optional[Transcript]):
        """Set the transcript to display statistics for."""
        try:
            self.transcript = transcript
            self.update_statistics()
        except Exception as e:
            from src.utils.logger import get_logger
            logger = get_logger("statistics_panel")
            logger.error(f"Error updating statistics: {e}", exc_info=True)
    
    def update_statistics(self):
        """Update all statistics displays."""
        if not self.transcript:
            self._clear_stats()
            return
        
        t = self.transcript
        
        # Duration stats
        self.duration_stat.set_value(format_timestamp(t.audio_duration))
        self.speaking_stat.set_value(format_duration(t.total_speech_duration))
        self.gap_time_stat.set_value(format_duration(t.total_gap_duration))
        
        # Count stats
        self.segment_stat.set_value(str(t.segment_count))
        self.word_stat.set_value(f"{t.word_count:,}")
        
        gaps = t.get_gaps(threshold=0.5)
        self.gap_count_stat.set_value(str(len(gaps)))
        
        # Rate stats
        wpm = calculate_words_per_minute(t.segments, t.total_speech_duration)
        self.wpm_stat.set_value(f"{wpm:.0f}")
        
        # Average confidence
        if t.segments:
            avg_conf = sum(s.average_confidence for s in t.segments) / len(t.segments)
            self.avg_confidence_stat.set_value(f"{avg_conf:.0%}")
        else:
            self.avg_confidence_stat.set_value("-")
        
        # Low confidence count
        low_conf_segments = t.get_low_confidence_segments(threshold=0.8)
        self.low_confidence_stat.set_value(str(len(low_conf_segments)))
        
        # Speaking ratio
        if t.audio_duration > 0:
            speaking_ratio, gap_ratio = get_speaking_ratio(t.segments, t.audio_duration)
            self.speaking_ratio_bar.setValue(int(speaking_ratio))
            self.ratio_label.setText(
                f"Speaking: {speaking_ratio:.1f}% | Gaps: {gap_ratio:.1f}%"
            )
        else:
            self.speaking_ratio_bar.setValue(0)
            self.ratio_label.setText("Speaking: 0% | Gaps: 0%")
        
        # Bookmarks
        bookmarked = t.get_bookmarked_segments()
        self.bookmarked_stat.set_value(str(len(bookmarked)))
        self.needs_review_stat.set_value(str(len(low_conf_segments)))
    
    def _clear_stats(self):
        """Clear all statistics to default values."""
        self.duration_stat.set_value("-")
        self.speaking_stat.set_value("-")
        self.gap_time_stat.set_value("-")
        self.segment_stat.set_value("-")
        self.word_stat.set_value("-")
        self.gap_count_stat.set_value("-")
        self.wpm_stat.set_value("-")
        self.avg_confidence_stat.set_value("-")
        self.low_confidence_stat.set_value("-")
        self.bookmarked_stat.set_value("0")
        self.needs_review_stat.set_value("0")
        self.speaking_ratio_bar.setValue(0)
        self.ratio_label.setText("Speaking: 0% | Gaps: 0%")
