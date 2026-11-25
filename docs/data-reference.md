# Data reference: what FlexML gives you

This page lists every piece of data the app can send, where to find it, and what is **not** available, so you can plan a robot before writing code. The exact JSON is in [protocol.md](protocol.md).

## Where to turn things on

All stream settings are in the app under **Network Setup**:

| Setting | Default | Controls |
|---|---|---|
| Stream › Rate | 15 per second | How often `inference` and `pose` are sent (5–60) |
| Stream › Inference results | on | `inference` messages |
| Stream › Camera pose (AR mode) | on | `pose` messages |
| Stream › 3D object map (AR mode) | on | `anchors` messages |
| Stream › 3D point cloud (AR mode) | on | `map` messages |
| Stream › IMU data | off | `imu` block inside `inference` |
| Stream › Segmentation mask image | off | `segmentation.maskPNG` (large) |
| Remote control › Accept commands from robots | on | whether `command` messages are obeyed |
| Microcontrollers › Send over Wi-Fi (UDP) / Bluetooth LE | off | the compact line format |

Your robot can change some of these at run time with commands (`set_stream_rate`, `set_rate`, `set_classes`, `set_threshold`…), see [robot-integration.md](robot-integration.md#commands-robot--phone).

## Available data

### Vision mode and AR mode

| Field | Type | Notes |
|---|---|---|
| `detections[].label`, `classId`, `confidence` | string, int, 0–1 | After the app's confidence/IoU thresholds and class filter |
| `detections[].box` | `[x, y, w, h]`, 0–1 | Top-left origin, in the **upright** camera image |
| `detections[].trackId` | int | Stable while the object stays in view; no need to match boxes yourself |
| `detections[].keypoints` | `[[x, y, conf], …]` | Pose models only |
| `classifications` | `[{label, confidence}]` | Classifier models |
| `segmentation` | size, per-class `coverage` (0–1), optional `maskPNG` | The mask image only when *Segmentation mask image* is on |
| `depth` | `width`, `height`, `min`, `max`, `center`, `relative` | **A summary**, not the depth image (see below) |
| `tensors` | name, shape, min, max, mean, first values | For models whose outputs FlexML doesn't recognise |
| `latencyMs` | preprocess / inference / postprocess | Per frame |
| `image` | size, orientation, `crop` | What the model actually saw |
| `imu` | acceleration, rotation rate, roll/pitch/yaw, gravity | When *IMU data* is on |

### AR mode only

| Data | Message | Notes |
|---|---|---|
| 3D position of each detection | `detections[].world` (metres) | ARKit world frame: y up, origin where AR started |
| Distance to each detection | `detections[].distance` (metres) | **Measured** with LiDAR; estimated by raycasting otherwise |
| Phone pose | `pose.position`, `orientation` (quaternion), `transform` (4×4) | Trust only when `tracking == "normal"` |
| Camera intrinsics | `pose.intrinsics` (3×3), `imageResolution` | For projecting points into the image |
| Object map | `anchors[]`: id, label, position, confidence, sightings | An object appears after 5 agreeing sightings and stays anchored |
| Point cloud | `map`: base64 float32 xyz + uint8 rgb | Incremental, ~1/s, ≤ 20,000 new points per message, 2 cm voxels |

### Files you can export from the app

| Export | Contents |
|---|---|
| **Recording** (Recordings › Share) | Camera video, optional annotated video, `timeline.jsonl` (every `inference`/`pose`/`anchors` message), `map.json` |
| **Space** (Spaces › Share) | `points.ply` (binary, metres), `objects.json`, `trajectory.json` (2 samples/s), `worldmap.arworld`, `space.json` |

## The point cloud in detail

The point cloud **is** streamed. If you don't receive it, check:

| Symptom | Cause | Fix |
|---|---|---|
| No `map` messages at all | Vision mode | Switch to **AR**, or `start_live` with `mode="ar"` |
| No `map` messages at all | Listening on UDP/BLE | Point clouds are WebSocket/HTTP only. Use `flexml serve` or the Python `Server` |
| No `map` messages at all | Toggle off | *Network Setup › Stream › 3D point cloud (AR mode)* |
| Only a few grey points | Device has no LiDAR | Expected: you get ARKit's sparse feature points. Use a Pro iPhone (12 Pro or later) or iPad Pro for dense colour |
| Cloud "restarts" | `reset: true` chunk | New AR session, `reset_map`, or a reconnect. Discard what you had |
| Cloud grows slowly | By design | ~1 message/s, only *new* points. Move the phone slowly to cover the room |

How to use it:
- **Python:** `phone.map` accumulates automatically. `phone.map.to_numpy()` returns `(N, 3)` float32 positions and `(N, 3)` uint8 colours; `phone.map.save_ply("room.ply")` writes a PLY.
- **CLI:** `flexml serve --map room.ply`.
- **ROS 2:** `/flexml/points` (`sensor_msgs/PointCloud2`, frame `flexml_map`, ROS axes).
- **Raw:** decode `positions` as little-endian float32 triplets and `colors` as uint8 triplets; `start` tells you where the chunk goes in the whole cloud.

Coordinates are metres in ARKit's world frame (x right, **y up**, −z forward at start). The ROS bridge converts to REP 103 (x forward, y left, z up).

## Not available (today)

| Not sent | Why / alternative |
|---|---|
| **Live camera video or JPEG frames** | Too heavy for a robot link. Record on the phone and share the video, or use the annotated recording |
| **Full depth image / LiDAR depth map** | Only the `depth` summary for depth models, and per-detection `distance`. Use the point cloud for geometry |
| **ARKit scene mesh** (triangles) | Not exported. The point cloud and `points.ply` are the geometry outputs |
| **Point cloud over UDP or Bluetooth** | Too large for microcontrollers. Use a Pi/computer with WebSocket, or the `P` pose line on the MCU |
| **Point cloud / pose / distances in Vision mode** | Need ARKit world tracking, i.e. AR mode |
| **Full raw output tensors** | Only summaries (`tensors`). Export the model in a layout FlexML recognises ([bring-your-own-model.md](bring-your-own-model.md)) |
| **Data while the app is in the background** | iOS pauses the camera. Keep FlexML open; use the screen-off mode (`screen` command) to save power |

If you need one of these, open an issue describing your robot and what you'd do with the data.
