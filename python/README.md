# flexml-companion

Companion library and CLI for the **FlexML** iOS app. It receives the phone's vision, pose and 3D-map stream, sends it commands, and bridges it to ROS 2.

> **Install from GitHub:** `flexml-companion` isn't on PyPI yet, so install it straight from this repository (below), or from a local clone with `pip install "./python[all]"`.

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml serve          # the app finds this computer automatically (Bonjour)
flexml serve --map space.ply --log session.jsonl
flexml udp            # print the compact microcontroller stream
flexml ros2           # publish ROS 2 topics (inside a sourced ROS 2 environment)
flexml check-model My.mlpackage --image photo.jpg   # will it run well in FlexML? (needs the [check] extra)
```

```python
import asyncio
import flexml_companion as flexml

async def main():
    async with flexml.Server() as phone:
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        async for msg in phone.messages():
            if isinstance(msg, flexml.Inference):
                for d in msg.detections:
                    print(d.track_id, d.label, round(d.confidence, 2), d.center, d.distance)
            elif isinstance(msg, flexml.Pose) and msg.is_tracking:
                print("phone at", msg.position)

asyncio.run(main())
```

| Extra | Adds |
|---|---|
| `discovery` | `zeroconf`, so the app finds the computer without an IP |
| `qr` | QR code for manual pairing |
| `map` | `numpy` for fast point-cloud handling |
| `check` | `coremltools` and `pillow` for `flexml check-model` |

**Documentation:**
- [Getting started](../docs/getting-started.md)
- [Robot integration](../docs/robot-integration.md)
- [Stream protocol](../docs/protocol.md)

**Tests:** `python -m unittest discover -s tests`
