# Examples

All examples live in the [`examples/`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples) folder of the repository. Clone it to run them:

```bash
git clone https://github.com/Arjun-2005aa/FlexML_SDK.git
cd FlexML_SDK
pip install -e "./python[all]"
```

## Python

Run a script, then open **Network Setup** in FlexML on a phone on the same Wi-Fi.

| Script | What it does |
|---|---|
| [`print_detections.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/python/print_detections.py) | Prints every detection with track ID, centre and distance |
| [`follow_person.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/python/follow_person.py) | Locks onto one person and computes speed/turn for a differential-drive robot (`drive()` is where your motor code goes) |
| [`save_point_cloud.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/python/save_point_cloud.py) | Scans for N seconds in AR mode and saves the coloured point cloud as PLY |
| [`occupancy_grid.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/python/occupancy_grid.py) | Turns the point cloud (live or a saved PLY) into a top-down obstacle map (PGM + NumPy) |
| [`remote_control.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/python/remote_control.py) | Command prompt for the phone: `start_live ar`, `set_model yolo`, `set_classes person,cup`… |

```bash
python examples/python/save_point_cloud.py --seconds 30 --out room.ply
python examples/python/occupancy_grid.py --ply room.ply --out map
```

## ROS 2

```bash
source /opt/ros/humble/setup.bash
flexml ros2                                   # publishes /flexml/* topics
python3 examples/ros2/follow_person_node.py   # subscribes /flexml/inference, publishes /cmd_vel
```

Topics: `/flexml/detections`, `/flexml/inference`, `/flexml/odom` (+ TF), `/flexml/points` (PointCloud2), `/flexml/objects`, `/flexml/command`, `/flexml/reply`. Frames, RViz and Nav2 notes: [ROS 2 guide on GitHub](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/ros2) and [Robot integration › ROS 2](robot-integration.md#ros-2).

## ESP32

Microcontrollers receive the **compact format** (one integer-only line per object) over Wi-Fi UDP or Bluetooth LE. Point clouds are not sent to microcontrollers.

| Example | Link | What it does |
|---|---|---|
| [`arduino/FlexML_UDP`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/esp32/arduino/FlexML_UDP) | Wi-Fi UDP | Steers toward a person; LED when closer than 1 m |
| [`arduino/FlexML_BLE`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/esp32/arduino/FlexML_BLE) | Bluetooth LE | Prints detections; forwards Serial Monitor commands to the phone |
| [`micropython/flexml_udp.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/esp32/micropython/flexml_udp.py) | Wi-Fi UDP | MicroPython parser and target direction |
| [`micropython/oled_udp.py`](https://github.com/Arjun-2005aa/FlexML_SDK/blob/main/examples/esp32/micropython/oled_udp.py) | Wi-Fi UDP | Detections on an SH1106 OLED, LED for a target |

In FlexML: **Network Setup › Microcontrollers** › *Send over Wi-Fi (UDP)* (board IP, port 5005) or *Send over Bluetooth LE*. Format and UUIDs: [Robot integration › Compact format](robot-integration.md#compact-format). Setup steps: [ESP32 guide on GitHub](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/examples/esp32).

More ideas: [What you can build](use-cases.md).
