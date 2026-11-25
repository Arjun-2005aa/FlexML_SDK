# ESP32 examples

Microcontrollers get FlexML's **compact format**: short integer-only text lines, one UDP datagram (or one Bluetooth LE notification line) per frame. It carries detections, classifications, segmentation coverage, depth and the phone's position, **not** point clouds (use a Pi or computer with the Python library for those; see [../../docs/data-reference.md](../../docs/data-reference.md)).

```
F <frame> <time_ms> <objects>
O <track_id> <label> <conf_pct> <cx> <cy> <w> <h> <dist_cm>     cx cy w h: 0–1000, dist −1 if unknown
C <label> <conf_pct>
S <label> <coverage_pct>
D <centre_mm>
P <x_cm> <y_cm> <z_cm> <heading_deg>
```

Parse one object in C: `sscanf(line, "O %d %31s %d %d %d %d %d %d", &id, label, &conf, &cx, &cy, &w, &h, &dist) == 8`.

## Examples

| Example | Link | What it does |
|---|---|---|
| [`arduino/FlexML_UDP`](arduino/FlexML_UDP) | Wi-Fi UDP | Steers toward a person (LEFT / RIGHT / AHEAD), LED when closer than 1 m. Replace `steer()` with motor code |
| [`arduino/FlexML_BLE`](arduino/FlexML_BLE) | Bluetooth LE | Connects to the phone (Nordic UART), prints detections, forwards commands typed in the Serial Monitor (`set_model yolo`, `start_live ar`…) |
| [`micropython/flexml_udp.py`](micropython/flexml_udp.py) | Wi-Fi UDP | MicroPython parser, prints the target's side and distance |
| [`micropython/oled_udp.py`](micropython/oled_udp.py) | Wi-Fi UDP | Shows detections on an SH1106 OLED and lights the LED for a target ([`sh1106.py`](micropython/sh1106.py) driver, [`oledtest.py`](micropython/oledtest.py) wiring check) |

## Setup

**Arduino IDE / PlatformIO:** install the ESP32 core (2.x or 3.x), open the sketch, set `WIFI_SSID` / `WIFI_PASSWORD` (UDP example), upload, and open the Serial Monitor at 115200.

**MicroPython:** flash MicroPython for ESP32, then copy the files with Thonny or `mpremote cp oled_udp.py :main.py && mpremote cp sh1106.py :`.

**In FlexML:** *Network Setup › Microcontrollers*
- **Send over Wi-Fi (UDP):** enter the board's IP (printed on the serial console / OLED) and port 5005.
- **Send over Bluetooth LE:** the phone advertises as **FlexML** with the Nordic UART Service (`6E400001-…`). TX `6E400003-…` (notify, phone → board), RX `6E400002-…` (write, board → phone). Test with the nRF Connect app first. Bluetooth runs while FlexML is in the foreground.

The compact stream has its own rate (default 10 frames/s) and sends at most 12 objects per frame. Labels have spaces replaced by `_`.

## Ideas

Person-following car, pan-tilt tracker (two servos on `cx`/`cy`), safety buzzer when a person is closer than a set distance, a classifier lighting one LED per class in a classroom. See [../../docs/use-cases.md](../../docs/use-cases.md).
