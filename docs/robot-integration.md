# Robot Integration

There are three ways to connect FlexML to a robot:
- **WebSocket + JSON (Wi-Fi):** a computer, Raspberry Pi or Jetson receives everything (detections, pose, objects, 3D map) and can send commands back. Use the `flexml-companion` Python package or any WebSocket library.
- **Compact lines (UDP or Bluetooth LE):** short text lines for microcontrollers. Bluetooth works without Wi-Fi.
- **ROS 2:** `flexml ros2` republishes the stream as standard ROS 2 topics.

---

## Commands (robot → phone)

Send commands as JSON over the WebSocket, or as one line of text over Bluetooth or the `flexml serve` prompt. Every command gets a reply.

```json
{"type": "command", "id": "17", "command": "set_threshold", "confidence": 0.5}
```
```json
{"v": 2, "type": "reply", "id": "17", "command": "set_threshold", "ok": true, "result": {"confidence": 0.5, "iou": 0.45}}
```
Over Bluetooth, the same command is `set_threshold 0.5`, and the reply is `OK set_threshold confidence=0.500 iou=0.450` (or `ERR <command> <reason>`).

| Command | Parameters (JSON / text) | Effect |
|---|---|---|
| `ping` | – | Replies `pong` |
| `get_status` | – | live, mode, model, task, inferences/s, latency, thermal state, objects, map points, recording |
| `list_models` | – | Models in the library |
| `start_live` | `mode`: `vision` or `ar` (optional) | Opens the camera and starts inference |
| `stop_live` | – | Closes the camera |
| `set_mode` | `mode` | Switches between Vision and AR |
| `set_model` | `model`: name, or a prefix like `yolo` | Switches model (loads it if live) |
| `set_threshold` | `confidence` 0–1, `iou` 0–1 | Detection or classification thresholds |
| `set_classes` | `classes`: list, or text `person,cup` / `all` | Only report these labels |
| `set_rate` | `hz` (0 = max) | Inference rate limit |
| `set_stream_rate` | `hz` | WebSocket stream rate |
| `start_recording` / `stop_recording` | – | Records video and results on the phone |
| `reset_map` | – | Clears the AR object map and point cloud |
| `save_space` | `name` | Saves the current AR map as a Space |
| `torch` | `on`: true/false | Torch (Vision mode) |
| `screen` | `on`: true/false | Turns the preview off or on; inference keeps running |

Commands can be turned off in **Network Setup › Remote control**.

**From Python:**

```python
import asyncio
import flexml_companion as flexml

async def main():
    async with flexml.Server() as phone:
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        await phone.command("set_model", model="yolo")
        await phone.command("set_classes", classes=["person"])
        print(await phone.command("get_status"))

asyncio.run(main())
```

---

## Compact format

<a id="compact-format"></a>

These are text lines with integers only. Over UDP, each datagram is one frame; over Bluetooth, each notification is one line.

```
F <frame> <time_ms> <objects>
O <track_id> <label> <conf_pct> <cx> <cy> <w> <h> <dist_cm>
C <label> <conf_pct>
S <label> <coverage_pct>
D <centre_mm>
P <x_cm> <y_cm> <z_cm> <heading_deg>
```

- **Box coordinates:** `cx cy w h` are 0–1000 of the upright camera image (0,0 is top-left).
- **`track_id`** stays the same while the object is in view.
- **`dist_cm`** is the distance in AR mode, or −1 when unknown.
- **`P`** is the phone's position in the AR world (y up) and its heading in degrees (0 = the direction it faced when AR started).
- **Labels** have spaces replaced by `_`, and at most 12 objects are sent per frame.

**Parsing in C:**

```c
int id, conf, cx, cy, w, h, dist; char label[32];
if (sscanf(line, "O %d %31s %d %d %d %d %d %d", &id, label, &conf, &cx, &cy, &w, &h, &dist) == 8) { /* … */ }
```

