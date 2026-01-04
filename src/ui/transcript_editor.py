"""
Transcript editor widget for PersonalTranscribe.
Provides line-by-line editing with timestamp display and confidence highlighting.
"""

from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QStyledItemDelegate, QLineEdit, QAbstractItemView, QLabel,
    QCheckBox, QFrame, QStyle, QPushButton, QSpinBox, QApplication,
    QMenu, QDialog, QDialogButtonBox, QFormLayout, QDoubleSpinBox,
    QTextEdit, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, pyqtSignal,
    QVariant, QPersistentModelIndex, QSize, QRect
)
from PyQt6.QtGui import (
    QColor, QBrush, QFont, QPainter, QTextDocument,
    QAbstractTextDocumentLayout, QPalette, QTextOption
)

from src.models.transcript import Transcript, Segment, Word, format_timestamp_range


# Confidence thresholds and colors
CONFIDENCE_HIGH = 0.9      # Green/normal
CONFIDENCE_MEDIUM = 0.8    # Yellow warning
CONFIDENCE_LOW = 0.6       # Red warning

COLOR_HIGH_CONFIDENCE = "#212121"      # Normal dark text
COLOR_MEDIUM_CONFIDENCE = "#f57f17"    # Amber/orange
COLOR_LOW_CONFIDENCE = "#c62828"       # Red
BACKGROUND_MEDIUM_CONFIDENCE = "#fff8e1"  # Light amber
BACKGROUND_LOW_CONFIDENCE = "#ffebee"     # Light red

# Threshold for "large" transcripts that need simplified display
LARGE_TRANSCRIPT_THRESHOLD = 100


def get_word_confidence_html(segment: Segment, show_confidence: bool = True) -> str:
    """Generate HTML with color-coded words based on confidence.
    
    Args:
        segment: Segment with word-level confidence data
        show_confidence: Whether to apply confidence highlighting
        
    Returns:
        HTML string with styled words
    """
    if not show_confidence or not segment.words:
        return segment.display_text
    
    html_parts = []
    
    # Add speaker label if present
    if segment.speaker_label:
        html_parts.append(f'<span style="font-weight: bold;">{segment.speaker_label}:</span> ')
    
    for word in segment.words:
        if word.confidence >= CONFIDENCE_HIGH:
            # High confidence - normal text
            html_parts.append(word.text)
        elif word.confidence >= CONFIDENCE_MEDIUM:
            # Medium confidence - amber text with light background
            html_parts.append(
                f'<span style="color: {COLOR_MEDIUM_CONFIDENCE}; '
                f'background-color: {BACKGROUND_MEDIUM_CONFIDENCE}; '
                f'padding: 1px 2px; border-radius: 2px;" '
                f'title="Confidence: {word.confidence:.0%}">{word.text}</span>'
            )
        else:
            # Low confidence - red text with light background
            html_parts.append(
                f'<span style="color: {COLOR_LOW_CONFIDENCE}; '
                f'background-color: {BACKGROUND_LOW_CONFIDENCE}; '
                f'padding: 1px 2px; border-radius: 2px; font-weight: bold;" '
                f'title="Confidence: {word.confidence:.0%}">{word.text}</span>'
            )
    
    return " ".join(html_parts)


