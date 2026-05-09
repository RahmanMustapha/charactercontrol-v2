"""
Shared pose data types used across sensors, interpreters, and replays.
Anything that produces or consumes body pose data should use these.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SegmentPose:
    """Position and orientation for a single body segment."""
    segment_id: int
    name: str
    position: tuple[float, float, float]      # (x, y, z) in meters, world frame
    quaternion: tuple[float, float, float, float]  # (w, x, y, z), unit quaternion


@dataclass
class Pose:
    """
    A complete body pose snapshot at one moment in time.
    Maps Xsens segment IDs (1..23) to their SegmentPose.
    """
    timestamp: float                                  # seconds since epoch
    sample_counter: int                               # MVN frame number
    segments: dict[int, SegmentPose] = field(default_factory=dict)

    def get(self, segment_id: int) -> Optional[SegmentPose]:
        """Convenience accessor; returns None if segment missing."""
        return self.segments.get(segment_id)

    def has_full_body(self) -> bool:
        """True if all 23 standard MVN body segments are present."""
        return len(self.segments) >= 23