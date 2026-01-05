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
    QColor, QBrush, QFont, QPainter, QPen, QTextDocument,
    QAbstractTextDocumentLayout, QPalette, QTextOption
)

from src.models.transcript import Transcript, Segment, Word, format_timestamp_range
from src.utils.logger import get_logger

logger = get_logger("transcript_editor")


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
            # Current segment uses BORDER now, not fill - so skip it here
            # Highlight bookmarked segments
            if segment.is_bookmarked:
                return QBrush(QColor("#4caf50"))  # Green - visible in both themes
            # Highlight segments with significant gaps (other party speaking)
            if self.show_gaps and col == self.COL_TIME:
                gap = self._get_gap_before_segment(row)
                if gap >= self.GAP_THRESHOLD:
                    return QBrush(QColor("#2196f3"))  # Bright blue for gaps
            # Highlight low confidence segments
            if segment.average_confidence < 0.8:
                return QBrush(QColor("#ffb74d"))  # Orange-amber for low confidence
        
        elif role == Qt.ItemDataRole.FontRole:
            if col == self.COL_TIME:
                font = QFont("Consolas", 10)
                return font
        
        elif role == Qt.ItemDataRole.ForegroundRole:
            # CRITICAL: Set contrasting text color for colored segments
            # (highlighted segment uses border now, so no special text color needed)
            if segment.is_bookmarked:
                return QBrush(QColor("#ffffff"))  # White text on green background
            # Time column with gaps
            if self.show_gaps and col == self.COL_TIME:
                gap = self._get_gap_before_segment(row)
                if gap >= self.GAP_THRESHOLD:
                    return QBrush(QColor("#ffffff"))  # White text on blue background
            # Low confidence - DON'T set foreground, let delegate handle it
            # This ensures text is readable in both light and dark modes
            # Time column uses muted color (but not for special segments)
            if col == self.COL_TIME:
                return QBrush(QColor("#9e9e9e"))  # Grey that works in both themes
        
        elif role == Qt.ItemDataRole.UserRole:
            # Return segment for custom handling
            return segment
        
        elif role == Qt.ItemDataRole.UserRole + 1:
            # Return HTML with confidence highlighting
            if col == self.COL_TEXT:
                return get_word_confidence_html(segment, self.show_confidence_highlighting)
        
        elif role == Qt.ItemDataRole.UserRole + 2:
            # Return True if this is the currently highlighted (playing) segment
            return segment.id == self.highlighted_segment_id
        
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


