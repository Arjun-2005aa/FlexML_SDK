# FlexML + ROS 2

The bridge is part of the Python package: `flexml ros2` receives the phone's stream and republishes it as standard ROS 2 topics (rclpy; Humble, Jazzy or Rolling).

## Run the bridge

```bash
source /opt/ros/humble/setup.bash                       # or jazzy / rolling
sudo apt install ros-humble-vision-msgs                 # for /flexml/detections
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
flexml ros2                                             # --namespace flexml --port 8080
```

Open **Network Setup** in FlexML (it finds the computer), then start AR so pose, objects and the point cloud flow.

| Topic | Type | Notes |
|---|---|---|
| `/flexml/detections` | `vision_msgs/Detection2DArray` | Pixels of the upright image; `id` = track ID; 3D position in `results[].pose` (AR) |
| `/flexml/inference` | `std_msgs/String` | Full JSON message (normalised boxes, distances, everything) |
| `/flexml/odom` | `nav_msgs/Odometry` | `flexml_map` → `flexml_device`, also on `/tf` |
| `/flexml/points` | `sensor_msgs/PointCloud2` | Accumulated coloured point cloud (x, y, z, rgb) in `flexml_map`, ~1 Hz |
| `/flexml/objects` | `visualization_msgs/MarkerArray` | Labelled spheres for mapped objects |
| `/flexml/command` (sub) | `std_msgs/String` | e.g. `ros2 topic pub --once /flexml/command std_msgs/String "data: 'start_live ar'"` |
| `/flexml/reply` | `std_msgs/String` | Command results (JSON) |

## Frames

FlexML converts ARKit (y up, −z forward) to REP 103 (x forward, y left, z up).

- `flexml_map`: where the AR session started, gravity-aligned.
- `flexml_device`: the phone; x out of the back camera, z up.

Tie the phone to your robot with a static transform for the mount:

```bash
ros2 run tf2_ros static_transform_publisher --x 0.10 --z 0.20 --frame-id base_link --child-frame-id flexml_device
```

Then in RViz set the fixed frame to `flexml_map` and add `PointCloud2` (`/flexml/points`), `MarkerArray` (`/flexml/objects`) and `TF`.

## Example: follow a person

[`follow_person_node.py`](follow_person_node.py) subscribes to `/flexml/inference` and publishes `/cmd_vel`:

```bash
python3 follow_person_node.py --ros-args -p target:=person -p follow_distance:=1.2 -r cmd_vel:=/cmd_vel
```

## Ideas

- **Navigation:** feed `/flexml/points` to `pointcloud_to_laserscan` or a Nav2 obstacle layer; use `/flexml/odom` as visual odometry (fuse with wheel odometry in `robot_localization`).
- **Semantic map:** subscribe to `/flexml/objects` and store labels with positions.
- **Commands from your stack:** publish to `/flexml/command` (`set_model yolo`, `set_classes person`, `reset_map`, `save_space Lab`).

Protocol and data details: [../../docs/protocol.md](../../docs/protocol.md), [../../docs/data-reference.md](../../docs/data-reference.md).
