"""
Live body state printer with proper interactive calibration.

Run: uv run python scripts/stream_body_state.py
Press 'r' + Enter at any time to recalibrate.
"""

import sys
import threading
import time

from charactercontrol.sensors.xsens_receiver import XsensReceiver
from charactercontrol.pose.interpreter import PoseInterpreter
from charactercontrol.pose.calibration import calibrate_with_retries, CalibrationError


PRINT_HZ = 4


class RecalRequest:
    """Tiny thread-safe flag set when user requests recalibration."""
    def __init__(self) -> None:
        self._flag = threading.Event()

    def request(self) -> None:
        self._flag.set()

    def consume(self) -> bool:
        if self._flag.is_set():
            self._flag.clear()
            return True
        return False


def _input_listener(recal: RecalRequest, stop: threading.Event) -> None:
    """Background thread: read stdin, watch for 'r' to trigger recalibration."""
    while not stop.is_set():
        try:
            line = sys.stdin.readline()
        except Exception:
            return
        if not line:
            return
        if line.strip().lower() == "r":
            recal.request()


def main() -> None:
    receiver = XsensReceiver()
    interpreter = PoseInterpreter()
    recal = RecalRequest()
    stop_event = threading.Event()

    receiver.start()
    print(f"Listening on {receiver._listen_ip}:{receiver._listen_port}")
    print("Waiting for first pose...")
    while receiver.get_latest() is None:
        time.sleep(0.05)

    # Initial calibration
    try:
        baseline = calibrate_with_retries(receiver.get_latest)
        interpreter.set_baseline(baseline)
    except CalibrationError as e:
        print(f"Could not calibrate: {e}")
        receiver.stop()
        return

    # Start input listener for runtime recalibration
    threading.Thread(
        target=_input_listener, args=(recal, stop_event), daemon=True
    ).start()

    print("\nStreaming body state. Type 'r' + Enter to recalibrate, Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(1.0 / PRINT_HZ)

            # Handle recalibration request
            if recal.consume():
                try:
                    baseline = calibrate_with_retries(receiver.get_latest)
                    interpreter.set_baseline(baseline)
                except CalibrationError as e:
                    print(f"Recalibration failed: {e}\nKeeping previous baseline.\n")

            pose = receiver.get_latest()
            if pose is None:
                continue
            state = interpreter.interpret(pose)
            if state is None:
                continue

            print(
                f"\rlean fwd={state.torso_lean_forward:+6.1f}°  "
                f"side={state.torso_lean_side:+6.1f}°  "
                f"facing={state.torso_facing:+6.1f}°  "
                f"hip_norm={state.hip_height_normalized:+.3f}m  "
                f"R_hand_up={state.right_hand_above_shoulder:+.2f}m  "
                f"L_hand_up={state.left_hand_above_shoulder:+.2f}m",
                end="",
                flush=True,
            )

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        stop_event.set()
        receiver.stop()


if __name__ == "__main__":
    main()