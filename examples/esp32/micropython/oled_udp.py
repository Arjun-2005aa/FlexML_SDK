# FlexML → ESP32 with an SH1106 OLED (128×64), MicroPython, over Wi-Fi (UDP).
#
# Shows the top detections on the display and lights the built-in LED while a TARGET is in view
# (or closer than NEAR_CM in AR mode).
#
# 1. Copy this file as main.py, plus sh1106.py, to the board (Thonny or mpremote).
# 2. Set your Wi-Fi below and reset the board; the display shows its IP.
# 3. In FlexML: Network Setup › Microcontrollers › "Send over Wi-Fi (UDP)", enter that IP, port 5005.
#
# Wiring (ESP32 DevKit): OLED SDA → GPIO21, SCL → GPIO22, VCC → 3V3, GND → GND.

import network
import socket
import time
from machine import I2C, Pin

import sh1106

WIFI_SSID = "your-wifi"
WIFI_PASSWORD = "your-password"
PORT = 5005
TARGET = "person"
NEAR_CM = 100
LED_PIN = 2

led = Pin(LED_PIN, Pin.OUT)
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
try:
    oled = sh1106.SH1106_I2C(128, 64, i2c)
except Exception as e:  # display missing: keep running, print to the serial console
    print("OLED not found:", e)
    oled = None


def show(lines):
    if not oled:
        print(" | ".join(lines))
        return
    oled.fill(0)
    for i, text in enumerate(lines[:5]):
        oled.text(text[:16], 0, i * 12)
    oled.show()


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        show(["FlexML", "Wi-Fi..."])
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.3)
    return wlan.ifconfig()[0]


def parse(text):
    """Compact lines → list of objects (see docs/robot-integration.md#compact-format)."""
    objects, classes = [], []
    for line in text.split("\n"):
        p = line.split()
        if len(p) >= 9 and p[0] == "O":
            objects.append((p[2], int(p[3]), int(p[4]), int(p[8])))   # label, conf %, cx, dist_cm
        elif len(p) >= 3 and p[0] == "C":
            classes.append((p[1], int(p[2])))
    return objects, classes


def main():
    ip = connect_wifi()
    show(["FlexML ready", ip, "port %d" % PORT, "Network Setup >", "Microcontrollers"])
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    sock.settimeout(2)
    while True:
        try:
            data, _ = sock.recvfrom(1500)
        except OSError:              # nothing for 2 s: phone stopped or out of range
            led.off()
            show(["FlexML", ip, "waiting..."])
            continue
        objects, classes = parse(data.decode())
        target = [o for o in objects if o[0] == TARGET]
        near = any(0 < o[3] < NEAR_CM for o in target)
        led.value(1 if (near or (target and all(o[3] < 0 for o in target))) else 0)
        lines = ["%s %d%%%s" % (o[0], o[1], " %dcm" % o[3] if o[3] >= 0 else "") for o in objects]
        lines += ["%s %d%%" % c for c in classes]
        show(lines or ["nothing seen"])


main()
