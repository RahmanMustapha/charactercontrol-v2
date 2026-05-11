"""
Live body-as-controller play loop.
Calibrates, then drives a virtual Xbox 360 controller from your motion.

Run: uv run python scripts/play.py [profile_name]
Default profile: 'default'. Examples: 'celeste'.
"""

import sys
import time
from pathlib import Path

from charactercontrol.sensors.xsens_receiver import XsensReceiver
from charactercontrol.pose.interpreter import PoseInterpreter
from charactercontrol.pose.calibration import calibrate_with_retries, CalibrationError
from charactercontrol.gestures.engine import GestureEngine
from charactercontrol.output.gamepad import VirtualGamepad
from charactercontrol.output.profiles import load_profile
from charactercontrol.output.mapper import GamepadMapper


UPDATE_HZ = 60
PROFILE_DIR = Path(__file__).parent.parent / "profiles"


def main() -> None:
    profile_name = sys.argv[1] if len(sys.argv) > 1 else "default"
    profile_path = PROFILE_DIR / f"{profile_name}.json"
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        return
    profile = load_profile(profile_path)
    print(f"Loaded profile: {profile.name} — {profile.description}")

    receiver = XsensReceiver()
    interpreter = PoseInterpreter()
    engine = GestureEngine()
    gamepad = VirtualGamepad()
    mapper = GamepadMapper(profile, gamepad)

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

    print("\nVirtual gamepad active. Lean to control. Ctrl+C to exit.")
    print("(Open joy.cpl to see live stick movement, or launch a game.)\n")

    try:
        last_pose_ts = 0.0
        last_state = None

        while True:
            time.sleep(1.0 / UPDATE_HZ)
            pose = receiver.get_latest()

            if pose is not None and pose.timestamp != last_pose_ts:
                last_pose_ts = pose.timestamp
                state = interpreter.interpret(pose)
                if state is not None:
                    events = engine.update(state)
                    mapper.update(state, events)
                    last_state = state
                    continue

        # No new pose this tick — re-push last known state to keep the driver fed.
        if last_state is not None:
            mapper.update(last_state, [])

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        gamepad.reset()
        receiver.stop()


if __name__ == "__main__":
    main()