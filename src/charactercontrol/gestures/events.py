"""
Gesture event types — discrete events emitted when a gesture starts or ends.
"""

from dataclasses import dataclass
from enum import Enum, auto


class GestureKind(Enum):
    LEAN_LEFT = auto()
    LEAN_RIGHT = auto()
    LEAN_FORWARD = auto()
    LEAN_BACK = auto()
    CROUCH = auto()
    JUMP = auto()
    RIGHT_HAND_RAISED = auto()
    LEFT_HAND_RAISED = auto()


class EventPhase(Enum):
    START = "start"
    END = "end"


@dataclass(frozen=True)
class GestureEvent:
    """A gesture starting or ending at a moment in time."""
    kind: GestureKind
    phase: EventPhase
    timestamp: float
    # Optional intensity (0–1, how strongly engaged) for downstream analog mapping.
    intensity: float = 1.0

    def __str__(self) -> str:
        return f"[{self.timestamp:.2f}] {self.kind.name} {self.phase.value.upper()}"