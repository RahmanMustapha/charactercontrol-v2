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
    
@dataclass(frozen=True)
class BodyState:
    """
    Semantic, body-relative interpretation of a Pose snapshot.
    Values are derived from raw segments and (where applicable) a calibration baseline.
    Downstream gesture/intent code should consume this, not raw Pose data.
    """
    # Torso orientation
    torso_lean_forward: float       # degrees; positive = leaning forward
    torso_lean_side: float          # degrees; positive = leaning to player's right
    torso_facing: float             # degrees; 0 = facing calibration forward direction

    # Vertical
    hip_height: float               # meters, world Z (raw)
    hip_height_normalized: float    # 0 = baseline; negative = crouching; positive = jumping

    # Hands (relative to same-side shoulder, in body frame)
    right_hand_above_shoulder: float  # meters; positive = raised above shoulder
    left_hand_above_shoulder: float
    right_hand_forward: float         # meters; positive = extended forward
    left_hand_forward: float

    # Feet
    feet_distance: float            # meters between feet
    right_foot_height: float        # meters above floor
    left_foot_height: float

    # Meta
    timestamp: float
    is_calibrated: bool             # False if no calibration baseline yet