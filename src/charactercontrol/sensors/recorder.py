"""
Pose stream recorder. Subscribes to a PoseSource and writes each pose to a JSONL file.

File format (JSONL):
  Line 1: header (session metadata, optional calibration baseline)
  Line 2+: one Pose per line

Each Pose line is a JSON object with timestamp, sample_counter, and segments.
"""

import json
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from charactercontrol.pose.types import Pose
from charactercontrol.pose.interpreter import CalibrationBaseline


class PoseRecorder:
    """
    Polls a pose source and writes every new pose to a JSONL file.
    Thread-safe; runs in its own background thread.
    """

    def __init__(
        self,
        get_pose: Callable[[], Optional[Pose]],
        output_path: Path,
        session_name: str = "",
        baseline: Optional[CalibrationBaseline] = None,
        poll_hz: float = 120.0,
    ) -> None:
        self._get_pose = get_pose
        self._output_path = output_path
        self._session_name = session_name
        self._baseline = baseline
        self._poll_interval = 1.0 / poll_hz

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._sample_count = 0

    def start(self) -> None:
        """Open the file, write header, start the recording thread."""
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._output_path, "w", encoding="utf-8")

        header = {
            "type": "header",
            "session_name": self._session_name,
            "recorded_at": time.time(),
            "baseline": asdict(self._baseline) if self._baseline else None,
        }
        self._file.write(json.dumps(header) + "\n")
        self._file.flush()

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._record_loop, name="PoseRecorder", daemon=True
        )
        self._thread.start()

    def stop(self) -> dict:
        """Stop recording and close the file. Returns a small summary dict."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._file.close()
        return {
            "samples_written": self._sample_count,
            "path": str(self._output_path),
        }

    def _record_loop(self) -> None:
        last_timestamp: float = 0.0
        while not self._stop_event.is_set():
            pose = self._get_pose()
            if pose is not None and pose.timestamp != last_timestamp:
                self._write_pose(pose)
                last_timestamp = pose.timestamp
            time.sleep(self._poll_interval)

    def _write_pose(self, pose: Pose) -> None:
        record = {
            "type": "pose",
            "timestamp": pose.timestamp,
            "sample_counter": pose.sample_counter,
            "segments": {
                str(sid): {
                    "name": seg.name,
                    "position": list(seg.position),
                    "quaternion": list(seg.quaternion),
                }
                for sid, seg in pose.segments.items()
            },
        }
        self._file.write(json.dumps(record) + "\n")
        self._sample_count += 1