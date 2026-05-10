"""
Live gesture event printer.
Calibrates, then prints each gesture event as it fires.

Run: uv run python scripts/stream_gestures.py
"""

import time
import threading
import sys

from charactercontrol.sensors.xsens_receiver import XsensReceiver
from charactercontrol.pose.interpreter import PoseInterpreter
from charactercontrol.pose.calibration import calibrate_with_retries, CalibrationError
from charactercontrol.gestures.engine import GestureEngine


UPDATE_HZ = 60   # match streaming rate so we don't miss fast events


def main() -> None:
    receiver = XsensReceiver()
    interpreter = PoseInterpreter()
    engine = GestureEngine()

    receiver.start()
    print("Waiting for first pose...")
    while receiver.get_latest() is None:
        time.sleep(0.05)

    try:
        baseline = calibrate_with_retries(receiver.get_latest)
        interpreter.set_baseline(baseline)
    except CalibrationError as e:
        print(f"Could not calibrate: {e}")
        receiver.stop()
        return

    print("\nStreaming gestures. Lean to test. Ctrl+C to exit.\n")

    try:
        last_pose_ts = 0.0
        while True:
            time.sleep(1.0 / UPDATE_HZ)
            pose = receiver.get_latest()
            if pose is None or pose.timestamp == last_pose_ts:
                continue
            last_pose_ts = pose.timestamp

            state = interpreter.interpret(pose)
            if state is None:
                continue

            events = engine.update(state)
            for event in events:
                print(event)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        receiver.stop()


if __name__ == "__main__":
    main()