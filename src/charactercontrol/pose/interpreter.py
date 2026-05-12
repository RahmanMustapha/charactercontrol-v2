"""
Convert raw Pose snapshots into semantic BodyState.
Stateless beyond an optional calibration baseline.
"""

from dataclasses import dataclass
from typing import Optional

from charactercontrol.pose.types import Pose, BodyState
from charactercontrol.pose import math_utils as m


# Xsens segment IDs we care about for interpretation.
PELVIS = 1
T8 = 5  # upper torso reference
HEAD = 7
RIGHT_SHOULDER = 8
RIGHT_HAND = 11
LEFT_SHOULDER = 12
LEFT_HAND = 15
RIGHT_FOOT = 18
LEFT_FOOT = 22


@dataclass
class CalibrationBaseline:
    """
    Reference values captured during calibration.
    Used to express measurements relative to the player's body.
    """
    standing_hip_height: float        # meters, world Z of pelvis at rest
    facing_yaw_offset: float          # degrees; subtract from torso yaw to get "0 = forward"
    head_height: float                # meters, world Z of head at rest
    floor_z: float                    # meters; average of foot Z at calibration
    shoulder_width: float             # meters; distance between shoulders
    arm_length: float                 # meters; shoulder to hand at rest, averaged
    player_height: float              # meters; head_height - floor_z

class PoseInterpreter:
    """
    Stateless interpreter (aside from optional calibration).
    
    Usage:
        interpreter = PoseInterpreter()
        # ... later, after calibration:
        interpreter.set_baseline(baseline)
        # Each frame:
        state = interpreter.interpret(pose)
    """

    def __init__(self) -> None:
        self._baseline: Optional[CalibrationBaseline] = None

    def set_baseline(self, baseline: CalibrationBaseline) -> None:
        self._baseline = baseline

    def interpret(self, pose: Pose) -> Optional[BodyState]:
        """
        Compute a BodyState from a Pose. Returns None if essential segments missing.
        """
        # Required segments — bail if anything critical is missing.
        required = (PELVIS, T8, RIGHT_SHOULDER, RIGHT_HAND,
                    LEFT_SHOULDER, LEFT_HAND, RIGHT_FOOT, LEFT_FOOT)
        for seg_id in required:
            if pose.get(seg_id) is None:
                return None

        pelvis = pose.get(PELVIS)
        t8 = pose.get(T8)
        r_shoulder = pose.get(RIGHT_SHOULDER)
        r_hand = pose.get(RIGHT_HAND)
        l_shoulder = pose.get(LEFT_SHOULDER)
        l_hand = pose.get(LEFT_HAND)
        r_foot = pose.get(RIGHT_FOOT)
        l_foot = pose.get(LEFT_FOOT)

        # First, extract yaw in world frame (this is "which way the body is facing").
        world_yaw, _, _ = m.quat_to_euler_zyx(t8.quaternion)

        # Construct a yaw-only quaternion and conjugate it to "remove" facing direction.
        # The remaining rotation is the body's pitch/roll in its own local frame.
        yaw_only = m.quat_yaw_only(world_yaw)
        yaw_inverse = m.quat_conjugate(yaw_only)
        body_local_quat = m.quat_multiply(yaw_inverse, t8.quaternion)

        # Now extract Euler angles from body-local quaternion.
        # Yaw of this should be ~0; pitch and roll are pure body-relative tilt.
        _, pitch, roll = m.quat_to_euler_zyx(body_local_quat)

        # Keep `yaw` for facing logic below
        yaw = world_yaw


        # Subtract calibration yaw offset if available, so 0 = "facing forward at calibration"
        if self._baseline is not None:
            facing = _normalize_angle(yaw - self._baseline.facing_yaw_offset)
        else:
            facing = yaw

        # MVN reports left-turn as positive yaw (right-handed Z-up convention).
        # Flip so that positive = right turn, matching game/UI conventions.
        facing = -facing

        # In Xsens default (Z-up, X-forward at calibration), "leaning forward" = pitch,
        # "leaning sideways" = roll. Sign conventions verified empirically below.
        torso_lean_forward = pitch
        torso_lean_side = roll

        # ---- Vertical / crouch ----
        hip_z = pelvis.position[2]
        if self._baseline is not None:
            hip_height_normalized = hip_z - self._baseline.standing_hip_height
        else:
            hip_height_normalized = 0.0

        # ---- Hand-relative-to-shoulder, expressed in body frame ----
        # We need a body-frame projection: "forward" in body coords, "up" globally.
        # For first pass, use world-frame components and rely on calibrated facing.
        r_hand_v = m.vec(r_hand.position) - m.vec(r_shoulder.position)
        l_hand_v = m.vec(l_hand.position) - m.vec(l_shoulder.position)

        right_hand_above_shoulder = float(r_hand_v[2])  # Z component
        left_hand_above_shoulder = float(l_hand_v[2])

        # "Forward" component: project onto body's facing direction in XY plane.
        #delete body_facing_rad = m._math.radians(facing) if False else 0.0  # see comment below
        
        # NOTE: First pass uses world X as "forward". This is correct as long as the
        # player stays facing roughly the calibration direction. We'll improve this
        # when we add proper body-frame transforms.
        right_hand_forward = float(r_hand_v[0])
        left_hand_forward = float(l_hand_v[0])

        # ---- Feet ----
        feet_distance = m.distance(r_foot.position, l_foot.position)
        right_foot_height = r_foot.position[2]
        left_foot_height = l_foot.position[2]

        return BodyState(
            torso_lean_forward=torso_lean_forward,
            torso_lean_side=torso_lean_side,
            torso_facing=facing,
            hip_height=hip_z,
            hip_height_normalized=hip_height_normalized,
            right_hand_above_shoulder=right_hand_above_shoulder,
            left_hand_above_shoulder=left_hand_above_shoulder,
            right_hand_forward=right_hand_forward,
            left_hand_forward=left_hand_forward,
            feet_distance=feet_distance,
            right_foot_height=right_foot_height,
            left_foot_height=left_foot_height,
            timestamp=pose.timestamp,
            is_calibrated=self._baseline is not None,
        )


def _normalize_angle(deg: float) -> float:
    """Wrap an angle to [-180, 180]."""
    while deg > 180:
        deg -= 360
    while deg < -180:
        deg += 360
    return deg