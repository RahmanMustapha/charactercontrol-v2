"""
Xsens MVN Real-Time Network Protocol receiver.

Listens for binary UDP datagrams from MVN Animate/Analyze and exposes the
latest body pose via a thread-safe interface.

Tested with MVN Animate 2026.4, Position+Quaternion datagram (MXTP02).
"""

import socket
import struct
import threading
import time
from typing import Optional

from charactercontrol.pose.types import Pose, SegmentPose


# Xsens MVN body segment names (23-segment biomechanical model).
SEGMENT_NAMES: dict[int, str] = {
    1: "Pelvis",
    2: "L5",
    3: "L3",
    4: "T12",
    5: "T8",
    6: "Neck",
    7: "Head",
    8: "RightShoulder",
    9: "RightUpperArm",
    10: "RightForearm",
    11: "RightHand",
    12: "LeftShoulder",
    13: "LeftUpperArm",
    14: "LeftForearm",
    15: "LeftHand",
    16: "RightUpperLeg",
    17: "RightLowerLeg",
    18: "RightFoot",
    19: "RightToe",
    20: "LeftUpperLeg",
    21: "LeftLowerLeg",
    22: "LeftFoot",
    23: "LeftToe",
}


class XsensReceiver:
    """
    Live receiver for Xsens MVN binary network stream.

    Usage:
        receiver = XsensReceiver()
        receiver.start()
        while True:
            pose = receiver.get_latest()
            if pose:
                ...  # use pose
        receiver.stop()
    """

    HEADER_SIZE = 24
    SEGMENT_RECORD_SIZE = 32  # 4 (id) + 12 (xyz) + 16 (quat wxyz)

    def __init__(
        self,
        listen_ip: str = "0.0.0.0",
        listen_port: int = 9763,
        socket_timeout: float = 0.5,
    ) -> None:
        self._listen_ip = listen_ip
        self._listen_port = listen_port
        self._socket_timeout = socket_timeout

        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._latest_pose: Optional[Pose] = None
        self._packet_count = 0
        self._last_message_type = ""

    # ---- PoseSource interface ----

    def start(self) -> None:
        """Open the UDP socket and start the receive thread."""
        if self._thread is not None and self._thread.is_alive():
            raise RuntimeError("XsensReceiver already running")

        self._stop_event.clear()
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind((self._listen_ip, self._listen_port))
        self._socket.settimeout(self._socket_timeout)

        self._thread = threading.Thread(
            target=self._receive_loop, name="XsensReceiver", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the receive thread to stop and clean up resources."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def get_latest(self) -> Optional[Pose]:
        """Return the most recent Pose snapshot (or None if none received yet)."""
        with self._lock:
            return self._latest_pose

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ---- Diagnostics ----

    def stats(self) -> dict:
        """Return packet count, last message type, etc. — for debugging."""
        with self._lock:
            return {
                "packet_count": self._packet_count,
                "last_message_type": self._last_message_type,
                "has_pose": self._latest_pose is not None,
                "segments_tracked": (
                    len(self._latest_pose.segments) if self._latest_pose else 0
                ),
            }

    # ---- Internal ----

    def _receive_loop(self) -> None:
        assert self._socket is not None
        while not self._stop_event.is_set():
            try:
                data, _addr = self._socket.recvfrom(8192)
            except socket.timeout:
                continue  # gives us a chance to check the stop flag
            except OSError:
                # Socket closed during shutdown
                break

            self._handle_packet(data)

    def _handle_packet(self, data: bytes) -> None:
        if len(data) < self.HEADER_SIZE:
            return

        try:
            id_string = data[0:6].decode("ascii", errors="replace")
            sample_counter = struct.unpack(">I", data[6:10])[0]
        except struct.error:
            return

        msg_type = id_string[4:6]

        with self._lock:
            self._packet_count += 1
            self._last_message_type = msg_type

        if msg_type == "02":
            pose = self._parse_type_02(data, sample_counter)
            if pose is not None:
                with self._lock:
                    self._latest_pose = pose

    def _parse_type_02(self, data: bytes, sample_counter: int) -> Optional[Pose]:
        """Type 02: position + quaternion per segment."""
        payload = data[self.HEADER_SIZE:]
        n_segments = len(payload) // self.SEGMENT_RECORD_SIZE
        if n_segments == 0:
            return None

        segments: dict[int, SegmentPose] = {}
        for i in range(n_segments):
            offset = i * self.SEGMENT_RECORD_SIZE
            try:
                seg_id = struct.unpack(">I", payload[offset:offset + 4])[0]
                x, y, z = struct.unpack(">fff", payload[offset + 4:offset + 16])
                qw, qx, qy, qz = struct.unpack(
                    ">ffff", payload[offset + 16:offset + 32]
                )
            except struct.error:
                continue

            segments[seg_id] = SegmentPose(
                segment_id=seg_id,
                name=SEGMENT_NAMES.get(seg_id, f"Segment{seg_id}"),
                position=(x, y, z),
                quaternion=(qw, qx, qy, qz),
            )

        return Pose(
            timestamp=time.time(),
            sample_counter=sample_counter,
            segments=segments,
        )