class TranscriptTableModel(QAbstractTableModel):
    """Table model for transcript segments."""
    
    COLUMNS = ["Time", "Text"]
    COL_TIME = 0
    COL_TEXT = 1
    
    # Gap threshold in seconds - gaps longer than this are highlighted
    GAP_THRESHOLD = 2.0
    
    def __init__(self):
        super().__init__()
        self.transcript: Optional[Transcript] = None
        self.highlighted_segment_id: Optional[str] = None
        self.show_confidence_highlighting: bool = True
        self.show_gaps: bool = True  # Show gap indicators
    
    def set_transcript(self, transcript: Transcript):
        """Set the transcript data."""
        self.beginResetModel()
        self.transcript = transcript
        self.endResetModel()
    
    def get_transcript(self) -> Optional[Transcript]:
        """Get the current transcript."""
        return self.transcript
    
    def rowCount(self, parent=QModelIndex()) -> int:
        if self.transcript is None:
            return 0
        return len(self.transcript.segments)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.COLUMNS[section]
            else:
                return section + 1
        return None
    
    def _get_gap_before_segment(self, row: int) -> float:
        """Get the gap duration before a segment (in seconds)."""
        if row == 0:
            # Gap at start of audio
            return self.transcript.segments[0].start_time
        else:
            prev_segment = self.transcript.segments[row - 1]
            curr_segment = self.transcript.segments[row]
            return curr_segment.start_time - prev_segment.end_time
    
    def _format_gap(self, gap_seconds: float) -> str:
        """Format a gap duration for display."""
        if gap_seconds >= 60:
            mins = int(gap_seconds // 60)
            secs = int(gap_seconds % 60)
            return f"[GAP {mins}m {secs}s]"
        else:
            return f"[GAP {gap_seconds:.0f}s]"
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self.transcript is None:
            return None
        
        row = index.row()
        col = index.column()
        
        if row >= len(self.transcript.segments):
            return None
        
        segment = self.transcript.segments[row]
        
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            if col == self.COL_TIME:
                time_str = format_timestamp_range(segment.start_time, segment.end_time)
                
                # Add gap indicator if there's a significant gap before this segment
                if self.show_gaps:
                    gap = self._get_gap_before_segment(row)
                    if gap >= self.GAP_THRESHOLD:
                        gap_str = self._format_gap(gap)
                        return f"{gap_str}\n{time_str}"
                
                return time_str
            elif col == self.COL_TEXT:
                return segment.display_text
        
        elif role == Qt.ItemDataRole.BackgroundRole:
            # Highlight current segment - use bright yellow for visibility in all themes
            if segment.id == self.highlighted_segment_id:
                return QBrush(QColor("#fff176"))  # Bright yellow - readable in light/dark
            # Highlight bookmarked segments
            if segment.is_bookmarked:
                return QBrush(QColor("#e8f5e9"))
            # Highlight segments with significant gaps (other party speaking)
            if self.show_gaps and col == self.COL_TIME:
                gap = self._get_gap_before_segment(row)
                if gap >= self.GAP_THRESHOLD:
                    return QBrush(QColor("#e3f2fd"))  # Light blue for gaps
            # Highlight low confidence segments
            if segment.average_confidence < 0.8:
                return QBrush(QColor("#fff8e1"))
        
        elif role == Qt.ItemDataRole.FontRole:
            if col == self.COL_TIME:
                font = QFont("Consolas", 10)
                return font
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            # CRITICAL: Set dark text color for highlighted segment (readable in any theme)
            if segment.id == self.highlighted_segment_id:
                return QBrush(QColor("#212121"))  # Dark text on yellow background
            if col == self.COL_TIME:
                return QBrush(QColor("#616161"))
        
        elif role == Qt.ItemDataRole.UserRole:
            # Return segment for custom handling
            return segment
        
        elif role == Qt.ItemDataRole.UserRole + 1:
            # Return HTML with confidence highlighting
            if col == self.COL_TEXT:
                return get_word_confidence_html(segment, self.show_confidence_highlighting)
        
        return None
    
    def set_show_confidence(self, show: bool):
        """Enable or disable confidence highlighting."""
        if self.show_confidence_highlighting != show:
            self.show_confidence_highlighting = show
            # Refresh all text cells
            if self.transcript:
                top_left = self.index(0, self.COL_TEXT)
                bottom_right = self.index(self.rowCount() - 1, self.COL_TEXT)
                self.dataChanged.emit(top_left, bottom_right)
    
    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or self.transcript is None:
            return False
        
        if role == Qt.ItemDataRole.EditRole and index.column() == self.COL_TEXT:
            row = index.row()
            if row < len(self.transcript.segments):
                self.transcript.segments[row].update_text(str(value))
                self.dataChanged.emit(index, index)
                return True
        
        return False
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        
        # Only text column is editable
        if index.column() == self.COL_TEXT:
            flags |= Qt.ItemFlag.ItemIsEditable
        
        return flags
    
    def highlight_segment(self, segment_id: str):
        """Highlight a segment by ID."""
        old_id = self.highlighted_segment_id
        self.highlighted_segment_id = segment_id
        
        # Find and refresh affected rows
        if self.transcript:
            for i, seg in enumerate(self.transcript.segments):
                if seg.id in (old_id, segment_id):
                    idx = self.index(i, 0)
                    idx2 = self.index(i, self.columnCount() - 1)
                    self.dataChanged.emit(idx, idx2)
    
    def get_segment_at_row(self, row: int) -> Optional[Segment]:
        """Get segment at a specific row."""
        if self.transcript and 0 <= row < len(self.transcript.segments):
            return self.transcript.segments[row]
        return None
    
    def get_row_for_segment(self, segment_id: str) -> int:
        """Get row index for a segment ID. Returns -1 if not found."""
        if self.transcript:
            for i, seg in enumerate(self.transcript.segments):
                if seg.id == segment_id:
                    return i
        return -1


class RichTextDelegate(QStyledItemDelegate):
    """Delegate for displaying and editing text with HTML formatting.
    
    Renders HTML for display (showing confidence highlighting) but
    provides plain text editing.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = QTextDocument()
    
    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Paint the cell with HTML rendering."""
        # Get the HTML content
        html = index.data(Qt.ItemDataRole.UserRole + 1)
        if html is None:
            html = index.data(Qt.ItemDataRole.DisplayRole) or ""
        
        # Setup painter
        painter.save()
        
        # Draw background (selection, alternating rows, etc.)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg:
                painter.fillRect(option.rect, bg)
        
        # Setup document for HTML rendering
        self._doc.setHtml(html)
        self._doc.setDefaultFont(option.font)
        self._doc.setTextWidth(option.rect.width() - 8)
        
        # Center vertically
        text_height = self._doc.size().height()
        y_offset = max(0, (option.rect.height() - text_height) / 2)
        
        # Translate and draw
        painter.translate(option.rect.left() + 4, option.rect.top() + y_offset)
        
        # Use appropriate text color
        ctx = QAbstractTextDocumentLayout.PaintContext()
        if option.state & QStyle.StateFlag.State_Selected:
            ctx.palette.setColor(QPalette.ColorRole.Text, option.palette.highlightedText().color())
        
        self._doc.documentLayout().draw(painter, ctx)
        
        painter.restore()
    
    def sizeHint(self, option, index: QModelIndex) -> QSize:
        """Calculate size hint based on HTML content."""
        html = index.data(Qt.ItemDataRole.UserRole + 1)
        if html is None:
            html = index.data(Qt.ItemDataRole.DisplayRole) or ""
        
        self._doc.setHtml(html)
        self._doc.setDefaultFont(option.font)
        self._doc.setTextWidth(option.rect.width() - 8 if option.rect.width() > 0 else 400)
        
        return QSize(
            int(self._doc.idealWidth()) + 8,
            max(40, int(self._doc.size().height()) + 8)
        )
    
    def createEditor(self, parent, option, index):
        """Create plain text editor for editing."""
        editor = QLineEdit(parent)
        editor.setFrame(False)
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor with plain text (not HTML)."""
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setText(str(value) if value else "")
    
    def setModelData(self, editor, model, index):
        """Save plain text back to model."""
        model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)


class TranscriptEditor(QWidget):
    """Widget for editing transcript with timestamps."""
    
    segment_clicked = pyqtSignal(object)  # Segment
    segment_edited = pyqtSignal(object)   # Segment
    
    # Pagination settings
    SEGMENTS_PER_PAGE = 100
    
    def __init__(self):
        super().__init__()
        self._simple_mode = False  # Whether we're in simplified display mode
        self._current_page = 0
        self._total_pages = 1
        self._full_transcript: Optional[Transcript] = None  # Store full transcript
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Table view
        self.table_view = QTableView()
        self.table_view.setObjectName("transcriptTable")
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.verticalHeader().setVisible(True)
        self.table_view.verticalHeader().setDefaultSectionSize(60)
        self.table_view.setWordWrap(True)
        
        # Model
        self.model = TranscriptTableModel()
        self.table_view.setModel(self.model)
        
        # Configure columns
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_view.setColumnWidth(0, 180)
        
        # Set delegate for rich text display and editing
        self.text_delegate = RichTextDelegate()
        self.table_view.setItemDelegateForColumn(1, self.text_delegate)
        
        # Connect signals
        self.table_view.clicked.connect(self._on_row_clicked)
        self.model.dataChanged.connect(self._on_data_changed)
        
        # Context menu for segment operations
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        
        layout.addWidget(self.table_view)
        
        # Pagination controls (hidden by default, shown for large transcripts)
        self.pagination_frame = QFrame()
        self.pagination_frame.setObjectName("paginationFrame")
        pagination_layout = QHBoxLayout(self.pagination_frame)
        pagination_layout.setContentsMargins(8, 4, 8, 4)
        
        self.first_page_btn = QPushButton("<<")
        self.first_page_btn.setFixedWidth(40)
        self.first_page_btn.clicked.connect(self._go_first_page)
        
        self.prev_page_btn = QPushButton("<")
        self.prev_page_btn.setFixedWidth(40)
        self.prev_page_btn.clicked.connect(self._go_prev_page)
        
        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setMinimumWidth(120)
        
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(1)
        self.page_spinbox.valueChanged.connect(self._on_page_changed)
        
        self.next_page_btn = QPushButton(">")
        self.next_page_btn.setFixedWidth(40)
        self.next_page_btn.clicked.connect(self._go_next_page)
        
        self.last_page_btn = QPushButton(">>")
        self.last_page_btn.setFixedWidth(40)
        self.last_page_btn.clicked.connect(self._go_last_page)
        
        self.segment_count_label = QLabel("0 segments")
        
        pagination_layout.addWidget(self.first_page_btn)
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(QLabel("Go to:"))
        pagination_layout.addWidget(self.page_spinbox)
        pagination_layout.addWidget(self.next_page_btn)
        pagination_layout.addWidget(self.last_page_btn)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.segment_count_label)
        
        self.pagination_frame.setVisible(False)  # Hidden by default
        layout.addWidget(self.pagination_frame)
    
    def load_transcript(self, transcript: Transcript):
        """Load a transcript for display/editing.
        
        For large transcripts (>100 segments), uses pagination and 
        simplified display mode to prevent crashes and improve performance.
        """
        from src.utils.logger import get_logger
        
        logger = get_logger("transcript_editor")
        
        segment_count = len(transcript.segments)
        logger.info(f"Loading transcript with {segment_count} segments")
        
        # Store full transcript for pagination
        self._full_transcript = transcript
        self._current_page = 0
        
        # Calculate pages
        self._total_pages = max(1, (segment_count + self.SEGMENTS_PER_PAGE - 1) // self.SEGMENTS_PER_PAGE)
        
        # CRITICAL: For large transcripts, use pagination and simplified display
        if segment_count > LARGE_TRANSCRIPT_THRESHOLD:
            logger.info(f"Large transcript - enabling pagination ({self._total_pages} pages)")
            self._enable_simple_mode()
            self._show_pagination(True)
            self._update_pagination_controls()
            # Load first page only
            self._load_page(0)
        else:
            self._disable_simple_mode()
            self._show_pagination(False)
            # Load all segments for small transcripts
            try:
                self.model.set_transcript(transcript)
                self.table_view.resizeRowsToContents()
                logger.info(f"Transcript loaded: {segment_count} segments")
            except Exception as e:
                logger.error(f"Error loading transcript: {e}", exc_info=True)
                raise
        
        self.segment_count_label.setText(f"{segment_count} segments total")
    
    def _enable_simple_mode(self):
        """Enable simplified display mode for large transcripts."""
        if self._simple_mode:
            return
        
        self._simple_mode = True
        
        # Disable confidence highlighting (uses expensive HTML rendering)
        self.model.show_confidence_highlighting = False
        
        # Use plain text delegate instead of rich text delegate
        self.table_view.setItemDelegateForColumn(
            TranscriptTableModel.COL_TEXT, 
            QStyledItemDelegate(self)
        )
        
        # Use fixed row height (larger for readability/editing)
        self.table_view.verticalHeader().setDefaultSectionSize(70)
        
        # Disable word wrap for performance
        self.table_view.setWordWrap(False)
    
    def _disable_simple_mode(self):
        """Disable simplified display mode (restore rich text)."""
        if not self._simple_mode:
            return
        
        self._simple_mode = False
        
        # Re-enable confidence highlighting
        self.model.show_confidence_highlighting = True
        
        # Restore rich text delegate
        self.table_view.setItemDelegateForColumn(1, self.text_delegate)
        
        # Restore settings
        self.table_view.verticalHeader().setDefaultSectionSize(60)
        self.table_view.setWordWrap(True)
    
    # ==================== PAGINATION METHODS ====================
    
    def _show_pagination(self, show: bool):
        """Show or hide pagination controls."""
        self.pagination_frame.setVisible(show)
    
    def _update_pagination_controls(self):
        """Update pagination controls based on current state."""
        self.page_label.setText(f"Page {self._current_page + 1} of {self._total_pages}")
        self.page_spinbox.setMaximum(self._total_pages)
        self.page_spinbox.blockSignals(True)
        self.page_spinbox.setValue(self._current_page + 1)
        self.page_spinbox.blockSignals(False)
        
        # Enable/disable navigation buttons
        self.first_page_btn.setEnabled(self._current_page > 0)
        self.prev_page_btn.setEnabled(self._current_page > 0)
        self.next_page_btn.setEnabled(self._current_page < self._total_pages - 1)
        self.last_page_btn.setEnabled(self._current_page < self._total_pages - 1)
    
    def _load_page(self, page: int):
        """Load a specific page of segments."""
        from src.utils.logger import get_logger
        logger = get_logger("transcript_editor")
        
        if not self._full_transcript:
            return
        
        # Clamp page number
        page = max(0, min(page, self._total_pages - 1))
        self._current_page = page
        
        # Calculate segment range for this page
        start_idx = page * self.SEGMENTS_PER_PAGE
        end_idx = min(start_idx + self.SEGMENTS_PER_PAGE, len(self._full_transcript.segments))
        
        logger.debug(f"Loading page {page + 1}: segments {start_idx + 1} to {end_idx}")
        
        # Create a subset transcript for this page
        page_segments = self._full_transcript.segments[start_idx:end_idx]
        page_transcript = Transcript(segments=page_segments)
        
        # Load into model
        try:
            self.model.set_transcript(page_transcript)
            self._update_pagination_controls()
            
            # Scroll to top of page
            if self.model.rowCount() > 0:
                self.table_view.scrollToTop()
                
        except Exception as e:
            logger.error(f"Error loading page {page + 1}: {e}", exc_info=True)
    
    def _go_first_page(self):
        """Navigate to first page."""
        self._load_page(0)
    
    def _go_prev_page(self):
        """Navigate to previous page."""
        self._load_page(self._current_page - 1)
    
    def _go_next_page(self):
        """Navigate to next page."""
        self._load_page(self._current_page + 1)
    
    def _go_last_page(self):
        """Navigate to last page."""
        self._load_page(self._total_pages - 1)
    
    def _on_page_changed(self, page: int):
        """Handle page spinbox change."""
        self._load_page(page - 1)  # Spinbox is 1-based
    
    def _get_page_for_segment(self, segment_id: str) -> int:
        """Get the page number containing a segment."""
        if not self._full_transcript:
            return 0
        for i, seg in enumerate(self._full_transcript.segments):
            if seg.id == segment_id:
                return i // self.SEGMENTS_PER_PAGE
        return 0
    
    # ==================== END PAGINATION METHODS ====================
    
    def set_transcript(self, transcript: Transcript):
        """Alias for load_transcript for compatibility."""
        self.load_transcript(transcript)
    
    def get_transcript(self) -> Optional[Transcript]:
        """Get the full transcript (not just current page)."""
        # Return full transcript if using pagination
        if self._full_transcript:
            return self._full_transcript
        return self.model.get_transcript()
    
    def highlight_segment(self, segment_id: str):
        """Highlight a segment and scroll to it.
        
        For paginated transcripts, navigates to the correct page first.
        """
        # For paginated transcripts, check if we need to change pages
        if self._full_transcript and self._total_pages > 1:
            target_page = self._get_page_for_segment(segment_id)
            if target_page != self._current_page:
                self._load_page(target_page)
        
        self.model.highlight_segment(segment_id)
        
        # Scroll to segment
        row = self.model.get_row_for_segment(segment_id)
        if row >= 0:
            index = self.model.index(row, 0)
            self.table_view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
    
    def get_selected_segment(self) -> Optional[Segment]:
        """Get the currently selected segment."""
        indexes = self.table_view.selectedIndexes()
        if indexes:
            row = indexes[0].row()
            return self.model.get_segment_at_row(row)
        return None
    
    def _on_row_clicked(self, index: QModelIndex):
        """Handle row click."""
        segment = self.model.get_segment_at_row(index.row())
        if segment:
            self.segment_clicked.emit(segment)
    
    def _on_data_changed(self, top_left: QModelIndex, bottom_right: QModelIndex, roles=None):
        """Handle data change."""
        # Emit signal for edited segment
        if top_left.column() == TranscriptTableModel.COL_TEXT:
            segment = self.model.get_segment_at_row(top_left.row())
            if segment:
                self.segment_edited.emit(segment)
    
    def set_show_confidence(self, show: bool):
        """Enable or disable confidence highlighting."""
        self.model.set_show_confidence(show)
        self.table_view.viewport().update()
    
    def get_low_confidence_segments(self, threshold: float = 0.8) -> List[Segment]:
        """Get segments with average confidence below threshold."""
        transcript = self.model.get_transcript()
        if not transcript:
            return []
        return [s for s in transcript.segments if s.average_confidence < threshold]
    
    def jump_to_next_low_confidence(self, from_row: int = -1) -> Optional[Segment]:
        """Jump to next segment with low confidence words.
        
        Args:
            from_row: Current row (-1 for start from current selection)
            
        Returns:
            Segment jumped to, or None if not found
        """
        transcript = self.model.get_transcript()
        if not transcript:
            return None
        
        # Get starting row
        if from_row < 0:
            selected = self.table_view.selectedIndexes()
            from_row = selected[0].row() if selected else -1
        
        # Search from next row
        for i in range(from_row + 1, len(transcript.segments)):
            segment = transcript.segments[i]
            if segment.average_confidence < CONFIDENCE_MEDIUM:
                # Select and scroll to this row
                index = self.model.index(i, 0)
                self.table_view.selectRow(i)
                self.table_view.scrollTo(index)
                self.segment_clicked.emit(segment)
                return segment
        
        # Wrap around to beginning
        for i in range(0, from_row + 1):
            segment = transcript.segments[i]
            if segment.average_confidence < CONFIDENCE_MEDIUM:
                index = self.model.index(i, 0)
                self.table_view.selectRow(i)
                self.table_view.scrollTo(index)
                self.segment_clicked.emit(segment)
                return segment
        
        return None
    
    def jump_to_prev_low_confidence(self, from_row: int = -1) -> Optional[Segment]:
        """Jump to previous segment with low confidence words.
        
        Args:
            from_row: Current row (-1 for start from current selection)
            
        Returns:
            Segment jumped to, or None if not found
        """
        transcript = self.model.get_transcript()
        if not transcript:
            return None
        
        # Get starting row
        if from_row < 0:
            selected = self.table_view.selectedIndexes()
            from_row = selected[0].row() if selected else len(transcript.segments)
        
        # Search backwards from previous row
        for i in range(from_row - 1, -1, -1):
            segment = transcript.segments[i]
            if segment.average_confidence < CONFIDENCE_MEDIUM:
                index = self.model.index(i, 0)
                self.table_view.selectRow(i)
                self.table_view.scrollTo(index)
                self.segment_clicked.emit(segment)
                return segment
        
        # Wrap around to end
        for i in range(len(transcript.segments) - 1, from_row - 1, -1):
            segment = transcript.segments[i]
            if segment.average_confidence < CONFIDENCE_MEDIUM:
                index = self.model.index(i, 0)
                self.table_view.selectRow(i)
                self.table_view.scrollTo(index)
                self.segment_clicked.emit(segment)
                return segment
        
        return None
    
    def get_selected_segment_indices(self) -> List[int]:
        """Get indices of all selected segments.
        
        Returns:
            List of segment indices that are selected
        """
        selected_rows = set()
        for index in self.table_view.selectedIndexes():
            row = index.row()
            # Map row to segment index (accounting for gaps if any)
            segment = self.model.get_segment_at_row(row)
            if segment:
                transcript = self.model.get_transcript()
                if transcript:
                    try:
                        seg_idx = transcript.segments.index(segment)
                        selected_rows.add(seg_idx)
                    except ValueError:
                        pass
        return sorted(list(selected_rows))
