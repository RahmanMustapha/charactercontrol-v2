"""
Pose replayer. Reads a JSONL recording and replays it in real-time as a PoseSource,
making downstream code unable to tell the difference between live and replayed input.
"""

import json
import threading
import time
from pathlib import Path
from typing import Optional

from charactercontrol.pose.types import Pose, SegmentPose
from charactercontrol.pose.interpreter import CalibrationBaseline


class PoseReplayer:
    """
    Replay a recorded pose stream. Implements the same surface as XsensReceiver
    (start/stop/get_latest/is_running) so it can be used in place of a live source.

    Args:
        path: JSONL file to replay
        speed: playback speed multiplier (1.0 = real-time, 2.0 = 2x, 0.5 = half)
        loop: if True, restart from beginning when the file ends
    """

    def __init__(
        self,
        path: Path,
        speed: float = 1.0,
        loop: bool = False,
    ) -> None:
        self._path = path
        self._speed = speed
        self._loop = loop

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._latest_pose: Optional[Pose] = None
        self._baseline: Optional[CalibrationBaseline] = None

    # ---- PoseSource interface ----

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("PoseReplayer already running")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._replay_loop, name="PoseReplayer", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def get_latest(self) -> Optional[Pose]:
        with self._lock:
            return self._latest_pose

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- Replay-specific ----

    @property
    def baseline(self) -> Optional[CalibrationBaseline]:
        """Calibration baseline from the recording's header, if present."""
        return self._baseline

    # ---- Internal ----

    def _replay_loop(self) -> None:
        while not self._stop_event.is_set():
            self._play_once()
            if not self._loop:
                break

    def _play_once(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            # Read header
            header_line = f.readline()
            header = json.loads(header_line)
            if header.get("type") == "header" and header.get("baseline"):
                self._baseline = CalibrationBaseline(**header["baseline"])

            # Read and emit poses with original timing
            first_pose_time: Optional[float] = None
            replay_start_wall: Optional[float] = None

            for line in f:
                if self._stop_event.is_set():
                    return
                record = json.loads(line)
                if record.get("type") != "pose":
                    continue

                pose = self._record_to_pose(record)

                if first_pose_time is None:
                    first_pose_time = pose.timestamp
                    replay_start_wall = time.time()

                # Wait until it's time to emit this pose
                elapsed_recording = (pose.timestamp - first_pose_time) / self._speed
                target_wall = replay_start_wall + elapsed_recording
                sleep_time = target_wall - time.time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

                # Update timestamp to wall clock so downstream code sees "live" time
                pose_with_live_ts = Pose(
                    timestamp=time.time(),
                    sample_counter=pose.sample_counter,
                    segments=pose.segments,
                )
                with self._lock:
                    self._latest_pose = pose_with_live_ts

    def _record_to_pose(self, record: dict) -> Pose:
        segments = {
            int(sid): SegmentPose(
                segment_id=int(sid),
                name=data["name"],
                position=tuple(data["position"]),
                quaternion=tuple(data["quaternion"]),
            )
            for sid, data in record["segments"].items()
        }
        return Pose(
            timestamp=record["timestamp"],
            sample_counter=record["sample_counter"],
            segments=segments,
        )