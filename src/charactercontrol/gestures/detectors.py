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
    
import time as _time

class JumpDetector:
    """
    Detects a physical jump-in-place by tracking hip rise above baseline.

    Fires a START event on takeoff, then and END event after a short hold
    duration, simulating a controller button tap. Includes a refractory 
    period to prevent spurious re-fires from lanfing bobble.
    """

    #Hip must rise this many meters above baseline to trigger
    DEFAULT_ON_THRESHOLD_M = .07#0.10
    DEFAULT_OFF_THRESHOLD_M = .03#0.05
    # How long the button stays "pressed" (START → END delay)
    BUTTON_HOLD_SEC = .06#0.08
    # No new jumps can fire within this window after the last one
    REFRACTORY_SEC = .15#0.25

    def __init__(
        self,
        on_threshold_m: float = DEFAULT_ON_THRESHOLD_M,
        off_threshold_m: float = DEFAULT_OFF_THRESHOLD_M,
    ) -> None:
        self._gate = HysteresisGate(on_threshold_m, off_threshold_m)
        self._last_jump_start: float = 0.0   # timestamp of the most recent START
        self._pending_end: bool = False      # waiting to emit END

    def update(self, state: BodyState) -> Iterable[GestureEvent]:
        events: list[GestureEvent] = []
        now = state.timestamp

        # Emit END if we've passed the hold duration
        if self._pending_end and (now - self._last_jump_start) >= self.BUTTON_HOLD_SEC:
            events.append(GestureEvent(
                kind=GestureKind.JUMP,
                phase=EventPhase.END,
                timestamp=now,
                intensity=0.0,
            ))
            self._pending_end = False

        was_engaged = self._gate.engaged
        is_engaged = self._gate.update(state.hip_height_normalized)

        # Fire START on rising edge, but only outside the refractory window
        if is_engaged and not was_engaged:
            time_since_last = now - self._last_jump_start
            if time_since_last >= self.REFRACTORY_SEC:
                self._last_jump_start = now
                self._pending_end = True
                events.append(GestureEvent(
                    kind=GestureKind.JUMP,
                    phase=EventPhase.START,
                    timestamp=now,
                    intensity=1.0,
                ))


        return events