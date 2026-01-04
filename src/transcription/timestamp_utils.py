"""
Timestamp utilities for PersonalTranscribe.
Provides time formatting, gap detection, and duration calculations.
"""

from typing import List, Tuple, Optional
from src.models.transcript import Segment, Gap, format_timestamp, format_timestamp_range


def detect_gaps(
    segments: List[Segment],
    audio_duration: float,
    threshold: float = 0.5
) -> List[Gap]:
    """Detect gaps between segments.
    
    Args:
        segments: List of transcript segments (should be sorted by start_time)
        audio_duration: Total audio duration in seconds
        threshold: Minimum gap duration to detect (seconds)
        
    Returns:
        List of Gap objects
    """
    if not segments:
        if audio_duration > threshold:
            return [Gap(start_time=0.0, end_time=audio_duration, after_segment_id="")]
        return []
    
    gaps = []
    
    # Gap at the beginning
    if segments[0].start_time > threshold:
        gaps.append(Gap(
            start_time=0.0,
            end_time=segments[0].start_time,
            after_segment_id=""
        ))
    
    # Gaps between segments
    for i in range(len(segments) - 1):
        current = segments[i]
        next_seg = segments[i + 1]
        gap_duration = next_seg.start_time - current.end_time
        
        if gap_duration >= threshold:
            gaps.append(Gap(
                start_time=current.end_time,
                end_time=next_seg.start_time,
                after_segment_id=current.id
            ))
    
    # Gap at the end
    if segments:
        last_end = segments[-1].end_time
        if audio_duration - last_end > threshold:
            gaps.append(Gap(
                start_time=last_end,
                end_time=audio_duration,
                after_segment_id=segments[-1].id
            ))
    
    return gaps


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "5.2 sec" or "2 min 30 sec"
    """
    if seconds < 60:
        return f"{seconds:.1f} sec"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        if secs > 0:
            return f"{minutes} min {secs:.0f} sec"
        return f"{minutes} min"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        if minutes > 0:
            return f"{hours} hr {minutes} min"
        return f"{hours} hr"


def format_gap_description(gap: Gap) -> str:
    """Format a gap as a descriptive string.
    
    Args:
        gap: Gap object
        
    Returns:
        Description like "[Gap: 5.2 sec]"
    """
    return f"[Gap: {format_duration(gap.duration)}]"


def get_speaking_ratio(
    segments: List[Segment],
    audio_duration: float
) -> Tuple[float, float]:
    """Calculate the ratio of speaking time to total time.
    
    Args:
        segments: List of transcript segments
        audio_duration: Total audio duration
        
    Returns:
        Tuple of (speaking_ratio, gap_ratio) as percentages
    """
    if audio_duration <= 0:
        return (0.0, 0.0)
    
    speaking_time = sum(s.duration for s in segments)
    speaking_ratio = (speaking_time / audio_duration) * 100
    gap_ratio = 100 - speaking_ratio
    
    return (speaking_ratio, gap_ratio)


def find_segment_at_time(
    segments: List[Segment],
    time_seconds: float
) -> Optional[Segment]:
    """Find the segment containing a specific time.
    
    Args:
        segments: List of segments to search
        time_seconds: Time in seconds
        
    Returns:
        Segment containing the time, or None
    """
    for segment in segments:
        if segment.start_time <= time_seconds <= segment.end_time:
            return segment
    return None


def find_nearest_segment(
    segments: List[Segment],
    time_seconds: float
) -> Optional[Segment]:
    """Find the nearest segment to a specific time.
    
    Args:
        segments: List of segments to search
        time_seconds: Time in seconds
        
    Returns:
        Nearest segment, or None if no segments
    """
    if not segments:
        return None
    
    # First check if we're inside a segment
    for segment in segments:
        if segment.start_time <= time_seconds <= segment.end_time:
            return segment
    
    # Find nearest by start time
    nearest = min(
        segments,
        key=lambda s: min(abs(s.start_time - time_seconds), abs(s.end_time - time_seconds))
    )
    return nearest


def calculate_words_per_minute(
    segments: List[Segment],
    total_speaking_time: Optional[float] = None
) -> float:
    """Calculate average words per minute.
    
    Args:
        segments: List of transcript segments
        total_speaking_time: If provided, use this instead of calculating
        
    Returns:
        Words per minute
    """
    if not segments:
        return 0.0
    
    total_words = sum(len(s.text.split()) for s in segments)
    
    if total_speaking_time is None:
        total_speaking_time = sum(s.duration for s in segments)
    
    if total_speaking_time <= 0:
        return 0.0
    
    # Convert seconds to minutes
    minutes = total_speaking_time / 60
    return total_words / minutes


def merge_segments(seg1: Segment, seg2: Segment) -> Segment:
    """Merge two consecutive segments into one.
    
    Args:
        seg1: First segment
        seg2: Second segment (should come after seg1)
        
    Returns:
        Merged segment
    """
    merged_text = f"{seg1.text} {seg2.text}"
    merged_words = seg1.words + seg2.words
    
    return Segment(
        id=seg1.id,
        start_time=seg1.start_time,
        end_time=seg2.end_time,
        text=merged_text,
        words=merged_words,
        speaker_label=seg1.speaker_label,
        is_bookmarked=seg1.is_bookmarked or seg2.is_bookmarked
    )


def split_segment(
    segment: Segment,
    split_time: float
) -> Tuple[Segment, Segment]:
    """Split a segment at a specific time.
    
    Args:
        segment: Segment to split
        split_time: Time at which to split (in seconds)
        
    Returns:
        Tuple of (first_part, second_part)
    """
    # Split words
    words_before = [w for w in segment.words if w.end <= split_time]
    words_after = [w for w in segment.words if w.start >= split_time]
    
    # Build text from words, or split by proportion if no word data
    if words_before and words_after:
        text_before = " ".join(w.text for w in words_before)
        text_after = " ".join(w.text for w in words_after)
    else:
        # Simple proportional split
        proportion = (split_time - segment.start_time) / segment.duration
        words = segment.text.split()
        split_idx = int(len(words) * proportion)
        text_before = " ".join(words[:split_idx])
        text_after = " ".join(words[split_idx:])
    
    first = Segment(
        id=segment.id,
        start_time=segment.start_time,
        end_time=split_time,
        text=text_before,
        words=words_before,
        speaker_label=segment.speaker_label,
        is_bookmarked=segment.is_bookmarked
    )
    
    second = Segment(
        id=Segment.generate_id(),
        start_time=split_time,
        end_time=segment.end_time,
        text=text_after,
        words=words_after,
        speaker_label=segment.speaker_label,
        is_bookmarked=False
    )
    
    return (first, second)
