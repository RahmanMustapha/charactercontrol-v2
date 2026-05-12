"""
Replay a recorded pose session through the full pipeline.
Useful for iterating on detectors and profiles without re-suiting.

Run: uv run python scripts/replay.py <recording_path> [profile_name] [--speed 1.0]
"""

import argparse
import time
from pathlib import Path

from charactercontrol.sensors.replayer import PoseReplayer
from charactercontrol.pose.interpreter import PoseInterpreter
from charactercontrol.gestures.engine import GestureEngine
from charactercontrol.output.gamepad import VirtualGamepad
from charactercontrol.output.profiles import load_profile
from charactercontrol.output.mapper import GamepadMapper


UPDATE_HZ = 60
PROFILE_DIR = Path(__file__).parent.parent / "profiles"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("recording", help="Path to .jsonl recording")
    p.add_argument("profile", nargs="?", default="default", help="Profile name")
    p.add_argument("--speed", type=float, default=1.0, help="Replay speed (1.0=real-time)")
    p.add_argument("--loop", action="store_true", help="Loop the recording")
    p.add_argument("--no-gamepad", action="store_true",
                   help="Don't drive a virtual gamepad; just print events.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    recording_path = Path(args.recording)
    if not recording_path.exists():
        print(f"Recording not found: {recording_path}")
        return

    profile_path = PROFILE_DIR / f"{args.profile}.json"
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        return
    profile = load_profile(profile_path)
    print(f"Loaded profile: {profile.name}")
    print(f"Replaying: {recording_path}")
    print(f"Speed: {args.speed}x{' (looping)' if args.loop else ''}")

    replayer = PoseReplayer(recording_path, speed=args.speed, loop=args.loop)
    interpreter = PoseInterpreter()
    engine = GestureEngine()

    gamepad = None
    mapper = None
    if not args.no_gamepad:
        gamepad = VirtualGamepad()
        mapper = GamepadMapper(profile, gamepad)

    replayer.start()

    # Wait for first pose, then apply recorded baseline if available
    while replayer.get_latest() is None:
        time.sleep(0.05)
    if replayer.baseline is not None:
        interpreter.set_baseline(replayer.baseline)
        print(f"Applied recorded calibration baseline.")
    else:
        print("Warning: recording has no baseline; values will not be normalized.")

    print("\nReplaying. Ctrl+C to stop.\n")

    last_pose_ts = 0.0
    last_state = None
    try:
        while replayer.is_running:
            time.sleep(1.0 / UPDATE_HZ)
            pose = replayer.get_latest()

            if pose is not None and pose.timestamp != last_pose_ts:
                last_pose_ts = pose.timestamp
                state = interpreter.interpret(pose)
                if state is not None:
                    events = engine.update(state)
                    for event in events:
                        print(event)
                    if mapper is not None:
                        mapper.update(state, events)
                    last_state = state
                    continue

            if mapper is not None and last_state is not None:
                mapper.update(last_state, [])

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if gamepad is not None:
            gamepad.reset()
        replayer.stop()


if __name__ == "__main__":
    main()