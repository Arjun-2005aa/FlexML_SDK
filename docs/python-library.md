# Python library and CLI

`flexml-companion` receives the phone's vision, pose and 3D-map stream, sends it commands, saves point clouds, bridges to ROS 2, and checks Core ML models. Python 3.9 or later.

## Install

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

| Extra | Adds |
|---|---|
| `discovery` | `zeroconf`, so the app finds the computer without typing an IP |
| `qr` | QR code for manual pairing |
| `map` | `numpy` for fast point-cloud handling |
| `check` | `coremltools` and `pillow` for `flexml check-model` |
| `all` | `discovery`, `qr` and `map` |

## Command line

```bash
flexml serve                                   # receive and print; type commands at the prompt
flexml serve --map room.ply --log session.jsonl  # save the point cloud on exit, log every message
flexml udp                                     # print the compact microcontroller stream (port 5005)
flexml ros2                                    # publish ROS 2 topics (inside a sourced ROS 2 shell)
flexml check-model My.mlpackage --image photo.jpg   # will it run well in FlexML? (needs [check])
```

## API

```python
import asyncio
import flexml_companion as flexml

async def main():
    async with flexml.Server(port=8080) as phone:     # WebSocket server + Bonjour advertising
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")  # raises flexml.FlexMLError if rejected
        await phone.command_text("set_classes person,cup")
        async for msg in phone.messages():            # typed messages; newest wins if you fall behind
            if isinstance(msg, flexml.Inference):
                for d in msg.detections:
                    print(d.track_id, d.label, d.confidence, d.center, d.world, d.distance)
            elif isinstance(msg, flexml.Pose) and msg.is_tracking:
                print("phone at", msg.position)

asyncio.run(main())
```

| Name | What it is |
|---|---|
| `Server(host, port=8080, http_port=8081, advertise=True, name=None, log_path=None)` | Receives the phone. Latest state: `.hello`, `.pose`, `.objects`, `.map` (a `PointCloud`) |
| `server.wait_for_phone(timeout=None)` | Waits until a phone connects |
| `server.messages()` | Async iterator of typed messages |
| `server.on(kind, callback)` | Callback per message type (`"inference"`, `"pose"`, `"anchors"`, `"map"`…) |
| `server.command(name, **params)` / `command_text("set_threshold 0.5")` | Sends a command, returns its result |
| `Inference` | `detections`, `classifications`, `segmentation`, `depth`, `tensors`, `imu`, `latency_ms`, `image`, `raw` |
| `Detection` | `track_id`, `label`, `class_id`, `confidence`, `box`, `center`, `keypoints`, `world`, `distance`, `anchor` |
| `Pose` | `tracking`, `is_tracking`, `position`, `orientation`, `transform`, `intrinsics`, `image_resolution` |
| `Anchors` / `Anchor` | Mapped objects: `id`, `label`, `position`, `confidence`, `sightings`, `last_seen` |
| `PointCloud` | `len()`, `to_numpy()` → `(N,3)` float32 + `(N,3)` uint8, `save_ply(path)` |
| `listen_udp(port)`, `parse_compact(text)` | Receive or parse the microcontroller format |
| `parse(text)` | Parse one JSON message (e.g. a line of a recording's `timeline.jsonl`) |

## Tests

```bash
cd python && python -m unittest discover -s tests
```
