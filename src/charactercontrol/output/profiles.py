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
class Profile:
    """A complete control mapping for one game."""
    name: str
    description: str
    analog: list[AnalogMapping] = field(default_factory=list)
    buttons: list[ButtonMapping] = field(default_factory=list)


def load_profile(path: Path) -> Profile:
    """Load and validate a profile from a JSON file."""
    data = json.loads(path.read_text())

    analog = [
        AnalogMapping(**m) for m in data.get("analog", [])
    ]
    buttons = [
        ButtonMapping(**m) for m in data.get("buttons", [])
    ]

    return Profile(
        name=data["name"],
        description=data.get("description", ""),
        analog=analog,
        buttons=buttons,
    )