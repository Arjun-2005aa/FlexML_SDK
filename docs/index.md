# FlexML SDK

**Get live vision, 3D pose, object maps and point clouds from the FlexML iPhone/iPad app into your robot, computer or microcontroller.**

FlexML runs any Core ML vision model on the phone's camera, tracks objects in 3D with ARKit (and LiDAR where available), and streams the results over Wi-Fi or Bluetooth. This SDK is the open-source receiving side: a Python library and CLI, a ROS 2 bridge, ESP32 firmware examples, and the full data reference.

[Get started](getting-started.md){ .md-button .md-button--primary } [What data can I get?](data-reference.md){ .md-button } [Source on GitHub](https://github.com/Arjun-2005aa/FlexML_SDK){ .md-button }

## Quick start

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml serve
```

1. Put the phone and the computer on the same Wi-Fi.
2. In FlexML, open **Network Setup**. It finds the computer automatically and connects.
3. Tap **Start Inference**. Detections print in the terminal. Switch to **AR** for pose, mapped objects and the point cloud.

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
                    print(d.track_id, d.label, f"{d.confidence:.0%}", d.center, d.distance)

asyncio.run(main())
```

## Where to go next

| I want to… | Read |
|---|---|
| Connect a laptop, Pi or Jetson | [Getting started](getting-started.md), [Python library](python-library.md) |
| Know exactly which data exists (incl. the point cloud) | [Data reference](data-reference.md) |
| Drive a robot, use an ESP32 or ROS 2 | [Robot integration](robot-integration.md), [Examples](examples.md) |
| Parse the messages myself | [Stream protocol](protocol.md) |
| Run my own model | [Bring your own model](bring-your-own-model.md), [AI agent porting kit](agents/README.md) |
| Get ideas | [What you can build](use-cases.md) |

## Is the point cloud sent?

Yes: in **AR mode**, over **WebSocket/HTTP** (not UDP/Bluetooth), about once a second as incremental chunks. LiDAR devices give a dense coloured cloud. `flexml serve --map room.ply` saves it; `flexml ros2` publishes it on `/flexml/points`. Details and troubleshooting: [Data reference › The point cloud](data-reference.md#the-point-cloud-in-detail).

## For AI coding agents

The repository's [`AGENTS.md`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/AGENTS.md) explains the codebase, the data contract and the Python API to coding agents (Claude Code, Codex, Cursor, Copilot…).

## Converting models

Use Apple's official [coremltools](https://github.com/apple/coremltools) to convert PyTorch, TensorFlow and Hugging Face models to Core ML, then check them with `flexml check-model`.