**UDP:** turn on **Network Setup › Microcontrollers › Send over Wi-Fi (UDP)** and enter the board's IP and port (default 5005). Leave the IP blank to use the companion computer's address. On a Raspberry Pi, `flexml udp` prints the frames.

**Bluetooth LE:** turn on **Send over Bluetooth LE**. FlexML advertises as **FlexML** with the Nordic UART Service:

| Characteristic | UUID | Direction |
|---|---|---|
| Service | `6E400001-B5A3-F393-E0A9-E50E24DCCA9E` | |
| TX (notify) | `6E400003-B5A3-F393-E0A9-E50E24DCCA9E` | phone → device: one line per notification |
| RX (write) | `6E400002-B5A3-F393-E0A9-E50E24DCCA9E` | device → phone: text commands |

You can test with the nRF Connect app before writing firmware. Bluetooth runs only while FlexML is in the foreground; keep it open, using screen-off mode if needed.

**Examples:**
- [`examples/esp32/arduino/FlexML_UDP`](../examples/esp32/arduino/FlexML_UDP): ESP32 over Wi-Fi; steers toward a person.
- [`examples/esp32/arduino/FlexML_BLE`](../examples/esp32/arduino/FlexML_BLE): ESP32 over Bluetooth; prints detections and forwards commands typed in the Serial Monitor.
- [`examples/esp32/micropython/flexml_udp.py`](../examples/esp32/micropython/flexml_udp.py): MicroPython over UDP.

---

## ROS 2

<a id="ros-2"></a>

```bash
source /opt/ros/humble/setup.bash        # or jazzy, rolling…
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml ros2                              # --namespace flexml --port 8080
```

| Topic | Type | Notes |
|---|---|---|
| `/flexml/detections` | `vision_msgs/Detection2DArray` | Pixels of the upright image; `id` is the track ID; 3D position in `results[].pose` (AR). Needs `ros-<distro>-vision-msgs` |
| `/flexml/inference` | `std_msgs/String` | Full JSON message |
| `/flexml/odom` | `nav_msgs/Odometry` | `flexml_map` → `flexml_device`, also broadcast on `/tf` |
| `/flexml/points` | `sensor_msgs/PointCloud2` | Coloured map (x, y, z, rgb) in `flexml_map`, ~1 Hz |
| `/flexml/objects` | `visualization_msgs/MarkerArray` | Labelled spheres for mapped objects |
| `/flexml/command` (subscribed) | `std_msgs/String` | e.g. `ros2 topic pub --once /flexml/command std_msgs/String "data: 'start_live ar'"` |
| `/flexml/reply` | `std_msgs/String` | Command results (JSON) |

**Frames:** FlexML converts ARKit coordinates (y up, −z forward) to ROS REP 103 (x forward, y left, z up).
- **`flexml_map`:** where AR started, gravity-aligned.
- **`flexml_device`:** the phone, with x pointing out of the back camera and z up.
- **Linking to your robot:** publish a static transform from your robot's `base_link` to `flexml_device` for the mount, e.g. `ros2 run tf2_ros static_transform_publisher --x 0.1 --z 0.2 --frame-id base_link --child-frame-id flexml_device` (adjust to your mount). Then RViz shows the map, objects and robot together.

---

## Tips for reliable robots

- **AR before moving:** start AR with `start_live ar` before the robot drives, then move slowly for the first seconds so tracking initialises. Watch `tracking` in `pose` messages and only trust poses where it's `normal`.
- **Stream rate:** use 10–15/s. When the network can't keep up, FlexML always sends the latest data rather than queueing old messages.
- **Mounting:** set **Settings › Robot › Phone mounted** to the real mount and turn on **Lock screen rotation**.
- **Heat:** keep the phone ventilated and out of direct sun. FlexML slows itself down when hot (20/s when warm, 10/s when hot) instead of stopping.
- **Power:** screen-off mode and a modest rate double battery life. For long runs, power the phone from the robot.
