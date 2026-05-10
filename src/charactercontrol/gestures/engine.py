"""
GestureEngine: runs all registered detectors against incoming BodyStates
and yields gesture events.
"""

from typing import Iterable

from charactercontrol.pose.types import BodyState
from charactercontrol.gestures.events import GestureEvent
from charactercontrol.gestures.detectors import LeanDetector


class GestureEngine:
    """
    Owns a collection of gesture detectors and runs each against incoming BodyStates.
    Events from all detectors are aggregated into a single output stream.
    """

    def __init__(self) -> None:
        # For now, just lean. We'll add more detectors as we build them.
        self._lean = LeanDetector()

    def update(self, state: BodyState) -> list[GestureEvent]:
        """Run all detectors and return aggregated events for this frame."""
        events: list[GestureEvent] = []
        events.extend(self._lean.update(state))
        return events