# FlexML → ESP32 over Wi-Fi (UDP), MicroPython.
#
# Copy this file (and sh1106.py if you use the OLED) to the board, set your Wi-Fi, and run it.
# In FlexML: Network Setup › Microcontrollers › "Send over Wi-Fi (UDP)", enter the IP printed
# below, port 5005.
#
# Lines (one datagram per frame), see docs/robot-integration.md:
#   F <frame> <time_ms> <objects>
#   O <track_id> <label> <conf_pct> <cx> <cy> <w> <h> <dist_cm>     (cx, cy, w, h in 0–1000)
#   P <x_cm> <y_cm> <z_cm> <heading_deg>

import network
import socket
import time

WIFI_SSID = "your-wifi"
WIFI_PASSWORD = "your-password"
PORT = 5005
TARGET = "person"


def parse(text):
    """Returns (objects, pose). objects: list of dicts; pose: (x_cm, y_cm, z_cm, heading) or None."""
    objects, pose = [], None
    for line in text.split("\n"):
        p = line.split()
        if len(p) >= 9 and p[0] == "O":
            objects.append({"id": int(p[1]), "label": p[2], "conf": int(p[3]), "cx": int(p[4]), "cy": int(p[5]),
                            "w": int(p[6]), "h": int(p[7]), "dist_cm": int(p[8])})
        elif len(p) >= 5 and p[0] == "P":
            pose = (int(p[1]), int(p[2]), int(p[3]), int(p[4]))
    return objects, pose


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.3)
    return wlan.ifconfig()[0]


def main():
    ip = connect_wifi()
    print("Ready. In FlexML enter", ip, "port", PORT)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    while True:
        data, _ = sock.recvfrom(1500)
        objects, pose = parse(data.decode())
        targets = [o for o in objects if o["label"] == TARGET]
        if targets:
            t = max(targets, key=lambda o: o["conf"])
            side = "LEFT" if t["cx"] < 400 else ("RIGHT" if t["cx"] > 600 else "AHEAD")
            print(TARGET, side, t["conf"], "% dist", t["dist_cm"], "cm")
        if pose:
            print("pose", pose)


main()
