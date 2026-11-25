# Python examples

Install the library once:

```bash
pip install "flexml-companion[all] @ git+https://github.com/Arjun-2005aa/FlexML_SDK.git#subdirectory=python"
```

Run any script, then open **Network Setup** in FlexML on a phone on the same Wi-Fi. It finds the computer automatically.

| Script | What it does | Needs |
|---|---|---|
| [`print_detections.py`](print_detections.py) | Prints every detection with track ID, centre and distance | – |
| [`follow_person.py`](follow_person.py) | Locks onto one person and computes speed/turn for a differential-drive robot; plug in your motors in `drive()` | AR mode for real distances |
| [`save_point_cloud.py`](save_point_cloud.py) | Scans for N seconds and saves the coloured point cloud as PLY | AR mode; LiDAR for a dense cloud |
| [`occupancy_grid.py`](occupancy_grid.py) | Turns the point cloud (live or a saved PLY) into a top-down obstacle map (PGM + NumPy) | `numpy` |
| [`remote_control.py`](remote_control.py) | Command prompt for the phone: `start_live ar`, `set_model yolo`, `set_classes person,cup`… | Commands allowed in Network Setup |

Want something else? The data you can use is listed in [docs/data-reference.md](../../docs/data-reference.md), and project ideas in [docs/use-cases.md](../../docs/use-cases.md).
