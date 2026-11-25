"""Follow a person with a differential-drive robot.

Locks onto one person (by track ID), turns to keep them centred, and drives forward until they
are within FOLLOW_DISTANCE (AR mode gives real distances; in Vision mode it uses box height).

Replace `drive()` with your motor code (serial to an Arduino, GPIO on a Pi, a ROS publisher…).

    python follow_person.py
"""
import asyncio
import time
from typing import Optional

import flexml_companion as flexml

TARGET = "person"
FOLLOW_DISTANCE = 1.2   # metres (AR mode)
TURN_GAIN = 1.5         # rad/s per unit of centring error
MAX_SPEED = 0.4         # m/s
LOST_AFTER = 1.0        # seconds without seeing the target before stopping


def drive(speed: float, turn: float) -> None:
    """Send to your motors. speed in m/s (forward +), turn in rad/s (left +)."""
    print(f"drive speed={speed:+.2f} m/s  turn={turn:+.2f} rad/s")


def control(d: flexml.Detection) -> tuple:
    error = d.center[0] - 0.5                      # −0.5 (left) … +0.5 (right)
    turn = -TURN_GAIN * error
    if d.distance is not None:                     # AR mode: measured/estimated distance
        gap = d.distance - FOLLOW_DISTANCE
    else:                                          # Vision mode: a tall box means close
        gap = 0.6 - d.box[3]
    speed = max(0.0, min(MAX_SPEED, 0.5 * gap)) if abs(error) < 0.3 else 0.0
    return speed, turn


async def main() -> None:
    async with flexml.Server() as phone:
        print(f"Waiting for FlexML at {phone.address} …")
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        await phone.command("set_classes", classes=[TARGET])
        print("Following. Ctrl-C to stop.")

        locked: Optional[int] = None
        last_seen = 0.0
        async for msg in phone.messages():
            if not isinstance(msg, flexml.Inference):
                continue
            people = [d for d in msg.detections if d.label == TARGET]
            target = next((d for d in people if d.track_id == locked), None)
            if target is None and people:
                target = max(people, key=lambda d: d.confidence)
                locked = target.track_id
                print(f"locked onto track {locked}")
            if target is not None:
                last_seen = time.monotonic()
                drive(*control(target))
            elif time.monotonic() - last_seen > LOST_AFTER:
                locked = None
                drive(0.0, 0.0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        drive(0.0, 0.0)
