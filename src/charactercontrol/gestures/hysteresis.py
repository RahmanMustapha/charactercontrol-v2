"""
Hysteresis gate: a thresholded boolean state with separate on/off thresholds
to prevent flicker on noisy continuous inputs.
"""


class HysteresisGate:
    """
    Tracks whether a continuous value is currently 'engaged' (above on_threshold)
    or 'released' (below off_threshold), with a deadband between to absorb noise.

    Conventions:
        - on_threshold > off_threshold: standard "high engages" gate.
          Use for things like "hand raised above shoulder" (positive value triggers).
        - on_threshold < off_threshold: inverted "low engages" gate.
          Use for things like "hip dropped below baseline" (negative value triggers).

    Usage:
        gate = HysteresisGate(on_threshold=15.0, off_threshold=8.0)
        for value in stream:
            engaged = gate.update(value)
            ...
    """

    def __init__(self, on_threshold: float, off_threshold: float) -> None:
        self._on_threshold = on_threshold
        self._off_threshold = off_threshold
        self._engaged = False

        # Detect orientation: "high engages" if on > off; "low engages" otherwise.
        self._high_engages = on_threshold > off_threshold

    def update(self, value: float) -> bool:
        """Feed a new value and return current engaged state."""
        if self._high_engages:
            if not self._engaged and value >= self._on_threshold:
                self._engaged = True
            elif self._engaged and value <= self._off_threshold:
                self._engaged = False
        else:
            if not self._engaged and value <= self._on_threshold:
                self._engaged = True
            elif self._engaged and value >= self._off_threshold:
                self._engaged = False
        return self._engaged

    @property
    def engaged(self) -> bool:
        return self._engaged

    def reset(self) -> None:
        self._engaged = False