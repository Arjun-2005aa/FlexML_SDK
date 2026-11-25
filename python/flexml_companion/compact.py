"""Parser for FlexML's compact microcontroller format (UDP / Bluetooth). See docs/robot-integration.md.

Lines (one UDP datagram per frame):

    F <frame> <time_ms> <objects>
    O <track_id> <label> <conf_pct> <cx> <cy> <w> <h> <dist_cm>
    C <label> <conf_pct>
    S <label> <coverage_pct>
    D <centre_mm>
    P <x_cm> <y_cm> <z_cm> <heading_deg>
"""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple


@dataclass
class CompactObject:
    track_id: int
    label: str
    confidence: int      # percent
    cx: int              # 0..1000 of the upright image
    cy: int
    w: int
    h: int
    distance_cm: int     # -1 when unknown


@dataclass
class CompactFrame:
    frame: int = 0
    time_ms: int = 0
    objects: List[CompactObject] = field(default_factory=list)
    classes: List[Tuple[str, int]] = field(default_factory=list)
    segments: List[Tuple[str, int]] = field(default_factory=list)
    depth_mm: Optional[int] = None
    pose: Optional[Tuple[int, int, int, int]] = None  # x_cm, y_cm, z_cm, heading_deg


def parse(text: str) -> CompactFrame:
    frame = CompactFrame()
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        try:
            if p[0] == "F" and len(p) >= 3:
                frame.frame, frame.time_ms = int(p[1]), int(p[2])
            elif p[0] == "O" and len(p) >= 9:
                frame.objects.append(CompactObject(int(p[1]), p[2], int(p[3]), int(p[4]), int(p[5]), int(p[6]), int(p[7]), int(p[8])))
            elif p[0] == "C" and len(p) >= 3:
                frame.classes.append((p[1], int(p[2])))
            elif p[0] == "S" and len(p) >= 3:
                frame.segments.append((p[1], int(p[2])))
            elif p[0] == "D" and len(p) >= 2:
                frame.depth_mm = int(p[1])
            elif p[0] == "P" and len(p) >= 5:
                frame.pose = (int(p[1]), int(p[2]), int(p[3]), int(p[4]))
        except ValueError:
            continue  # tolerate a malformed line
    return frame


def listen_udp(port: int = 5005, host: str = "0.0.0.0") -> Iterator[CompactFrame]:
    """Yields frames received on a UDP port (blocking). Handy on a Raspberry Pi."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    try:
        while True:
            data, _ = sock.recvfrom(2048)
            yield parse(data.decode("utf-8", "replace"))
    finally:
        sock.close()
