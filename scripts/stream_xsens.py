"""
Live pose stream printer.
Run: uv run python scripts/stream_xsens.py
"""

import time

from charactercontrol.sensors.xsens_receiver import XsensReceiver


PRINT_HZ = 2
INTERESTING_SEGMENTS = (1, 7, 11, 15, 18, 22)  # pelvis, head, hands, feet


def main() -> None:
    receiver = XsensReceiver()
    receiver.start()
    print(f"Listening for Xsens stream on {receiver._listen_ip}:{receiver._listen_port}")
    print("Press Ctrl+C to stop.\n")

    last_count = 0
    try:
        while True:
            time.sleep(1.0 / PRINT_HZ)
            stats = receiver.stats()
            pose = receiver.get_latest()

            rate = (stats["packet_count"] - last_count) * PRINT_HZ
            last_count = stats["packet_count"]

            print(
                f"\n--- {rate:.0f} pkts/sec | "
                f"type: MXTP{stats['last_message_type']} | "
                f"segments: {stats['segments_tracked']} ---"
            )

            if pose is not None:
                for seg_id in INTERESTING_SEGMENTS:
                    seg = pose.get(seg_id)
                    if seg is not None:
                        x, y, z = seg.position
                        print(f"  {seg.name:18} pos=({x:+.3f}, {y:+.3f}, {z:+.3f})")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        receiver.stop()
        print("Receiver stopped cleanly.")


if __name__ == "__main__":
    main()