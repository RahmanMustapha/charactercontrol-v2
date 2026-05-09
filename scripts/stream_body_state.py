"""
Live body state printer.
Same as stream_xsens.py, but runs the interpreter and prints semantic values.

Run: uv run python scripts/stream_body_state.py
"""

import time

from charactercontrol.sensors.xsens_receiver import XsensReceiver
from charactercontrol.pose.interpreter import PoseInterpreter, CalibrationBaseline


PRINT_HZ = 4


def main() -> None:
    receiver = XsensReceiver()
    interpreter = PoseInterpreter()

    receiver.start()
    print("Streaming body state. Stand still and press Enter to set calibration baseline.")
    print("Press Ctrl+C to exit.\n")

    # Prime the receiver — wait for first pose.
    while receiver.get_latest() is None:
        time.sleep(0.05)

    # Quick calibration: capture current pose as baseline on Enter, or skip with no-op.
    print("Capturing baseline in 2 seconds — stand neutrally...")
    time.sleep(2.0)
    baseline_pose = receiver.get_latest()
    if baseline_pose is not None:
        from charactercontrol.pose.math_utils import quat_to_euler_zyx
        t8 = baseline_pose.get(5)
        pelvis = baseline_pose.get(1)
        if t8 and pelvis:
            yaw, _, _ = quat_to_euler_zyx(t8.quaternion)
            interpreter.set_baseline(CalibrationBaseline(
                standing_hip_height=pelvis.position[2],
                facing_yaw_offset=yaw,
            ))
            print(f"Baseline set: hip_height={pelvis.position[2]:.3f}m, yaw={yaw:.1f}°\n")

    try:
        while True:
            time.sleep(1.0 / PRINT_HZ)
            pose = receiver.get_latest()
            if pose is None:
                continue
            state = interpreter.interpret(pose)
            if state is None:
                print("(waiting for full body data...)")
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
        receiver.stop()


if __name__ == "__main__":
    main()