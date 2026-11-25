"""Print every detection FlexML sends.

Run this, then open FlexML › Network Setup on a phone on the same Wi-Fi (it finds this computer
automatically) and tap Start Inference.

    python print_detections.py
"""
import asyncio

import flexml_companion as flexml


async def main() -> None:
    async with flexml.Server() as phone:
        print(f"Waiting for FlexML at {phone.address} …")
        await phone.wait_for_phone()
        await asyncio.sleep(0.2)  # the phone's `hello` arrives right after it connects
        if phone.hello:
            h = phone.hello
            print(f"Connected: {h.app} on {h.device}, {h.system}, capabilities: {h.capabilities}")
        async for msg in phone.messages():
            if isinstance(msg, flexml.Inference):
                for d in msg.detections:
                    cx, cy = d.center
                    dist = f"{d.distance:.2f} m" if d.distance is not None else "–"
                    print(f"#{d.track_id:<4} {d.label:<14} {d.confidence:4.0%}  centre=({cx:.2f}, {cy:.2f})  distance={dist}")
                for label, conf in msg.classifications:
                    print(f"class {label} {conf:.0%}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
