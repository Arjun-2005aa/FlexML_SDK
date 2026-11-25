"""Typed FlexML stream messages (protocol v2). See docs/protocol.md."""
from __future__ import annotations

import base64
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Detection:
    track_id: int
    label: str
    class_id: int
    confidence: float
    #: (x, y, width, height), normalized 0..1, top-left origin, upright image.
    box: Tuple[float, float, float, float]
    keypoints: Optional[List[Tuple[float, float, float]]] = None
    #: World position in metres (AR mode): ARKit frame, y up.
    world: Optional[Tuple[float, float, float]] = None
    distance: Optional[float] = None
    anchor: Optional[str] = None

    @property
    def center(self) -> Tuple[float, float]:
        x, y, w, h = self.box
        return (x + w / 2, y + h / 2)


@dataclass
class Inference:
    t: float
    frame: int
    model: str
    task: str
    latency_ms: Dict[str, float]
    image: Dict[str, Any]
    detections: List[Detection] = field(default_factory=list)
    classifications: List[Tuple[str, float]] = field(default_factory=list)
    segmentation: Optional[Dict[str, Any]] = None
    depth: Optional[Dict[str, Any]] = None
    tensors: Optional[List[Dict[str, Any]]] = None
    imu: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Pose:
    t: float
    tracking: str
    position: Tuple[float, float, float]
    #: Quaternion (x, y, z, w), ARKit world frame.
    orientation: Tuple[float, float, float, float]
    #: 4x4 camera-to-world, column-major (16 floats).
    transform: List[float]
    intrinsics: List[float]
    image_resolution: Tuple[int, int]

    @property
    def is_tracking(self) -> bool:
        return self.tracking == "normal"


@dataclass
class Anchor:
    id: str
    label: str
    position: Tuple[float, float, float]
    confidence: float
    sightings: int
    last_seen: float


@dataclass
class Anchors:
    t: float
    anchors: List[Anchor]


@dataclass
class MapChunk:
    t: float
    reset: bool
    start: int
    count: int
    total: int
    positions: bytes  # little-endian float32 x,y,z per point
    colors: bytes     # uint8 r,g,b per point

    def points(self) -> List[Tuple[float, float, float, int, int, int]]:
        """(x, y, z, r, g, b) tuples. Use `to_numpy()` for large maps."""
        xyz = struct.unpack(f"<{self.count * 3}f", self.positions[: self.count * 12])
        return [(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2], *self.colors[i * 3: i * 3 + 3]) for i in range(self.count)]


@dataclass
class Hello:
    t: float
    app: str
    device: str
    system: str
    capabilities: Dict[str, bool]


@dataclass
class Reply:
    id: Optional[str]
    command: str
    ok: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]


Message = Any  # one of the dataclasses above, or a dict for unknown types


def parse(msg: Dict[str, Any]) -> Message:
    """Turns a decoded JSON message into a typed object (unknown types are returned as dicts)."""
    kind = msg.get("type")
    if kind == "inference":
        dets = [
            Detection(
                track_id=d.get("trackId", 0), label=d["label"], class_id=d.get("classId", -1),
                confidence=d["confidence"], box=tuple(d["box"]),
                keypoints=[tuple(k) for k in d["keypoints"]] if d.get("keypoints") else None,
                world=tuple(d["world"]) if d.get("world") else None,
                distance=d.get("distance"), anchor=d.get("anchor"),
            )
            for d in msg.get("detections") or []
        ]
        return Inference(
            t=msg["t"], frame=msg.get("frame", 0), model=msg["model"]["name"], task=msg["model"]["task"],
            latency_ms=msg.get("latencyMs", {}), image=msg.get("image", {}), detections=dets,
            classifications=[(c["label"], c["confidence"]) for c in msg.get("classifications") or []],
            segmentation=msg.get("segmentation"), depth=msg.get("depth"), tensors=msg.get("tensors"),
            imu=msg.get("imu"), raw=msg,
        )
    if kind == "pose":
        return Pose(t=msg["t"], tracking=msg["tracking"], position=tuple(msg["position"]),
                    orientation=tuple(msg["orientation"]), transform=msg["transform"],
                    intrinsics=msg["intrinsics"], image_resolution=tuple(msg["imageResolution"]))
    if kind == "anchors":
        return Anchors(t=msg["t"], anchors=[
            Anchor(id=a["id"], label=a["label"], position=tuple(a["position"]), confidence=a["confidence"],
                   sightings=a["sightings"], last_seen=a["lastSeen"]) for a in msg["anchors"]])
    if kind == "map":
        return MapChunk(t=msg["t"], reset=msg["reset"], start=msg["start"], count=msg["count"], total=msg["total"],
                        positions=base64.b64decode(msg["positions"]), colors=base64.b64decode(msg["colors"]))
    if kind == "hello":
        return Hello(t=msg["t"], app=msg["app"], device=msg["device"], system=msg["system"],
                     capabilities=msg.get("capabilities", {}))
    if kind == "reply":
        return Reply(id=msg.get("id"), command=msg["command"], ok=msg["ok"], result=msg.get("result"),
                     error=msg.get("error"))
    return msg


class PointCloud:
    """Accumulates `map` chunks into one cloud; can save a binary PLY."""

    def __init__(self) -> None:
        self.xyz = bytearray()
        self.rgb = bytearray()

    def __len__(self) -> int:
        return len(self.rgb) // 3

    def add(self, chunk: MapChunk) -> None:
        if chunk.reset:
            self.xyz.clear()
            self.rgb.clear()
        self.xyz += chunk.positions[: chunk.count * 12]
        self.rgb += chunk.colors[: chunk.count * 3]

    def to_numpy(self):
        """(N, 3) float32 positions and (N, 3) uint8 colours (requires numpy)."""
        import numpy as np
        return (np.frombuffer(bytes(self.xyz), dtype="<f4").reshape(-1, 3),
                np.frombuffer(bytes(self.rgb), dtype=np.uint8).reshape(-1, 3))

    def save_ply(self, path: str) -> int:
        n = len(self)
        header = (f"ply\nformat binary_little_endian 1.0\ncomment FlexML map (metres, ARKit frame: y up)\n"
                  f"element vertex {n}\nproperty float x\nproperty float y\nproperty float z\n"
                  "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n").encode()
        body = bytearray(n * 15)
        for i in range(n):
            body[i * 15: i * 15 + 12] = self.xyz[i * 12: i * 12 + 12]
            body[i * 15 + 12: i * 15 + 15] = self.rgb[i * 3: i * 3 + 3]
        with open(path, "wb") as f:
            f.write(header)
            f.write(body)
        return n
