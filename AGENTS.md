# AGENTS.md: FlexML SDK

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot, Gemini CLI…) working in this repository or helping a user build on it. Read this before writing code.

## What this is

[FlexML](README.md) is an iOS app that runs Core ML vision models on the iPhone/iPad camera, tracks objects in 3D with ARKit/LiDAR, and **streams the results to a robot**. The app is closed source; this repository is the open **receiving side**:

- `python/flexml_companion/`: the reference client library and the `flexml` CLI.
- `examples/`: runnable Python, ROS 2 and ESP32 code.
- `docs/`: the protocol and data contracts. **These docs are the source of truth for message formats.**

The phone is the **client**: it connects to a WebSocket server on the user's computer (default port 8080, Bonjour service `_flexml._tcp`). Your code is the **server**. Microcontrollers instead *receive* UDP datagrams or Bluetooth LE notifications from the phone.

## Repository map

| Path | Purpose |
|---|---|
| `python/flexml_companion/server.py` | `Server`: WebSocket + HTTP receiver, Bonjour advertising, typed message stream, `command()` |
| `python/flexml_companion/messages.py` | Dataclasses `Hello`, `Inference`, `Detection`, `Pose`, `Anchors`, `Anchor`, `MapChunk`, `PointCloud`, `Reply`; `parse()` |
| `python/flexml_companion/compact.py` | Parser and UDP listener for the microcontroller line format |
| `python/flexml_companion/frames.py` | ARKit ↔ ROS (REP 103) coordinate conversion |
| `python/flexml_companion/ros2_bridge.py` | `flexml ros2`: publishes ROS 2 topics (imports `rclpy` lazily) |
| `python/flexml_companion/discovery.py` | Bonjour advertiser (optional `zeroconf`) |
| `python/flexml_companion/modelcheck.py` | `flexml check-model`: will a Core ML model run well in FlexML? |
| `python/flexml_companion/cli.py` | `flexml serve | udp | ros2 | check-model` |
| `python/tests/` | `unittest` tests (no network or phone needed) |
| `examples/python/` | Standalone scripts that use only the public API |
| `examples/ros2/` | `rclpy` node examples |
| `examples/esp32/` | Arduino (`.ino`) and MicroPython examples for the compact format |
| `docs/protocol.md` | JSON message reference (v2) |
| `docs/data-reference.md` | What data exists, defaults, and what is **not** available |
| `docs/robot-integration.md` | Commands, compact format, Bluetooth UUIDs, ROS 2 topics and frames |
| `docs/agents/` | A *separate* kit for porting a user's ML model to Core ML (copy into *their* model project) |

## The data contract in brief

All JSON messages have `v` (= 2), `type` and `t` (seconds, device monotonic clock).

| `type` | When | Key fields |
|---|---|---|
| `hello` | once on connect | `app`, `device`, `system`, `capabilities{ar, lidar, neuralEngine}` |
| `inference` | stream rate | `detections[]{trackId, label, confidence, box[x,y,w,h] 0–1 top-left, keypoints?, world?, distance?}`, `classifications`, `segmentation`, `depth` (summary), `tensors`, `imu?` |
| `pose` | stream rate, AR | `tracking`, `position`, `orientation` [x,y,z,w], `transform` (16, column-major), `intrinsics` (9) |
| `anchors` | ~2/s, AR | `anchors[]{id, label, position, confidence, sightings}` |
| `map` | ~1/s, AR | incremental point cloud: base64 float32 `positions`, uint8 `colors`, `start`, `count`, `total`, `reset` |
| `reply` | after a command | `id`, `command`, `ok`, `result` / `error` |

Rules that bite:
- **World coordinates are ARKit:** metres, **y up**, origin where AR started. Convert with `frames.py` for ROS.
- **Boxes are normalised to the upright image**, origin top-left.
- **AR-only data** (`world`, `distance`, `pose`, `anchors`, `map`) is absent in Vision mode. Check for `None`.
- **Only trust poses with `tracking == "normal"`** (`Pose.is_tracking`).
- **Point clouds never go over UDP/BLE.** Accumulate `map` chunks; discard on `reset: true` (`PointCloud.add` does this).
- **Newest data wins:** the phone drops stale messages under load. Don't assume every frame arrives.

## Python API you should use

```python
import asyncio, flexml_companion as flexml

async def main():
    async with flexml.Server(port=8080) as phone:      # advertise=True by default
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")   # raises FlexMLError on rejection
        async for msg in phone.messages():             # typed messages; newest wins if you're slow
            if isinstance(msg, flexml.Inference): ...
        # latest state without iterating: phone.pose, phone.objects, phone.map (PointCloud), phone.hello
        # callbacks: phone.on("inference", fn)

asyncio.run(main())
```

`Detection.center` and `Pose.is_tracking` are properties. `PointCloud.to_numpy()` needs numpy; `save_ply()` doesn't. Text commands (`"set_threshold 0.5"`) go through `phone.command_text()`. The full command list is in `docs/robot-integration.md`.

## Working conventions

- **Python ≥ 3.9**, standard library + `websockets` only in the core. Optional dependencies (`zeroconf`, `qrcode`, `numpy`, `coremltools`, `rclpy`) must be imported lazily so the core still imports without them.
- **Don't change the wire format here.** The app defines it. If you need a field the protocol lacks, say so; don't invent one. Update `docs/protocol.md` and `messages.py` together only to *match* the app.
- **Examples must run as-is** against the public API (`import flexml_companion as flexml`), have a docstring with the exact run command, and never contain real Wi-Fi credentials (use `your-wifi` / `your-password`).
- **Docs:** short, task-first, with copy-pasteable commands. Cross-link instead of duplicating.
- **Tests** for any parsing change: add a case to `python/tests/test_flexml.py` using a literal JSON or compact message.

## Commands

```bash
cd python
pip install -e ".[all]"                       # library + CLI + optional extras
python -m unittest discover -s tests          # run tests (no phone needed)
flexml serve --log session.jsonl              # receive from a real phone; replay-able log
flexml udp                                    # print the compact stream
flexml check-model My.mlpackage --json        # model compatibility (needs the [check] extra)
```

To test without a phone, feed recorded lines to `flexml_companion.parse()` (each line of a `--log` file or a recording's `timeline.jsonl` is one message).

## When a user asks you to build something

1. Find the data they need in `docs/data-reference.md` and confirm it exists (and in which mode / transport).
2. Start from the closest example in `examples/` and keep its structure.
3. For robots: stop the motors when the target is lost or the connection drops, and start AR before moving.
4. For new models: point them at [coremltools](https://github.com/apple/coremltools) and the `docs/agents/` porting kit, and validate with `flexml check-model`.
