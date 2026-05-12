"""
Profile loading and validation.

A profile defines how gestures and continuous body values map to gamepad inputs.
Profiles are JSON files in the project's `profiles/` directory.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AnalogMapping:
    """
    Maps a continuous BodyState attribute to an analog gamepad axis.
    
    Example: lean_side → left_stick_x with deadzone 8°, full at 25°.
    """
    source: str           # name of BodyState attribute (e.g. "torso_lean_side")
    target: str           # name of gamepad target (e.g. "left_stick_x")
    deadzone: float       # values within ±deadzone produce 0 output
    full_scale: float     # |value| >= full_scale produces ±1.0 output
    invert: bool = False  # flip sign of output


@dataclass
class ButtonMapping:
    """
    Maps a gesture event to a gamepad button.
    Button is held while the gesture is engaged; released when it ends.
    """
    gesture: str          # GestureKind name, e.g. "JUMP"
    button: str           # gamepad button name, e.g. "A"

@dataclass
class OrientationMapping:
    """
    Maps body facing direction combined with forward lean to an analog stick.

    The stick's direction is set by `torso_facing`:
        facing = 0°    → no horizontal stick output
        facing = +90°  → stick fully right (or as configured)
        facing = -90°  → stick fully left

    The stick's magnitude is gated by forward lean: the user must lean forward
    past `forward_deadzone` to commit to movement, scaled up to `forward_full_scale`.

    Standing upright but facing sideways = stick neutral (intent without commit).
    """
    target: str                # gamepad target, e.g. "left_stick_x"
    facing_deadzone: float     # facing angles within ±this produce no direction
    facing_full_scale: float   # facing angles ≥ this produce full deflection
    forward_deadzone: float    # forward lean below this produces no movement
    forward_full_scale: float  # forward lean ≥ this produces full magnitude
    invert: bool = False
    
@dataclass
class Profile:
    """A complete control mapping for one game."""
    name: str
    description: str
    analog: list[AnalogMapping] = field(default_factory=list)
    buttons: list[ButtonMapping] = field(default_factory=list)
    orientation: list[OrientationMapping] = field(default_factory=list)


def load_profile(path: Path) -> Profile:
    """Load and validate a profile from a JSON file."""
    data = json.loads(path.read_text())

    analog = [
        AnalogMapping(**m) for m in data.get("analog", [])
    ]
    buttons = [
        ButtonMapping(**m) for m in data.get("buttons", [])
    ]
    orientation = [OrientationMapping(**m) for m in data.get("orientation", [])]

    return Profile(
        name=data["name"],
        description=data.get("description", ""),
        analog=analog,
        buttons=buttons,
        orientation=orientation,
    )

