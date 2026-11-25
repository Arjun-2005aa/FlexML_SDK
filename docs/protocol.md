# FlexML Stream Protocol (v2)

FlexML sends one JSON object per message, either as WebSocket text frames or as HTTP `POST` bodies (`Content-Type: application/json`). The reference implementation is the [`flexml-companion`](https://github.com/Arjun-2005aa/FlexML_SDK/tree/main/python) Python package.

Every message has these fields:

| Field | Meaning |
|---|---|
| `v` | Protocol version (`2`) |
| `type` | `hello`, `inference`, `pose`, `anchors`, `map` or `reply` (phone → computer); `command` (computer → phone) |
| `t` | Timestamp in seconds on the device's monotonic clock. Camera, AR and IMU timestamps all use this clock, so messages can be aligned with each other. |

## Coordinates

- **Image coordinates** (`box`, `keypoints`) are normalized to `0…1` with the origin at the **top-left**. They are relative to the **upright** camera image, meaning the frame rotated so that up is up for the configured mount (`image.orientation`).
- `image.crop` is the region of that upright image the model actually saw, as `[x, y, w, h]`. With *Fit*, it extends past `0…1` (the letterbox bars).
- **World coordinates** (`world`, `position`, anchors) are in metres, in ARKit's world frame:
  - y points up, against gravity.
  - The origin is where the AR session started.
  - The frame is right-handed.

## `hello`
Sent once on connect.
```json
{"v":2,"type":"hello","t":1234.5,"app":"FlexML 1.0","device":"iPhone","system":"iOS 27.0",
 "capabilities":{"ar":true,"lidar":false,"neuralEngine":true}}
```

## `inference`
Sent at the configured stream rate. Each field appears only when the model produces it.
```json
{
  "v": 2, "type": "inference", "t": 1234.567, "frame": 812,
  "model": {"name": "yolo11n", "task": "detection"},
  "latencyMs": {"preprocess": 0.9, "inference": 11.2, "postprocess": 1.4},
  "image": {"width": 720, "height": 1280, "orientation": "right", "crop": [0, 0.21875, 1, 0.5625]},
  "detections": [
    {"trackId": 17, "label": "person", "classId": 0, "confidence": 0.91, "box": [0.31, 0.40, 0.22, 0.35],
     "keypoints": [[0.42, 0.43, 0.97]],
     "world": [0.12, -0.30, -1.85], "distance": 1.9, "anchor": "6F0C…"}
  ],
  "classifications": [{"label": "keyboard", "confidence": 0.82}],
  "segmentation": {"width": 513, "height": 513, "classes": [{"label": "person", "coverage": 0.27}],
                   "maskPNG": "<base64, only when enabled>"},
  "depth": {"width": 518, "height": 392, "min": 0.1, "max": 7.9, "center": 2.3, "relative": true},
  "tensors": [{"name": "var_914", "shape": [1, 10], "min": -3.2, "max": 5.1, "mean": 0.2, "first": [0.1, 0.4]}],
  "imu": {"timestamp": 1234.56, "accelerationX": 0.01, "rotationRateZ": 0.002, "roll": 0.1, "pitch": 1.5, "yaw": 0.3,
          "gravityX": 0, "gravityY": -1, "gravityZ": 0}
}
```

Field notes:
- **`trackId`** stays the same while the same object remains in view (boxes are tracked and smoothed between frames), so you can follow objects without matching boxes yourself.
- **`world`, `distance` and `anchor`** are filled in AR mode only. With LiDAR, the distance is measured. Without LiDAR, it's estimated by raycasting against detected surfaces.
- **`depth`** values are in the model's own units. Most monocular models output *relative* depth.
- **`tensors`** is sent for models whose output FlexML doesn't recognise, so you can decode them yourself.
- **`imu`** is included when *IMU data* is enabled in *Connect › Stream*.

## `pose` (AR mode)
The device's 6-DoF pose from ARKit visual-inertial odometry, sent at the stream rate.
```json
{"v":2,"type":"pose","t":1234.567,"tracking":"normal",
 "position":[0.12,0.01,-0.40],"orientation":[0.0,0.38,0.0,0.92],
 "transform":[...16 floats, column-major camera-to-world...],
 "intrinsics":[...9 floats, column-major, sensor pixels...],"imageResolution":[1920,1440]}
```

Field notes:
- **`tracking`** is one of `normal`, `initializing`, `relocalizing`, `excessiveMotion`, `insufficientFeatures` or `notAvailable`. Only trust poses whose state is `normal`.
- **`orientation`** is a quaternion `[x, y, z, w]`.
- **Camera axes** follow ARKit: x right, y up, and the camera looks down −z.

## `anchors` (AR mode)
The object map, sent about twice a second. An object is added only after at least 5 sightings that agree on its position; it is then held by an ARKit anchor, so its position stays consistent as tracking refines. The map starts empty in every AR session.
```json
{"v":2,"type":"anchors","t":1234.6,
 "anchors":[{"id":"6F0C…","label":"chair","position":[1.2,-0.4,-2.1],"confidence":0.88,"sightings":14,"lastSeen":1234.5}]}
```

## `map` (AR mode)
The 3D point cloud, sent incrementally about once a second (up to 20,000 new points per message). Points are kept on a 2 cm voxel grid, so revisiting an area doesn't duplicate points.
```json
{"v":2,"type":"map","t":1240.0,"reset":false,"start":180000,"count":4211,"total":184211,
 "positions":"<base64: little-endian Float32 x,y,z per point>","colors":"<base64: R,G,B bytes per point>"}
```

Field notes:
- **`reset: true`** marks the first chunk of a new map (new AR session, map reset, or a new connection). Discard previous points when you see it.
- **Coordinates** are metres in the same world frame as `pose` and `anchors`.
- **Device support:** LiDAR devices produce a dense, coloured cloud. Other devices send ARKit's sparse feature points (grey).

## `command` and `reply`
The computer can control the phone by sending `command` messages over the same WebSocket. Each one is answered with a `reply` carrying the same `id`:

```json
{"type":"command","id":"5","command":"set_model","model":"yolo"}
{"v":2,"type":"reply","id":"5","command":"set_model","ok":true,"result":{"model":"YOLOv3 Tiny (sample)","task":"detection"}}
```

The full command list is in [Robot integration](robot-integration.md#commands-robot--phone).

## Discovery
`flexml serve` advertises the Bonjour service `_flexml._tcp` with TXT keys `ip`, `ws`, `http`, `name` and `v`. The app browses for it and connects automatically when no address is configured.

## Compact format (microcontrollers)
UDP and Bluetooth LE use one-line integer records (`F`, `O`, `C`, `S`, `D`, `P`), described in [Robot integration](robot-integration.md#compact-format).

## Rates and backpressure
- **Rates:** each message type is limited to the rate chosen in *Connect › Stream* (5–60 per second). Anchors are capped at 2 per second.
- **Backpressure:** at most two messages are in flight. When the network can't keep up, newer messages replace older ones rather than queueing, so the data you receive is always recent.

## Recordings and Spaces
- **Recordings:** each recording's `timeline.jsonl` contains the same `inference`, `pose` and `anchors` messages, one per line. `map.json` is the final object map.
- **Spaces:** a saved Space is a folder containing:
  - `points.ply`: binary PLY with float x, y, z and uchar r, g, b, in metres.
  - `objects.json`: the anchor list.
  - `trajectory.json`: `t`, `position` and `orientation`, two samples per second.
  - `worldmap.arworld`: ARKit's world map, used to relocalize on the device.
  - `space.json`: metadata.
