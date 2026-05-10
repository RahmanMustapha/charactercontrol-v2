"""
Interactive calibration routine.

Captures a stable baseline pose by averaging multiple samples while the user
stands neutrally. Validates that the captured pose looks like an upright person
before accepting it.
"""

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from charactercontrol.pose.types import Pose
from charactercontrol.pose.interpreter import (
    CalibrationBaseline,
    PELVIS, HEAD, RIGHT_SHOULDER, LEFT_SHOULDER,
    RIGHT_HAND, LEFT_HAND, RIGHT_FOOT, LEFT_FOOT,
)
from charactercontrol.pose.math_utils import quat_to_euler_zyx, distance


# ---- Sampling parameters ----
CAPTURE_DURATION_SEC = 1.0     # how long to collect samples
SAMPLE_INTERVAL_SEC = 0.02     # ~50 Hz sampling within the capture window
MIN_SAMPLES = 20               # require at least this many for a valid baseline


# ---- Validation thresholds ----
# These are sanity bounds, not precision requirements.
MIN_PLAYER_HEIGHT_M = 1.2
MAX_PLAYER_HEIGHT_M = 2.3
MAX_TORSO_LEAN_DEG = 20.0      # if torso pitches/rolls more than this at "rest", reject
MAX_HIP_VARIANCE_M = 0.05      # hip Z shouldn't jitter more than 5cm during capture
MAX_HAND_RAISE_M = 0.20        # hands should be near the body, not in the air
MIN_HAND_BELOW_SHOULDER_M = 0.30   # hand must be ≥30cm below shoulder. At rest, hands hang well below the shoulders. T-pose and forward-extension
                                   # both place the hand at ~shoulder height. Require hands to be clearly down.


class CalibrationError(Exception):
    """Raised when calibration capture fails validation."""


@dataclass
class _SampleAccumulator:
    """Collects samples during the capture window for averaging."""
    pelvis_z: list[float]
    head_z: list[float]
    foot_z_avg: list[float]
    yaw_deg: list[float]
    shoulder_width: list[float]
    arm_length: list[float]
    torso_pitch: list[float]
    torso_roll: list[float]
    hand_above_shoulder_max: list[float]
    shoulder_to_hand_dist_max: list[float]


def _empty_accumulator() -> _SampleAccumulator:
    return _SampleAccumulator(
        pelvis_z=[], head_z=[], foot_z_avg=[],
        yaw_deg=[], shoulder_width=[], arm_length=[],
        torso_pitch=[], torso_roll=[], hand_above_shoulder_max=[],
        shoulder_to_hand_dist_max = [],
    )


def _accumulate(acc: _SampleAccumulator, pose: Pose) -> bool:
    """Pull values from a single Pose into the accumulator. Returns False if pose incomplete."""
    required = (PELVIS, HEAD, RIGHT_SHOULDER, LEFT_SHOULDER,
                RIGHT_HAND, LEFT_HAND, RIGHT_FOOT, LEFT_FOOT)
    for sid in required:
        if pose.get(sid) is None:
            return False

    pelvis = pose.get(PELVIS)
    head = pose.get(HEAD)
    r_shoulder = pose.get(RIGHT_SHOULDER)
    l_shoulder = pose.get(LEFT_SHOULDER)
    r_hand = pose.get(RIGHT_HAND)
    l_hand = pose.get(LEFT_HAND)
    r_foot = pose.get(RIGHT_FOOT)
    l_foot = pose.get(LEFT_FOOT)

    # T8 carries upper-torso orientation; we use it for facing/lean.
    t8 = pose.get(5)
    if t8 is None:
        return False
    yaw, pitch, roll = quat_to_euler_zyx(t8.quaternion)

    acc.pelvis_z.append(pelvis.position[2])
    acc.head_z.append(head.position[2])
    acc.foot_z_avg.append(0.5 * (r_foot.position[2] + l_foot.position[2]))
    acc.yaw_deg.append(yaw)
    acc.torso_pitch.append(pitch)
    acc.torso_roll.append(roll)
    acc.shoulder_width.append(distance(r_shoulder.position, l_shoulder.position))
    acc.arm_length.append(0.5 * (
        distance(r_shoulder.position, r_hand.position) +
        distance(l_shoulder.position, l_hand.position)
    ))
    # Hands should be near the body — track the max raised value to catch raised arms.
    r_hand_above = r_hand.position[2] - r_shoulder.position[2]
    l_hand_above = l_hand.position[2] - l_shoulder.position[2]
    acc.hand_above_shoulder_max.append(max(r_hand_above, l_hand_above))


    return True


