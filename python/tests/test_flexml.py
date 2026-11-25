"""Tests for the flexml companion package. Run: python -m unittest discover -s tests"""
import asyncio
import base64
import json
import math
import os
import socket
import struct
import tempfile
import unittest

import flexml_companion as flexml
from flexml_companion import frames
from flexml_companion.compact import parse as parse_compact


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


INFERENCE = {
    "v": 2, "type": "inference", "t": 12.5, "frame": 7, "model": {"name": "yolo", "task": "detection"},
    "latencyMs": {"preprocess": 0.5, "inference": 6.1, "postprocess": 0.1},
    "image": {"width": 720, "height": 1280, "orientation": "right", "crop": [0, 0, 1, 1]},
    "detections": [{"trackId": 3, "label": "person", "classId": 0, "confidence": 0.9, "box": [0.4, 0.2, 0.2, 0.6],
                    "world": [0.1, 0.0, -2.0], "distance": 2.0}],
}


class MessageTests(unittest.TestCase):
    def test_inference(self):
        msg = flexml.parse(INFERENCE)
        self.assertIsInstance(msg, flexml.Inference)
        d = msg.detections[0]
        self.assertEqual((d.track_id, d.label), (3, "person"))
        self.assertAlmostEqual(d.center[0], 0.5)
        self.assertAlmostEqual(d.center[1], 0.5)

    def test_map_chunk_and_ply(self):
        xyz = struct.pack("<6f", 1, 2, 3, -1, -2, -3)
        chunk = flexml.parse({"type": "map", "t": 0, "reset": True, "start": 0, "count": 2, "total": 2,
                              "positions": base64.b64encode(xyz).decode(), "colors": base64.b64encode(bytes([1, 2, 3, 4, 5, 6])).decode()})
        self.assertEqual(chunk.points()[1], (-1.0, -2.0, -3.0, 4, 5, 6))
        cloud = flexml.PointCloud()
        cloud.add(chunk)
        self.assertEqual(len(cloud), 2)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.ply")
            self.assertEqual(cloud.save_ply(path), 2)
            data = open(path, "rb").read()
            self.assertIn(b"element vertex 2", data)
            self.assertEqual(len(data.split(b"end_header\n", 1)[1]), 30)


class CompactTests(unittest.TestCase):
    def test_parse(self):
        f = parse_compact("F 12 34567 1\nO 3 person 87 512 430 210 380 145\nC cup 55\nP 10 -5 200 90\n")
        self.assertEqual((f.frame, f.time_ms), (12, 34567))
        o = f.objects[0]
        self.assertEqual((o.track_id, o.label, o.confidence, o.cx, o.distance_cm), (3, "person", 87, 512, 145))
        self.assertEqual(f.classes, [("cup", 55)])
        self.assertEqual(f.pose, (10, -5, 200, 90))

    def test_tolerates_garbage(self):
        self.assertEqual(parse_compact("O x y\nnonsense\n").objects, [])


class FrameTests(unittest.TestCase):
    def test_point(self):
        # 2 m in front of the camera in ARKit (-z) is +x in ROS.
        self.assertEqual(frames.point_to_ros((0, 0, -2)), (2, 0, 0))
        self.assertEqual(frames.point_to_ros((0, 1, 0)), (0, 0, 1))  # up stays up

    def test_yaw_maps_to_ros_yaw(self):
        # ARKit: 90° rotation about +y (up). ROS: 90° about +z (up).
        s = math.sin(math.pi / 4)
        q = frames.orientation_to_ros((0, s, 0, s))
        self.assertAlmostEqual(abs(q[2]), s, places=6)
        self.assertAlmostEqual(abs(q[3]), s, places=6)
        self.assertAlmostEqual(q[0], 0, places=6)
        self.assertAlmostEqual(q[1], 0, places=6)

    def test_identity(self):
        q = frames.orientation_to_ros((0, 0, 0, 1))
        self.assertAlmostEqual(abs(q[3]), 1, places=6)


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_and_commands(self):
        import websockets
        port, http_port = free_port(), free_port()
        async with flexml.Server(host="127.0.0.1", port=port, http_port=http_port, advertise=False) as server:
            async with websockets.connect(f"ws://127.0.0.1:{port}") as phone:
                # A fake phone that answers every command.
                async def answer():
                    async for text in phone:
                        cmd = json.loads(text)
                        ok = cmd["command"] != "bad"
                        await phone.send(json.dumps({"v": 2, "type": "reply", "id": cmd["id"], "command": cmd["command"],
                                                     "ok": ok, "result": {"echo": cmd.get("value")} if ok else None,
                                                     "error": None if ok else "nope"}))
                responder = asyncio.create_task(answer())
                await server.wait_for_phone(timeout=2)

                stream = server.messages()
                await phone.send(json.dumps(INFERENCE))
                msg = await asyncio.wait_for(stream.__anext__(), 2)
                self.assertIsInstance(msg, flexml.Inference)

                self.assertEqual(await server.command_text("set_threshold 0.5"), {"echo": "0.5"})
                with self.assertRaises(flexml.FlexMLError):
                    await server.command("bad")
                responder.cancel()

            # HTTP transport delivers the same messages.
            stream = server.messages()
            reader, writer = await asyncio.open_connection("127.0.0.1", http_port)
            body = json.dumps(INFERENCE).encode()
            writer.write(b"POST / HTTP/1.1\r\nContent-Length: %d\r\n\r\n" % len(body) + body)
            await writer.drain()
            self.assertIn(b"200 OK", await reader.read(100))
            writer.close()
            self.assertIsInstance(await asyncio.wait_for(stream.__anext__(), 2), flexml.Inference)


if __name__ == "__main__":
    unittest.main()
