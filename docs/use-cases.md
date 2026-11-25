# What you can build with FlexML

Each idea lists the data it uses, the connection, and a sketch. The runnable examples are in [`examples/`](../examples). Data details: [data-reference.md](data-reference.md).

---

## 1. Person-following robot
**Uses:** `detections` (box centre, `trackId`, `distance` in AR) · **Link:** UDP to an ESP32, or Python on a Pi

Steer so the target's box centre stays at x = 0.5; drive forward while `distance` is above your follow distance. Lock onto one `trackId` so the robot doesn't jump between people.

```python
error = d.center[0] - 0.5            # −0.5 … 0.5
turn = -1.2 * error                  # P controller
speed = 0.3 if (d.distance or 2.0) > 1.0 else 0.0
```
Runnable: [`examples/python/follow_person.py`](../examples/python/follow_person.py), [`examples/esp32/arduino/FlexML_UDP`](../examples/esp32/arduino/FlexML_UDP), ROS 2: [`examples/ros2/follow_person_node.py`](../examples/ros2/follow_person_node.py).

## 2. Object-seeking rover ("find the red cup")
**Uses:** `set_classes`, `detections[].world` · **Link:** Python

Send `set_classes` with the target class, rotate until it appears, then drive toward its `world` position (AR mode), which stays valid even when the object leaves the frame for a moment. Use `anchors` to remember objects you've already visited.

## 3. Obstacle map for navigation
**Uses:** `map` point cloud, `pose` · **Link:** Python or ROS 2

Project the point cloud onto the floor: points between ~10 cm and your robot's height are obstacles. Grid them at 5 cm and you have an occupancy map for path planning.
- Python: [`examples/python/occupancy_grid.py`](../examples/python/occupancy_grid.py) writes a PGM image you can open anywhere.
- ROS 2: feed `/flexml/points` to `pointcloud_to_laserscan` or an Nav2 costmap's obstacle layer, with a static transform from `base_link` to `flexml_device`.

## 4. Visual odometry for robots without encoders
**Uses:** `pose` · **Link:** ROS 2 (`/flexml/odom` + TF) or Python

Mount the phone rigidly, start AR before moving, and use the phone's 6-DoF pose as the robot's odometry. Great for tracked robots, legged robots, boats and anything whose wheels slip. Only trust poses where `tracking == "normal"`.

## 5. "Where did I leave it?" semantic map
**Uses:** `anchors` · **Link:** Python

Walk around once in AR mode; each object type is anchored in 3D after five sightings. Keep `{label: position}` in a dictionary and answer "where is my backpack?" with a distance and direction from the current `pose`. Save a **Space** in the app to keep the map.

## 6. Safety stop near machines
**Uses:** `detections` with `distance` · **Link:** Bluetooth LE to an ESP32 driving a relay (no Wi-Fi needed)

If a `person` is closer than a threshold, cut power to a motor or sound a buzzer. The compact `O` line includes `dist_cm`. Add hysteresis (e.g. stop under 1.0 m, resume above 1.5 m) to avoid chattering. Treat it as a teaching demo, not a certified safety system.

## 7. Pan-tilt camera or drone gimbal tracking
**Uses:** box centre (`cx`, `cy` in the compact format) · **Link:** UDP or BLE to an ESP32 with two servos

Two P (or PID) loops on `cx − 500` and `cy − 500`, one per servo. Lock to a `track_id` for stability.

## 8. Room scanning and 3D capture
**Uses:** `map`, Spaces · **Link:** WebSocket, or export from the app

Collect the coloured cloud live with [`examples/python/save_point_cloud.py`](../examples/python/save_point_cloud.py), or save a Space in the app and share `points.ply`. Open it in MeshLab, CloudCompare, Open3D or Blender, measure rooms, or use it as a prior map for a robot.

## 9. Dataset collection for your own models
**Uses:** recordings (`timeline.jsonl` + video), or `flexml serve --log session.jsonl` · **Link:** WebSocket

Run a detector as a "pre-labeller", record sessions, and use the timeline to pick frames with low confidence or rare classes for labelling. Retrain, convert with [coremltools](https://github.com/apple/coremltools), and load the new model in FlexML.

## 10. Smart-home and IoT triggers
**Uses:** `detections` · **Link:** Python → MQTT / HTTP / Home Assistant

Forward events like "person at the door", "package detected" or "cat on the table" to MQTT or a webhook. Use `trackId` to send one event per new object instead of one per frame.

## 11. Classroom and workshop labs
**Uses:** classification or detection over BLE · **Link:** ESP32 with LEDs/servos

Students train a classifier in Create ML, AirDrop it to the phone, and an ESP32 lights an LED per class (`C <label> <conf_pct>` lines). No Wi-Fi, laptop or cloud needed.

## 12. Fleet or multi-robot monitoring
**Uses:** `pose`, `anchors`, `get_status` · **Link:** WebSocket, one companion per phone (different ports)

Run several `Server(port=…)` instances, poll `get_status` (inference rate, thermal state, map size), and show every phone's position on one map.

## 13. Agriculture and inspection
**Uses:** a custom detector + `world` positions · **Link:** Python

Count fruit, weeds or defects with a custom YOLO model and log their 3D positions along a row. The 5-sighting anchor rule removes most double counts.

---

**Tips that apply to all of them:** start AR before moving and move slowly for the first seconds; use a stream rate of 10–15/s; set the phone's real mount in *Settings › Robot*; keep the phone cool and powered for long runs. More in [robot-integration.md](robot-integration.md#tips-for-reliable-robots).
