"""
GestureEngine: runs all registered detectors against incoming BodyStates
and yields gesture events.
"""

from typing import Iterable

from charactercontrol.pose.types import BodyState
from charactercontrol.gestures.events import GestureEvent
from charactercontrol.gestures.detectors import LeanDetector, JumpDetector


class GestureEngine:
    """
    Owns a collection of gesture detectors and runs each against incoming BodyStates.
    Events from all detectors are aggregated into a single output stream.
    """

    def __init__(self) -> None:
        self._lean = LeanDetector()
        self._jump = JumpDetector()


    def update(self, state: BodyState) -> list[GestureEvent]:
        """Run all detectors and return aggregated events for this frame."""
        events: list[GestureEvent] = []
        events.extend(self._lean.update(state))
        events.extend(self._jump.update(state))

        return events