class TimeColumnDelegate(QStyledItemDelegate):
    """Delegate for Time column that properly renders background colors.
    
    Ensures highlighted segments show their background color even when
    QSS tries to override it. Uses orange BORDER for currently playing segment.
    """
    
    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Paint the cell with proper background color support."""
        painter.save()
        
        # Check if this is the currently highlighted (playing) segment
        is_highlighted = index.data(Qt.ItemDataRole.UserRole + 2) or False
        
        # Draw background - check model's BackgroundRole first
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg and isinstance(bg, QBrush):
                painter.fillRect(option.rect, bg)
        
        # Draw orange border for highlighted (playing) segment
        if is_highlighted and not (option.state & QStyle.StateFlag.State_Selected):
            pen = QPen(QColor("#ff6b35"))  # Bright orange
            pen.setWidth(3)
            painter.setPen(pen)
            # Draw border inside the rect (adjusted to not clip)
            border_rect = option.rect.adjusted(1, 1, -2, -2)
            painter.drawRect(border_rect)
        
        # Get text and foreground color
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        
        # Determine text color
        if option.state & QStyle.StateFlag.State_Selected:
            text_color = option.palette.highlightedText().color()
        else:
            fg = index.data(Qt.ItemDataRole.ForegroundRole)
            if fg and isinstance(fg, QBrush):
                text_color = fg.color()
            else:
                # Detect dark/light mode from background
                bg = index.data(Qt.ItemDataRole.BackgroundRole)
                if bg and isinstance(bg, QBrush):
                    bg_color = bg.color()
                else:
                    bg_color = option.palette.base().color()
                luminance = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
                text_color = QColor("#212121") if luminance >= 128 else QColor("#eaeaea")
        
        # Draw text
        painter.setPen(text_color)
        font = index.data(Qt.ItemDataRole.FontRole)
        if font:
            painter.setFont(font)
        
        # Draw with padding
        text_rect = option.rect.adjusted(8, 4, -8, -4)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
        
        painter.restore()


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
        
        # Check if this is the currently highlighted (playing) segment
        is_highlighted = index.data(Qt.ItemDataRole.UserRole + 2) or False
        
        # Setup painter
        painter.save()
        
        # Draw background (selection, alternating rows, etc.)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg:
                painter.fillRect(option.rect, bg)
        
        # Draw orange border for highlighted (playing) segment
        if is_highlighted and not (option.state & QStyle.StateFlag.State_Selected):
            pen = QPen(QColor("#ff6b35"))  # Bright orange
            pen.setWidth(3)
            painter.setPen(pen)
            # Draw border inside the rect (adjusted to not clip)
            border_rect = option.rect.adjusted(1, 1, -2, -2)
            painter.drawRect(border_rect)
        
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
        else:
            # Check if the model specifies a foreground color (e.g., for highlighted segments)
            fg = index.data(Qt.ItemDataRole.ForegroundRole)
            if fg and isinstance(fg, QBrush):
                ctx.palette.setColor(QPalette.ColorRole.Text, fg.color())
            else:
                # Detect dark mode by checking background luminance
                bg_color = option.palette.base().color()
                # Calculate luminance (0-255 scale, dark = low, light = high)
                luminance = (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000
                if luminance < 128:
                    # Dark mode - use light text
                    ctx.palette.setColor(QPalette.ColorRole.Text, QColor("#eaeaea"))
                else:
                    # Light mode - use dark text
                    ctx.palette.setColor(QPalette.ColorRole.Text, QColor("#212121"))
        
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
        """Create multi-line text editor with word wrapping."""
        editor = QTextEdit(parent)
        editor.setFrameStyle(QFrame.Shape.NoFrame)
        editor.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        editor.setAcceptRichText(False)  # Plain text only
        # Style for visibility
        editor.setStyleSheet("""
            QTextEdit {
                padding: 4px;
                background-color: palette(base);
                color: palette(text);
            }
        """)
        # Set minimum height based on row height
        editor.setMinimumHeight(option.rect.height())
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor with plain text (not HTML)."""
        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        editor.setPlainText(str(value) if value else "")
        # Move cursor to end
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        editor.setTextCursor(cursor)
    
    def setModelData(self, editor, model, index):
        """Save plain text back to model."""
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        """Make the editor fill the cell properly."""
        # Expand the editor to be at least the cell height, or larger for multi-line
        rect = option.rect
        # Add some extra height for comfortable editing
        min_height = max(rect.height(), 100)
        editor.setGeometry(rect.x(), rect.y(), rect.width(), min_height)


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
        self._pending_highlight: Optional[str] = None  # Segment ID to highlight after editing
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
        # Auto-resize rows to fit content (multi-line text)
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.verticalHeader().setMinimumSectionSize(60)
        self.table_view.setWordWrap(True)
        
        # Enable text elide mode for the table
        self.table_view.setTextElideMode(Qt.TextElideMode.ElideNone)
        
        # Model
        self.model = TranscriptTableModel()
        self.table_view.setModel(self.model)
        
        # Configure columns
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_view.setColumnWidth(0, 180)
        
        # Set delegate for Time column (ensures highlighting works)
        self.time_delegate = TimeColumnDelegate()
        self.table_view.setItemDelegateForColumn(0, self.time_delegate)
        
        # Set delegate for rich text display and editing
        self.text_delegate = RichTextDelegate()
        self.table_view.setItemDelegateForColumn(1, self.text_delegate)
        
        # Connect signals
        self.table_view.clicked.connect(self._on_row_clicked)
        self.model.dataChanged.connect(self._on_data_changed)
        
        # Connect to delegate's closeEditor to apply pending highlight after editing
        self.text_delegate.closeEditor.connect(self._on_editor_closed)
        
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
        try:
            segment_count = len(transcript.segments)
            logger.info(f"Loading transcript with {segment_count} segments")
            
            # Store full transcript for pagination
            self._full_transcript = transcript
            self._current_page = 0
            
            # Calculate pages
            self._total_pages = max(1, (segment_count + self.SEGMENTS_PER_PAGE - 1) // self.SEGMENTS_PER_PAGE)
            logger.debug(f"Pagination calculated: {self._total_pages} total pages")
            
            # CRITICAL: For large transcripts, use pagination and simplified display
            if segment_count > LARGE_TRANSCRIPT_THRESHOLD:
                logger.info(f"Large transcript ({segment_count} > {LARGE_TRANSCRIPT_THRESHOLD}) - enabling pagination")
                
                try:
                    self._enable_simple_mode()
                    logger.debug("Simple display mode enabled")
                    
                    self._show_pagination(True)
                    self._update_pagination_controls()
                    logger.debug("Pagination controls shown")
                    
                    # Load first page only
                    self._load_page(0)
                    logger.info("First page loaded successfully")
                except Exception as e:
                    logger.error(f"Error initializing pagination: {e}", exc_info=True)
                    raise
            else:
                logger.info("Small transcript - loading all segments normally")
                try:
                    self._disable_simple_mode()
                    self._show_pagination(False)
                    logger.debug("Simple mode disabled, pagination hidden")
                    
                    # Load all segments for small transcripts
                    self.model.set_transcript(transcript)
                    self.table_view.resizeRowsToContents()
                    logger.info(f"Transcript loaded into model: {segment_count} segments")
                except Exception as e:
                    logger.error(f"Error loading transcript into model: {e}", exc_info=True)
                    raise
            
            self.segment_count_label.setText(f"{segment_count} segments total")
            logger.info("load_transcript completed successfully")
            
        except Exception as e:
            logger.error(f"CRITICAL ERROR in load_transcript: {e}", exc_info=True)
            # Re-raise to ensure main_window sees it too
            raise
    
    def _enable_simple_mode(self):
        """Enable simplified display mode for large transcripts."""
        if self._simple_mode:
            return
            
        logger.debug("_enable_simple_mode: Starting")
        self._simple_mode = True
        
        # Disable confidence highlighting (uses expensive HTML rendering)
        self.model.show_confidence_highlighting = False
        logger.debug("_enable_simple_mode: Disabled confidence highlighting")
        
        # Use plain text delegate instead of rich text delegate
        try:
            # Create delegate first and PERSIST it to prevent garbage collection
            self._simple_delegate = QStyledItemDelegate(self)
            logger.debug("_enable_simple_mode: Created simple delegate (persisted)")
            
            # Apply delegate
            self.table_view.setItemDelegateForColumn(
                TranscriptTableModel.COL_TEXT, 
                self._simple_delegate
            )
            logger.debug("_enable_simple_mode: Applied simple delegate")
        except Exception as e:
            logger.error(f"_enable_simple_mode: Error setting delegate: {e}", exc_info=True)
            raise
        
        # Auto-resize rows to fit content
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        logger.debug("_enable_simple_mode: Set row height")
        
        # Keep word wrap enabled for readability
        self.table_view.setWordWrap(True)
        self.table_view.setTextElideMode(Qt.TextElideMode.ElideNone)
        logger.debug("_enable_simple_mode: Completed")
    
    def _disable_simple_mode(self):
        """Disable simplified display mode (restore rich text)."""
        if not self._simple_mode:
            return
        
        self._simple_mode = False
        
        # Re-enable confidence highlighting
        self.model.show_confidence_highlighting = True
        
        # Restore rich text delegate
        self.table_view.setItemDelegateForColumn(1, self.text_delegate)
        
        # Restore settings - auto-resize rows to fit content
        self.table_view.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_view.setWordWrap(True)
        self.table_view.setTextElideMode(Qt.TextElideMode.ElideNone)
    
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
        
        # Load into model with processEvents to prevent UI freeze
        try:
            # Process events before model update
            QApplication.processEvents()
            
            self.model.set_transcript(page_transcript)
            
            # Process events after model update
            QApplication.processEvents()
            
            self._update_pagination_controls()
            
            # Resize rows to fit wrapped content (only for current page, so it's fast)
            self.table_view.resizeRowsToContents()
            
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
        Skips all updates if user is currently editing to avoid disrupting their work.
        """
        is_editing = self.table_view.state() == QAbstractItemView.State.EditingState
        
        # If editing, DON'T update anything - this prevents the editor from closing
        # The highlight will catch up when editing finishes
        if is_editing:
            # Just store the pending highlight - it will be applied when editing ends
            self._pending_highlight = segment_id
            return
        
        # Clear any pending highlight
        self._pending_highlight = None
        
        # For paginated transcripts, check if we need to change pages
        if self._full_transcript and self._total_pages > 1:
            target_page = self._get_page_for_segment(segment_id)
            if target_page != self._current_page:
                self._load_page(target_page)
        
        # Update the model's highlight - this makes the row visually highlighted
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
    
    def _on_editor_closed(self, editor, hint):
        """Handle editor closed - apply any pending highlight."""
        if self._pending_highlight:
            segment_id = self._pending_highlight
            self._pending_highlight = None
            # Apply the pending highlight now that editing is done
            self.model.highlight_segment(segment_id)
    
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
    
    # ==================== CONTEXT MENU & SEGMENT OPERATIONS ====================
    
    def _show_context_menu(self, position):
        """Show context menu for segment operations."""
        menu = QMenu(self)
        
        selected_rows = self._get_selected_rows()
        
        # Merge action (requires 2+ segments selected)
        merge_action = menu.addAction("Merge Selected Segments")
        merge_action.setEnabled(len(selected_rows) >= 2)
        merge_action.triggered.connect(self._merge_selected_segments)
        
        menu.addSeparator()
        
        # Split action (requires 1 segment selected)
        split_action = menu.addAction("Split Segment...")
        split_action.setEnabled(len(selected_rows) == 1)
        split_action.triggered.connect(self._split_segment)
        
        menu.addSeparator()
        
        # Insert actions
        insert_before_action = menu.addAction("Insert Segment Before...")
        insert_before_action.setEnabled(len(selected_rows) >= 1)
        insert_before_action.triggered.connect(lambda: self._insert_segment(before=True))
        
        insert_after_action = menu.addAction("Insert Segment After...")
        insert_after_action.setEnabled(len(selected_rows) >= 1)
        insert_after_action.triggered.connect(lambda: self._insert_segment(before=False))
        
        menu.addSeparator()
        
        # Delete action
        delete_action = menu.addAction("Delete Selected Segment(s)")
        delete_action.setEnabled(len(selected_rows) >= 1)
        delete_action.triggered.connect(self._delete_selected_segments)
        
        menu.exec(self.table_view.viewport().mapToGlobal(position))
    
    def _get_selected_rows(self) -> List[int]:
        """Get list of selected row indices."""
        rows = set()
        for index in self.table_view.selectedIndexes():
            rows.add(index.row())
        return sorted(list(rows))
    
    def _merge_selected_segments(self):
        """Merge selected segments into one."""
        transcript = self.get_transcript()
        if not transcript:
            return
        
        selected_rows = self._get_selected_rows()
        if len(selected_rows) < 2:
            return
        
        # Get segments to merge (must be in current page view for paginated transcripts)
        segments_to_merge = []
        for row in selected_rows:
            segment = self.model.get_segment_at_row(row)
            if segment:
                segments_to_merge.append(segment)
        
        if len(segments_to_merge) < 2:
            return
        
        # Sort by start time
        segments_to_merge.sort(key=lambda s: s.start_time)
        
        # Create merged segment
        merged_text = " ".join(s.text.strip() for s in segments_to_merge)
        merged_words = []
        for s in segments_to_merge:
            merged_words.extend(s.words)
        
        merged_segment = Segment(
            id=segments_to_merge[0].id,
            start_time=segments_to_merge[0].start_time,
            end_time=segments_to_merge[-1].end_time,
            text=merged_text,
            words=merged_words,
            speaker_label=segments_to_merge[0].speaker_label,
            is_bookmarked=any(s.is_bookmarked for s in segments_to_merge)
        )
        
        # Update transcript: remove merged segments, insert new one
        for segment in segments_to_merge:
            if segment in transcript.segments:
                transcript.segments.remove(segment)
        
        # Find correct insert position
        insert_idx = 0
        for i, seg in enumerate(transcript.segments):
            if seg.start_time > merged_segment.start_time:
                insert_idx = i
                break
            insert_idx = i + 1
        
        transcript.segments.insert(insert_idx, merged_segment)
        
        # Refresh display
        self._refresh_after_edit()
        self.segment_edited.emit(merged_segment)
    
    def _split_segment(self):
        """Split a segment at a specified time."""
        selected_rows = self._get_selected_rows()
        if len(selected_rows) != 1:
            return
        
        segment = self.model.get_segment_at_row(selected_rows[0])
        if not segment:
            return
        
        # Show split dialog
        dialog = SplitSegmentDialog(segment, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            split_time = dialog.get_split_time()
            
            transcript = self.get_transcript()
            if not transcript:
                return
            
            # Create two new segments
            seg1_words = [w for w in segment.words if w.end <= split_time]
            seg2_words = [w for w in segment.words if w.start >= split_time]
            
            # Handle words spanning the split point
            for w in segment.words:
                if w.start < split_time < w.end:
                    # Word spans split - put in first segment
                    if w not in seg1_words:
                        seg1_words.append(w)
            
            seg1_text = " ".join(w.text for w in seg1_words) if seg1_words else segment.text[:len(segment.text)//2]
            seg2_text = " ".join(w.text for w in seg2_words) if seg2_words else segment.text[len(segment.text)//2:]
            
            import uuid
            segment1 = Segment(
                id=segment.id,
                start_time=segment.start_time,
                end_time=split_time,
                text=seg1_text.strip(),
                words=seg1_words,
                speaker_label=segment.speaker_label
            )
            
            segment2 = Segment(
                id=str(uuid.uuid4())[:8],
                start_time=split_time,
                end_time=segment.end_time,
                text=seg2_text.strip(),
                words=seg2_words,
                speaker_label=segment.speaker_label
            )
            
            # Replace original with two new segments
            idx = transcript.segments.index(segment)
            transcript.segments.remove(segment)
            transcript.segments.insert(idx, segment1)
            transcript.segments.insert(idx + 1, segment2)
            
            self._refresh_after_edit()
            self.segment_edited.emit(segment1)
    
    def _insert_segment(self, before: bool = True):
        """Insert a new segment before or after the selected segment."""
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return
        
        ref_row = selected_rows[0] if before else selected_rows[-1]
        ref_segment = self.model.get_segment_at_row(ref_row)
        if not ref_segment:
            return
        
        transcript = self.get_transcript()
        if not transcript:
            return
        
        # Determine time range for new segment
        ref_idx = transcript.segments.index(ref_segment)
        
        if before:
            # Insert before: time between previous segment and this one
            if ref_idx > 0:
                prev_seg = transcript.segments[ref_idx - 1]
                default_start = prev_seg.end_time
            else:
                default_start = 0.0
            default_end = ref_segment.start_time
        else:
            # Insert after: time between this segment and next one
            default_start = ref_segment.end_time
            if ref_idx < len(transcript.segments) - 1:
                next_seg = transcript.segments[ref_idx + 1]
                default_end = next_seg.start_time
            else:
                default_end = default_start + 5.0  # Default 5 seconds
        
        # Show insert dialog
        dialog = InsertSegmentDialog(default_start, default_end, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text, new_start, new_end = dialog.get_values()
            
            import uuid
            new_segment = Segment(
                id=str(uuid.uuid4())[:8],
                start_time=new_start,
                end_time=new_end,
                text=new_text,
                words=[],  # No word-level timestamps for manually added text
                speaker_label=""
            )
            
            # Insert at correct position
            insert_idx = ref_idx if before else ref_idx + 1
            transcript.segments.insert(insert_idx, new_segment)
            
            self._refresh_after_edit()
            self.segment_edited.emit(new_segment)
    
    def _delete_selected_segments(self):
        """Delete selected segments."""
        transcript = self.get_transcript()
        if not transcript:
            return
        
        selected_rows = self._get_selected_rows()
        if not selected_rows:
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Segments",
            f"Delete {len(selected_rows)} segment(s)?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Get segments to delete
        segments_to_delete = []
        for row in selected_rows:
            segment = self.model.get_segment_at_row(row)
            if segment:
                segments_to_delete.append(segment)
        
        # Remove from transcript
        for segment in segments_to_delete:
            if segment in transcript.segments:
                transcript.segments.remove(segment)
        
        self._refresh_after_edit()
        if segments_to_delete:
            self.segment_edited.emit(segments_to_delete[0])
    
    def _refresh_after_edit(self):
        """Refresh the display after editing segments."""
        transcript = self.get_transcript()
        if transcript:
            # Update pagination if needed
            self._full_transcript = transcript
            segment_count = len(transcript.segments)
            self._total_pages = max(1, (segment_count + self.SEGMENTS_PER_PAGE - 1) // self.SEGMENTS_PER_PAGE)
            
            if self._total_pages > 1:
                self._show_pagination(True)
                self._load_page(min(self._current_page, self._total_pages - 1))
            else:
                self._show_pagination(False)
                self.model.set_transcript(transcript)
            
            self.segment_count_label.setText(f"{segment_count} segments total")


class SplitSegmentDialog(QDialog):
    """Dialog for splitting a segment at a specific time."""
    
    def __init__(self, segment: Segment, parent=None):
        super().__init__(parent)
        self.segment = segment
        self.setWindowTitle("Split Segment")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        # Info label
        from src.models.transcript import format_timestamp
        info_text = (
            f"Segment: {format_timestamp(segment.start_time)} - {format_timestamp(segment.end_time)}\n"
            f"Text: {segment.text[:80]}{'...' if len(segment.text) > 80 else ''}"
        )
        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Split time input
        form_layout = QFormLayout()
        
        self.split_time_spinbox = QDoubleSpinBox()
        self.split_time_spinbox.setDecimals(2)
        self.split_time_spinbox.setSuffix(" sec")
        self.split_time_spinbox.setMinimum(segment.start_time + 0.1)
        self.split_time_spinbox.setMaximum(segment.end_time - 0.1)
        self.split_time_spinbox.setValue((segment.start_time + segment.end_time) / 2)
        form_layout.addRow("Split at time:", self.split_time_spinbox)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_split_time(self) -> float:
        return self.split_time_spinbox.value()


class InsertSegmentDialog(QDialog):
    """Dialog for inserting a new segment."""
    
    def __init__(self, default_start: float, default_end: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insert New Segment")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Time range inputs
        form_layout = QFormLayout()
        
        self.start_spinbox = QDoubleSpinBox()
        self.start_spinbox.setDecimals(2)
        self.start_spinbox.setSuffix(" sec")
        self.start_spinbox.setMinimum(0)
        self.start_spinbox.setMaximum(99999)
        self.start_spinbox.setValue(default_start)
        form_layout.addRow("Start time:", self.start_spinbox)
        
        self.end_spinbox = QDoubleSpinBox()
        self.end_spinbox.setDecimals(2)
        self.end_spinbox.setSuffix(" sec")
        self.end_spinbox.setMinimum(0)
        self.end_spinbox.setMaximum(99999)
        self.end_spinbox.setValue(default_end)
        form_layout.addRow("End time:", self.end_spinbox)
        
        layout.addLayout(form_layout)
        
        # Text input
        layout.addWidget(QLabel("Transcript text:"))
        self.text_edit = QTextEdit()
        self.text_edit.setMaximumHeight(100)
        self.text_edit.setPlaceholderText("Enter the missing transcript text here...")
        layout.addWidget(self.text_edit)
        
        # Tip
        tip_label = QLabel(
            "Tip: Listen to the audio at this time range to transcribe the missing text."
        )
        tip_label.setStyleSheet("color: gray; font-style: italic;")
        tip_label.setWordWrap(True)
        layout.addWidget(tip_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self) -> tuple:
        """Return (text, start_time, end_time)."""
        return (
            self.text_edit.toPlainText().strip(),
            self.start_spinbox.value(),
            self.end_spinbox.value()
        )