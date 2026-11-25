# FlexML SDK

**Get live vision, 3D pose, object maps and point clouds from the [FlexML](https://testflight.apple.com/join/pxAZj36a) iPhone/iPad app into your robot, computer or microcontroller.**

FlexML runs any Core ML vision model on the phone's camera, tracks objects in 3D with ARKit (and LiDAR where available), and streams the results over Wi-Fi or Bluetooth. This repository is everything you need on the *receiving* side:

| Folder | What's inside |
|---|---|
| [`python/`](python) | **`flexml-companion`**: Python library + `flexml` command-line tool. Receives the stream, sends commands to the phone, saves point clouds, bridges to ROS 2, and checks Core ML models. |
| [`examples/python/`](examples/python) | Ready-to-run scripts: print detections, follow a person, save the point cloud, build an obstacle map, remote control. |
| [`examples/ros2/`](examples/ros2) | ROS 2 bridge usage and a person-following node that publishes `/cmd_vel`. |
| [`examples/esp32/`](examples/esp32) | ESP32 firmware: Arduino (Wi-Fi UDP and Bluetooth LE) and MicroPython (UDP, OLED display). |
| [`docs/`](docs) | Protocol reference, data reference, robot integration, bringing your own model, project ideas. |
| [`docs/agents/`](docs/agents) | A drop-in `AGENTS.md` that lets a coding agent convert *your* model to Core ML for FlexML. |
| [`AGENTS.md`](AGENTS.md) | Orientation for AI coding agents working with this SDK (Claude Code, Codex, Cursor, Copilot…). |

> The FlexML app itself is distributed through the App Store. This SDK is MIT-licensed and open source.

---

## Quick start (2 minutes)

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml serve
```

1. Put the phone and the computer on the same Wi-Fi.
2. In FlexML, open **Network Setup**. It finds the computer automatically (Bonjour) and connects.
3. Tap **Start Inference**. Detections print in the terminal. Switch to **AR** to also get pose, mapped objects and the point cloud.

```python
import asyncio
import flexml_companion as flexml

async def main():
    async with flexml.Server() as phone:          # listens on :8080 and advertises itself
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        async for msg in phone.messages():
            if isinstance(msg, flexml.Inference):
                for d in msg.detections:
                    print(d.track_id, d.label, f"{d.confidence:.0%}", d.center, d.distance)
            elif isinstance(msg, flexml.Pose) and msg.is_tracking:
                print("phone at", msg.position)

asyncio.run(main())
```

Full walkthrough: [docs/getting-started.md](docs/getting-started.md).

---

## What data can I get?

| Data | Message | Mode | How often | How to receive |
|---|---|---|---|---|
| Detections (label, confidence, box, **stable track ID**, keypoints) | `inference` | Vision + AR | stream rate (5–60/s) | WebSocket/HTTP, UDP, BLE, ROS 2 |
| Classification, segmentation coverage, depth summary, raw tensor stats | `inference` | Vision + AR | stream rate | WebSocket/HTTP (classification/segmentation also UDP/BLE) |
| **3D position + distance** of each detection | `inference.detections[].world`, `.distance` | AR | stream rate | WebSocket/HTTP, ROS 2; distance also UDP/BLE |
| **6-DoF phone pose** + camera intrinsics | `pose` | AR | stream rate | WebSocket/HTTP, ROS 2 (`/odom`, TF); position + heading on UDP/BLE |
| **Object map** (labelled objects anchored in 3D) | `anchors` | AR | ~2/s | WebSocket/HTTP, ROS 2 (`/objects`) |
| **Point cloud** (coloured, metres) | `map` | AR | ~1/s, incremental | WebSocket/HTTP, ROS 2 (`/points`), saved `.ply` |
| IMU (acceleration, rotation, attitude, gravity) | `inference.imu` | Vision + AR | stream rate | WebSocket/HTTP (turn on *IMU data*) |
| Recordings (video, annotated video, `timeline.jsonl`) and Spaces (`points.ply`, objects, trajectory) | files | – | after the session | Share from the app |

Field-by-field details and what is **not** available: [docs/data-reference.md](docs/data-reference.md). Wire format: [docs/protocol.md](docs/protocol.md).

### Is the point cloud really sent?

**Yes**, but only under these conditions, which is the usual reason people don't see it:

1. **AR mode.** Vision mode has no 3D tracking, so there is no map. Tap **AR** on the camera screen or send `start_live` with `mode="ar"`.
2. **WebSocket/HTTP only.** The compact UDP and Bluetooth LE formats for microcontrollers carry detections and pose, **not** point clouds (they're far too large).
3. **The toggle is on.** *Network Setup › Stream › 3D point cloud (AR mode)* is on by default.
4. **It arrives slowly and incrementally:** about once a second, up to 20,000 *new* points per message, on a 2 cm voxel grid. Accumulate the chunks (the Python `Server` does this for you in `phone.map`).
5. **Density depends on the device.** LiDAR iPhones/iPads (Pro models) send a dense, coloured cloud; other devices send ARKit's sparse grey feature points.

Three ways to get it:
```bash
flexml serve --map room.ply                      # saves the accumulated cloud when you press Ctrl-C
python examples/python/save_point_cloud.py --seconds 30 --out room.ply
flexml ros2                                       # publishes sensor_msgs/PointCloud2 on /flexml/points
```
Or save a **Space** in the app and share `points.ply`.

---

## Connect your robot

| Robot brain | Use | Start here |
|---|---|---|
| Laptop, Raspberry Pi, Jetson (Python) | WebSocket + JSON, two-way | [`python/`](python), [`examples/python/`](examples/python) |
| ROS 2 robot | `flexml ros2` bridge | [`examples/ros2/`](examples/ros2) |
| ESP32 / microcontroller over Wi-Fi | Compact UDP lines | [`examples/esp32/`](examples/esp32) |
| ESP32 without Wi-Fi | Bluetooth LE (Nordic UART) | [`examples/esp32/arduino/FlexML_BLE`](examples/esp32/arduino/FlexML_BLE) |
| Anything else | Any WebSocket client; the protocol is plain JSON | [docs/protocol.md](docs/protocol.md) |

Your robot can also **drive the app**: start/stop the camera, switch models, change thresholds and classes, record, reset or save the map. See the command list in [docs/robot-integration.md](docs/robot-integration.md).

---

## Bring your own model

FlexML runs Core ML models (`.mlmodel` / `.mlpackage`) with an image input: detection, classification, segmentation, depth, pose and image-to-image.

- **Convert from PyTorch, TensorFlow, Hugging Face and more** with Apple's official converter, **[coremltools](https://github.com/apple/coremltools)** ([documentation](https://apple.github.io/coremltools/docs-guides/)).
- **Ultralytics YOLO:** `yolo export model=yolo11n.pt format=coreml nms=True`.
- **Check before you copy it to the phone:** `flexml check-model MyModel.mlpackage --image photo.jpg` (install the `[check]` extra).
- **Let an AI agent do it:** copy [`docs/agents/AGENTS.md`](docs/agents/AGENTS.md) into your model project and ask *"Port my model to FlexML."*

Guide: [docs/bring-your-own-model.md](docs/bring-your-own-model.md).

---

## What can I build?

Person-following robots, object-seeking rovers, obstacle maps for navigation, visual odometry for robots without wheel encoders, "where did I leave it" semantic maps, safety stops near machines, pan-tilt camera tracking, dataset collection, classroom labs… Each with the data it uses and a sketch of the code: **[docs/use-cases.md](docs/use-cases.md)**.

---

## For AI coding agents

[`AGENTS.md`](AGENTS.md) explains this repository to coding agents: layout, the message types, the Python API, how to run the tests, and the rules for adding examples. Claude Code reads it through [`CLAUDE.md`](CLAUDE.md).

## Development

```bash
cd python
pip install -e ".[all]"
python -m unittest discover -s tests
```

## License

[MIT](LICENSE). Contributions welcome: open an issue or a pull request.