def _validate(acc: _SampleAccumulator) -> Optional[str]:
    """Return None if baseline looks valid, otherwise a human-readable rejection reason."""
    if len(acc.pelvis_z) < MIN_SAMPLES:
        return f"only got {len(acc.pelvis_z)} valid samples (need {MIN_SAMPLES}); is the suit streaming?"

    pelvis_var = float(np.std(acc.pelvis_z))
    if pelvis_var > MAX_HIP_VARIANCE_M:
        return f"hip jittered {pelvis_var * 100:.1f}cm during capture — please stand more still"

    player_h = float(np.mean(acc.head_z) - np.mean(acc.foot_z_avg))
    if player_h < MIN_PLAYER_HEIGHT_M or player_h > MAX_PLAYER_HEIGHT_M:
        return f"player height computed as {player_h:.2f}m — outside expected range. Are you standing upright?"

    pitch = float(np.mean(acc.torso_pitch))
    roll = float(np.mean(acc.torso_roll))
    if abs(pitch) > MAX_TORSO_LEAN_DEG or abs(roll) > MAX_TORSO_LEAN_DEG:
        return f"torso is leaning (pitch={pitch:+.1f}°, roll={roll:+.1f}°) — please stand neutrally"

    highest_hand = float(np.max(acc.hand_above_shoulder_max))
    if highest_hand > -MIN_HAND_BELOW_SHOULDER_M:
        return (f"hand reached {highest_hand * 100:+.0f}cm relative to shoulder — "
                f"arms should hang at sides (hands well below shoulders)")



    return None


def _baseline_from_acc(acc: _SampleAccumulator) -> CalibrationBaseline:
    """Average accumulated samples into a final baseline."""
    return CalibrationBaseline(
        standing_hip_height=float(np.mean(acc.pelvis_z)),
        facing_yaw_offset=float(np.mean(acc.yaw_deg)),
        head_height=float(np.mean(acc.head_z)),
        floor_z=float(np.mean(acc.foot_z_avg)),
        shoulder_width=float(np.mean(acc.shoulder_width)),
        arm_length=float(np.mean(acc.arm_length)),
        player_height=float(np.mean(acc.head_z) - np.mean(acc.foot_z_avg)),
    )


def calibrate_interactive(get_pose, prompt: bool = True) -> CalibrationBaseline:
    """
    Run an interactive calibration routine.

    Args:
        get_pose: callable returning the latest Pose (or None if no data).
                  Typically receiver.get_latest.
        prompt: if True, prompt the user via stdin. If False, captures immediately.

    Returns:
        A validated CalibrationBaseline.

    Raises:
        CalibrationError: if validation fails. Caller can retry.
    """
    if prompt:
        print("\n=== Calibration ===")
        print("Stand upright, facing forward, arms relaxed at your sides.")
        input("Press Enter when ready... ")
        print("Capturing in 3...", end=" ", flush=True)
        time.sleep(1)
        print("2...", end=" ", flush=True)
        time.sleep(1)
        print("1...", end=" ", flush=True)
        time.sleep(1)
        print("hold still!")

    acc = _empty_accumulator()
    deadline = time.time() + CAPTURE_DURATION_SEC
    while time.time() < deadline:
        pose = get_pose()
        if pose is not None:
            _accumulate(acc, pose)
        time.sleep(SAMPLE_INTERVAL_SEC)

    rejection = _validate(acc)
    if rejection is not None:
        raise CalibrationError(rejection)

    baseline = _baseline_from_acc(acc)
    if prompt:
        print(f"\n✓ Calibration complete:")
        print(f"  Player height: {baseline.player_height:.2f}m")
        print(f"  Hip height:    {baseline.standing_hip_height:.2f}m")
        print(f"  Arm length:    {baseline.arm_length:.2f}m")
        print(f"  Facing offset: {baseline.facing_yaw_offset:+.1f}°")
    return baseline


def calibrate_with_retries(get_pose, max_attempts: int = 3) -> CalibrationBaseline:
    """
    Wrap calibrate_interactive with a retry loop.
    Re-prompts the user up to max_attempts times if validation fails.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return calibrate_interactive(get_pose, prompt=True)
        except CalibrationError as e:
            print(f"\n✗ Calibration failed: {e}")
            if attempt < max_attempts:
                print(f"Retrying ({attempt + 1}/{max_attempts})...")
            else:
                raise CalibrationError(
                    f"Calibration failed after {max_attempts} attempts. Last reason: {e}"
                ) from e
    raise RuntimeError("unreachable")  # for type checker