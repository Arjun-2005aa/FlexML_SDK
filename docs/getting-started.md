# Getting Started with FlexML

FlexML turns an iPhone or iPad into a vision and spatial sensor for robots. It runs your Core ML models on the camera, tracks its own position in 3D, maps the space, and streams everything to a computer or microcontroller.

**Requirements:**
- **Device:** iPhone XS/XR or newer, or a recent iPad, on iOS 17 or later.
- **AR and maps:** AR mode needs ARKit, which every supported device has. Dense 3D maps need LiDAR (iPhone 12 Pro and later Pro models, iPad Pro 2020 and later). Without LiDAR, distances are estimated and maps are sparse.

---

## 1. First run (2 minutes)

1. Open FlexML. After the welcome pages, the home screen shows the selected model, **YOLOv3 Tiny (sample)**.
2. Tap **Start Inference** and allow camera access. Point the phone at people, cups, chairs or laptops.
3. Tap **Display** (top left) to choose what's drawn: boxes, labels, confidence, masks and the status panel. You can also set the confidence threshold and pick which classes to show.
4. Tap **Change Model** on the home screen to try **DeepLabV3** (segmentation), or import your own model (see [Bring your own model](bring-your-own-model.md)).

FlexML runs in landscape. Hold the phone sideways, or mount it that way on the robot.

## 2. AR mode, 3D objects and maps

Switch the bottom selector from **Vision** to **AR**:
- **Position tracking:** ARKit tracks the phone's position and rotation (visual-inertial odometry).
- **3D objects:** detected objects are placed in 3D and **remembered**: a marker appears after a few consistent sightings and stays put as you move.
- **Maps:** on LiDAR devices, a **coloured 3D point cloud** of the space builds up as you walk. The stats panel shows the point count.
- **Save a Space:** tap the save button (bottom left) to save the map, objects and your path. Open saved Spaces from the cube icon on the home screen, view them in 3D, export them (`points.ply` opens in MeshLab, CloudCompare, Open3D and Blender), or tap **Continue in AR** to relocalize and keep mapping.

## 3. Connect a computer (Mac, Linux, Windows, Raspberry Pi)

On the computer, using Python 3.9 or newer on the same Wi-Fi as the phone:

> **Install from GitHub:** `flexml-companion` isn't on PyPI yet, so install it straight from this repository (below), or from a local clone with `pip install "./python[all]"`.

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml serve
```

FlexML finds the computer automatically: open the camera or **Network Setup** and it connects. Without auto-discovery, enter the IP address that `flexml serve` prints, or scan its QR code, in **Network Setup**.

`flexml serve` prints detections as they arrive, and you can type commands such as `start_live ar`, `set_threshold 0.5` or `get_status`. Useful options:

```bash
flexml serve --log session.jsonl   # save everything
flexml serve --map space.ply       # save the streamed 3D point cloud when you quit (Ctrl-C)
```

**Troubleshooting:**
- **macOS firewall:** if macOS asks whether Python may accept incoming connections, choose **Allow**.
- **Local Network permission:** the phone asks for it the first time. If you declined, turn it on in Settings › Privacy & Security › Local Network › FlexML.
- **Network isolation:** guest or corporate Wi-Fi often blocks devices from seeing each other. Use a home network or a phone hotspot.

### In your own code

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
                    print(d.track_id, d.label, d.confidence, d.center, d.distance)

asyncio.run(main())
```

## 4. Microcontrollers (ESP32, Arduino)

FlexML can send short text lines that a microcontroller reads with `sscanf`, such as `O 3 person 87 512 430 210 380 145`:

| | Wi-Fi (UDP) | Bluetooth LE |
|---|---|---|
| Turn on | Network Setup › Microcontrollers › **Send over Wi-Fi (UDP)**, then enter the board's IP and port 5005 | Network Setup › Microcontrollers › **Send over Bluetooth LE** |
| Example | [`examples/esp32/arduino/FlexML_UDP`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/esp32/arduino/FlexML_UDP), [`examples/esp32/micropython/flexml_udp.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/esp32/micropython/flexml_udp.py) | [`examples/esp32/arduino/FlexML_BLE`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/esp32/arduino/FlexML_BLE) |
| Commands to the phone | No (use Wi-Fi + WebSocket) | Yes: write text such as `set_threshold 0.5` |

The line format is in [Robot integration](robot-integration.md#compact-format).

## 5. ROS 2

In a sourced ROS 2 environment (Humble or newer):

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml ros2
```

This publishes detections, odometry, TF, the point cloud and object markers under `/flexml`, and accepts commands on `/flexml/command`. See [Robot integration › ROS 2](robot-integration.md#ros-2).

## 6. Settings for robots

| Setting | Where | Why |
|---|---|---|
| Phone mounted | Settings › Robot | Keeps the model's view upright when the phone is mounted flat or tilted |
| Lock screen rotation | Settings › Robot | Controls don't flip when the robot tilts |
| Screen off | Moon button, or double-tap the preview | Saves power and heat; inference and streaming continue |
| Max inference rate, 60 fps camera | Settings › Performance | Trade speed against heat and battery |
| Recording | Record button | Camera video, annotated video and every result (`timeline.jsonl`) |

## Where to go next
- [Bring your own model](bring-your-own-model.md): converting and tuning models for FlexML
- [Port with an AI agent](agents/README.md): drop `AGENTS.md` into your model project
- [Robot integration](robot-integration.md): commands, microcontrollers, ROS 2
- [Stream protocol](protocol.md): every message, field by field
