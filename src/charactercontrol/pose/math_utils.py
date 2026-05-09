"""
Math helpers for pose interpretation.
Quaternions are stored as (w, x, y, z) tuples — same convention as Xsens MVN.
"""

import math
import numpy as np


def quat_to_rotation_matrix(quat: tuple[float, float, float, float]) -> np.ndarray:
    """
    Convert quaternion (w, x, y, z) to a 3x3 rotation matrix.
    """
    w, x, y, z = quat
    # Normalize defensively; tiny floating point drift can break orthogonality.
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n == 0:
        return np.eye(3)
    w, x, y, z = w / n, x / n, y / n, z / n

    return np.array([
        [1 - 2 * (y * y + z * z),     2 * (x * y - z * w),     2 * (x * z + y * w)],
        [    2 * (x * y + z * w), 1 - 2 * (x * x + z * z),     2 * (y * z - x * w)],
        [    2 * (x * z - y * w),     2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def quat_to_euler_zyx(quat: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """
    Convert quaternion to Euler angles (yaw, pitch, roll) in degrees, ZYX order.
    
    Returns:
        yaw   — rotation around Z (vertical axis); facing direction
        pitch — rotation around Y; forward/back lean
        roll  — rotation around X; side-to-side lean
    
    Note: Euler conversions are convention-dependent. This uses ZYX intrinsic rotations,
    which matches the common "yaw-pitch-roll" interpretation for an upright body.
    """
    w, x, y, z = quat

    # Roll (rotation around X)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # Pitch (rotation around Y)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)  # gimbal lock
    else:
        pitch = math.asin(sinp)

    # Yaw (rotation around Z)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def vec(p: tuple[float, float, float]) -> np.ndarray:
    """Position tuple → numpy 3-vector."""
    return np.array(p, dtype=float)


def distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """Euclidean distance between two 3D points."""
    return float(np.linalg.norm(vec(a) - vec(b)))