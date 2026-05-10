"""
Gesture detectors: take a BodyState, return any GestureEvents that fire.

Each detector encapsulates its own state (typically HysteresisGates).
Detectors are stateless across body states only in the sense that they
don't store BodyState history themselves; their state is the gates' engaged flags.
"""

from typing import Optional, Iterable

from charactercontrol.pose.types import BodyState
from charactercontrol.gestures.hysteresis import HysteresisGate
from charactercontrol.gestures.events import GestureKind, EventPhase, GestureEvent


class LeanDetector:
    """
    Detects torso lean in four directions: left, right, forward, back.
    
    Uses separate hysteresis gates per direction. Lean is computed from
    BodyState.torso_lean_side (positive=right) and torso_lean_forward (positive=forward).
    """

    # Default thresholds in degrees. Tuned for natural standing posture.
    DEFAULT_LEAN_ON_DEG = 15.0
    DEFAULT_LEAN_OFF_DEG = 8.0
    # Cap intensity scaling at this lean angle (i.e. lean ≥30° == full intensity).
    INTENSITY_FULL_DEG = 30.0

    def __init__(
        self,
        on_threshold_deg: float = DEFAULT_LEAN_ON_DEG,
        off_threshold_deg: float = DEFAULT_LEAN_OFF_DEG,
    ) -> None:
        # Side leans: positive=right, negative=left
        self._right_gate = HysteresisGate(on_threshold_deg, off_threshold_deg)
        self._left_gate = HysteresisGate(-on_threshold_deg, -off_threshold_deg)
        # Forward/back: positive=forward, negative=back
        self._forward_gate = HysteresisGate(on_threshold_deg, off_threshold_deg)
        self._back_gate = HysteresisGate(-on_threshold_deg, -off_threshold_deg)

    def update(self, state: BodyState) -> Iterable[GestureEvent]:
        """Update gates and yield any state-change events."""
        events = []

        events.extend(self._update_gate(
            state, self._right_gate, state.torso_lean_side,
            GestureKind.LEAN_RIGHT, sign=+1,
        ))
        events.extend(self._update_gate(
            state, self._left_gate, state.torso_lean_side,
            GestureKind.LEAN_LEFT, sign=-1,
        ))
        events.extend(self._update_gate(
            state, self._forward_gate, state.torso_lean_forward,
            GestureKind.LEAN_FORWARD, sign=+1,
        ))
        events.extend(self._update_gate(
            state, self._back_gate, state.torso_lean_forward,
            GestureKind.LEAN_BACK, sign=-1,
        ))

        return events

    def _update_gate(
        self,
        state: BodyState,
        gate: HysteresisGate,
        value: float,
        kind: GestureKind,
        sign: int,
    ) -> list[GestureEvent]:
        """Update one gate and emit start/end events on transitions."""
        was_engaged = gate.engaged
        is_engaged = gate.update(value)

        if is_engaged == was_engaged:
            return []

        # Compute intensity: how far past the on_threshold are we, normalized.
        intensity = min(abs(value) / self.INTENSITY_FULL_DEG, 1.0) if is_engaged else 0.0

        phase = EventPhase.START if is_engaged else EventPhase.END
        return [GestureEvent(
            kind=kind,
            phase=phase,
            timestamp=state.timestamp,
            intensity=intensity,
        )]