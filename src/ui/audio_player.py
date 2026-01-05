"""
Audio player widget with waveform visualization for PersonalTranscribe.
"""

import numpy as np
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider,
    QLabel, QComboBox, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

import soundfile as sf
import pyqtgraph as pg


class WaveformWidget(pg.PlotWidget):
    """Widget to display audio waveform with click and drag seeking."""
    
    clicked = pyqtSignal(float)  # Position in seconds
    dragging = pyqtSignal(float)  # Position while dragging
    
    def __init__(self):
        super().__init__()
        
        self.audio_data: Optional[np.ndarray] = None
        self.sample_rate: int = 44100
        self.duration: float = 0.0
        self._is_dragging: bool = False
        
        # Configure plot
        self.setBackground('#fafafa')
        self.showGrid(x=True, y=False, alpha=0.3)
        self.setMouseEnabled(x=False, y=False)
        self.hideButtons()
        self.setMenuEnabled(False)
        
        # Hide axes labels
        self.getAxis('left').setStyle(showValues=False)
        self.getAxis('bottom').setStyle(showValues=True)
        self.setLabel('bottom', 'Time', units='s')
        
        # Waveform plot
        self.waveform_plot = self.plot(pen=pg.mkPen('#1976d2', width=1))
        
        # Playhead line
        self.playhead = pg.InfiniteLine(
            pos=0,
            angle=90,
            pen=pg.mkPen('#d32f2f', width=2)
        )
        self.addItem(self.playhead)
        
        # Segment highlight region
        self.segment_region = pg.LinearRegionItem(
            values=[0, 0],
            brush=pg.mkBrush('#bbdefb80'),
            pen=pg.mkPen('#1976d2', width=1),
            movable=False
        )
        self.segment_region.setVisible(False)
        self.addItem(self.segment_region)
        
        # Gap regions
        self.gap_regions = []
        
        # Taller for better visibility
        self.setFixedHeight(150)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def load_audio(self, file_path: str):
        """Load and display audio waveform."""
        try:
            # Read audio file
            data, self.sample_rate = sf.read(file_path)
            
            # Convert to mono if stereo
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)
            
            self.audio_data = data
            self.duration = len(data) / self.sample_rate
            
            # Downsample for display (max 10000 points for performance)
            target_points = min(10000, len(data))
            step = max(1, len(data) // target_points)
            display_data = data[::step]
            
            # Create time axis
            time_axis = np.linspace(0, self.duration, len(display_data))
            
            # Update plot
            self.waveform_plot.setData(time_axis, display_data)
            self.setXRange(0, self.duration)
            self.setYRange(-1, 1)
            
            # Reset playhead
            self.playhead.setPos(0)
            
        except Exception as e:
            print(f"Error loading audio for waveform: {e}")
    
    def set_position(self, seconds: float):
        """Update playhead position."""
        self.playhead.setPos(seconds)
    
    def highlight_segment(self, start: float, end: float):
        """Highlight a segment on the waveform."""
        self.segment_region.setRegion([start, end])
        self.segment_region.setVisible(True)
    
    def clear_highlight(self):
        """Clear segment highlight."""
        self.segment_region.setVisible(False)

    def show_gaps(self, gaps: list):
        """Display gaps on the waveform.
        
        Args:
            gaps: List of tuples (start, end) or Gap objects
        """
        self.clear_gaps()
        
        for gap in gaps:
            # Handle both Gap objects and tuples
            if hasattr(gap, 'start_time') and hasattr(gap, 'end_time'):
                start, end = gap.start_time, gap.end_time
            else:
                start, end = gap
                
            region = pg.LinearRegionItem(
                values=[start, end],
                brush=pg.mkBrush('#ffcdd280'),  # Light red, semi-transparent
                pen=pg.mkPen('#ef5350', width=0),  # No border or thin border
                movable=False
            )
            region.setZValue(-10)  # Behind other items
            self.addItem(region)
            self.gap_regions.append(region)

    def clear_gaps(self):
        """Remove all gap regions."""
        for region in self.gap_regions:
            self.removeItem(region)
        self.gap_regions = []
    
    def mousePressEvent(self, event):
        """Handle mouse click to start seeking."""
        from PyQt6.QtCore import QPointF
        if self.duration > 0 and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            # Convert QPoint to QPointF for pyqtgraph compatibility
            pos_f = QPointF(event.pos())
            pos = self.plotItem.vb.mapSceneToView(pos_f)
            click_time = max(0, min(pos.x(), self.duration))
            self.clicked.emit(click_time)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse drag to scrub through audio."""
        from PyQt6.QtCore import QPointF
        if self._is_dragging and self.duration > 0:
            # Convert QPoint to QPointF for pyqtgraph compatibility
            pos_f = QPointF(event.pos())
            pos = self.plotItem.vb.mapSceneToView(pos_f)
            drag_time = max(0, min(pos.x(), self.duration))
            self.dragging.emit(drag_time)
            self.playhead.setPos(drag_time)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to finish seeking."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
        super().mouseReleaseEvent(event)


class AudioPlayer(QWidget):
    """Audio player with waveform and transport controls."""
    
    position_changed = pyqtSignal(float)  # Current position in seconds
    duration_changed = pyqtSignal(float)  # Total duration in seconds
    
    def __init__(self):
        super().__init__()
        
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.duration_seconds: float = 0.0
        self.is_looping: bool = False
        self.loop_start: float = 0.0
        self.loop_end: float = 0.0
        
        self._init_ui()
        self._connect_signals()
        
        # Update timer for position
        self.position_timer = QTimer()
        self.position_timer.setInterval(50)  # 50ms updates
        self.position_timer.timeout.connect(self._update_position)
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Waveform
        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform)
        
        # Controls frame
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        
        # Play/Pause button
        self.play_button = QPushButton("Play")
        self.play_button.setMinimumWidth(80)
        self.play_button.clicked.connect(self.toggle_play)
        controls_layout.addWidget(self.play_button)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumWidth(70)
        self.stop_button.clicked.connect(self.stop)
        controls_layout.addWidget(self.stop_button)
        
        # Rewind button
        self.rewind_button = QPushButton("<<")
        self.rewind_button.setMinimumWidth(50)
        self.rewind_button.clicked.connect(lambda: self.skip(-5))
        controls_layout.addWidget(self.rewind_button)
        
        # Forward button
        self.forward_button = QPushButton(">>")
        self.forward_button.setMinimumWidth(50)
        self.forward_button.clicked.connect(lambda: self.skip(5))
        controls_layout.addWidget(self.forward_button)
        
        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self._on_slider_moved)
        self.position_slider.sliderPressed.connect(self._on_slider_pressed)
        self.position_slider.sliderReleased.connect(self._on_slider_released)
        controls_layout.addWidget(self.position_slider, 1)
        
        # Time label
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setFixedWidth(140)
        controls_layout.addWidget(self.time_label)
        
        # Speed selector
        speed_label = QLabel("Speed:")
        controls_layout.addWidget(speed_label)
        
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["0.5x", "0.75x", "1.0x", "1.25x", "1.5x", "2.0x"])
        self.speed_combo.setCurrentText("1.0x")
        self.speed_combo.currentTextChanged.connect(self._on_speed_changed)
        self.speed_combo.setFixedWidth(70)
        controls_layout.addWidget(self.speed_combo)
        
        # Loop button
        self.loop_button = QPushButton("Loop")
        self.loop_button.setCheckable(True)
        self.loop_button.setMinimumWidth(70)
        self.loop_button.clicked.connect(self._on_loop_toggled)
        controls_layout.addWidget(self.loop_button)
        
        layout.addWidget(controls_frame)
        
        # Initially disabled
        self._set_controls_enabled(False)
        
        self._slider_being_dragged = False
    
    def _connect_signals(self):
        """Connect player signals."""
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.player.positionChanged.connect(self._on_position_changed_internal)
        self.waveform.clicked.connect(self._on_waveform_clicked)
        self.waveform.dragging.connect(self._on_waveform_dragged)
    
    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable controls."""
        self.play_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)
        self.rewind_button.setEnabled(enabled)
        self.forward_button.setEnabled(enabled)
        self.position_slider.setEnabled(enabled)
        self.speed_combo.setEnabled(enabled)
        self.loop_button.setEnabled(enabled)
    
    def load_audio(self, file_path: str):
        """Load an audio file."""
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.waveform.load_audio(file_path)
        self._set_controls_enabled(True)
        self.play_button.setText("Play")
    
    def play(self):
        """Start playback."""
        self.player.play()
        self.position_timer.start()
    
    def pause(self):
        """Pause playback."""
        self.player.pause()
        self.position_timer.stop()
    
    def stop(self):
        """Stop playback."""
        self.player.stop()
        self.position_timer.stop()
        self.waveform.set_position(0)
        self.is_looping = False
        self.loop_button.setChecked(False)
        self.waveform.clear_highlight()
    
    def toggle_play(self):
        """Toggle play/pause."""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()
    
    def seek(self, position_seconds: float):
        """Seek to position in seconds."""
        position_ms = int(position_seconds * 1000)
        self.player.setPosition(position_ms)
        self.waveform.set_position(position_seconds)
    
    def skip(self, seconds: float):
        """Skip forward or backward."""
        current = self.player.position() / 1000.0
        new_pos = max(0, min(current + seconds, self.duration_seconds))
        self.seek(new_pos)
    
    def set_speed(self, rate: float):
        """Set playback speed."""
        self.player.setPlaybackRate(rate)
    
    def play_segment(self, start: float, end: float):
        """Play a specific segment."""
        self.loop_start = start
        self.loop_end = end
        self.is_looping = self.loop_button.isChecked()
        self.waveform.highlight_segment(start, end)
        self.seek(start)
        self.play()
    
    def replay_last_seconds(self, seconds: float = 5.0):
        """Replay the last N seconds of audio.
        
        Args:
            seconds: Number of seconds to go back
        """
        current = self.player.position() / 1000.0
        new_pos = max(0, current - seconds)
        self.seek(new_pos)
        self.play()
    
    def set_waveform_visible(self, visible: bool):
        """Show or hide the waveform."""
        self.waveform.setVisible(visible)

    def show_gaps(self, gaps: list):
        """Show gaps on waveform."""
        self.waveform.show_gaps(gaps)
    
    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self.duration_seconds = duration_ms / 1000.0
        self.duration_changed.emit(self.duration_seconds)
        self._update_time_label()
    
    def _on_playback_state_changed(self, state):
        """Handle playback state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")
    
    def _on_position_changed_internal(self, position_ms: int):
        """Handle internal position change."""
        position_seconds = position_ms / 1000.0
        
        # Check loop
        if self.is_looping and position_seconds >= self.loop_end:
            self.seek(self.loop_start)
            return
        
        # Check segment end (non-looping)
        if not self.is_looping and self.loop_end > 0 and position_seconds >= self.loop_end:
            self.pause()
            self.loop_end = 0
            self.waveform.clear_highlight()
    
    def _update_position(self):
        """Update position display."""
        position_ms = self.player.position()
        position_seconds = position_ms / 1000.0
        
        self.waveform.set_position(position_seconds)
        self.position_changed.emit(position_seconds)
        self._update_time_label()
        
        if not self._slider_being_dragged and self.duration_seconds > 0:
            slider_pos = int((position_seconds / self.duration_seconds) * 1000)
            self.position_slider.setValue(slider_pos)
    
    def _update_time_label(self):
        """Update the time display label."""
        from src.models.transcript import format_timestamp
        position = self.player.position() / 1000.0
        self.time_label.setText(
            f"{format_timestamp(position)} / {format_timestamp(self.duration_seconds)}"
        )
    
    def _on_slider_moved(self, value: int):
        """Handle slider movement."""
        if self.duration_seconds > 0:
            position = (value / 1000.0) * self.duration_seconds
            self.waveform.set_position(position)
    
    def _on_slider_pressed(self):
        """Handle slider press."""
        self._slider_being_dragged = True
    
    def _on_slider_released(self):
        """Handle slider release."""
        self._slider_being_dragged = False
        if self.duration_seconds > 0:
            value = self.position_slider.value()
            position = (value / 1000.0) * self.duration_seconds
            self.seek(position)
    
    def _on_speed_changed(self, text: str):
        """Handle speed change."""
        speed = float(text.replace("x", ""))
        self.set_speed(speed)
    
    def _on_loop_toggled(self, checked: bool):
        """Handle loop toggle."""
        self.is_looping = checked
    
    def _on_waveform_clicked(self, position: float):
        """Handle waveform click."""
        self.seek(position)
    
    def _on_waveform_dragged(self, position: float):
        """Handle waveform drag for scrubbing."""
        # Update position while dragging (real-time scrubbing)
        self.seek(position)
    
    def jump_to_time(self, seconds: float):
        """Jump to a specific time in seconds."""
        if 0 <= seconds <= self.duration_seconds:
            self.seek(seconds)
            return True
        return False
    
    def get_current_position(self) -> float:
        """Get current playback position in seconds."""
        return self.player.position() / 1000.0
    
    def get_duration(self) -> float:
        """Get total audio duration in seconds."""
        return self.duration_seconds