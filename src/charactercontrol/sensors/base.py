"""
Common interface for anything that produces a stream of Pose snapshots.
Implementers: XsensReceiver (live), PoseReplayer (from recorded file), and
eventually a fused RealSense+Xsens source.
"""

from typing import Protocol, Optional
from charactercontrol.pose.types import Pose


class PoseSource(Protocol):
    """A source of live body pose data."""

    def start(self) -> None:
        """Begin producing poses. Non-blocking."""
        ...

    def stop(self) -> None:
        """Stop producing poses and clean up resources."""
        ...

    def get_latest(self) -> Optional[Pose]:
        """
        Return the most recent Pose snapshot, or None if no data yet.
        Thread-safe; can be called from any thread.
        """
        ...

    @property
    def is_running(self) -> bool:
        """True if the source is actively producing poses."""
        ...