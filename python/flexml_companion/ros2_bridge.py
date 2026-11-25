"""ROS 2 bridge: republishes the FlexML stream as standard ROS messages.

Run with `flexml ros2` inside a sourced ROS 2 environment (Humble or newer).

Topics (all prefixed with the namespace, default `/flexml`):

| Topic | Type | Notes |
|---|---|---|
| `detections` | vision_msgs/Detection2DArray | pixels of the upright image (needs `ros-<distro>-vision-msgs`) |
| `inference` | std_msgs/String | the full JSON message, always published |
| `odom` | nav_msgs/Odometry | `flexml_map` -> `flexml_device`, ROS axes (x forward, z up); also on TF |
| `points` | sensor_msgs/PointCloud2 | accumulated coloured map in `flexml_map`, ~1 Hz |
| `objects` | visualization_msgs/MarkerArray | labelled spheres for mapped objects |
| `command` (subscribed) | std_msgs/String | text commands, e.g. "set_threshold 0.5" |
| `reply` | std_msgs/String | command results as JSON |
"""
from __future__ import annotations

import asyncio
import json
import struct
import threading
import time

from . import frames
from .messages import Anchors, Inference, MapChunk, Pose
from .server import FlexMLError, Server


def run(server: Server, namespace: str = "flexml", map_frame: str = "flexml_map", device_frame: str = "flexml_device") -> None:
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import PointCloud2, PointField
        from visualization_msgs.msg import Marker, MarkerArray
        from geometry_msgs.msg import TransformStamped
    except ImportError as e:  # pragma: no cover - needs ROS
        raise SystemExit(f"ROS 2 isn't available ({e}). Source your ROS 2 setup first, e.g. `source /opt/ros/humble/setup.bash`.")
    try:
        from vision_msgs.msg import Detection2D, Detection2DArray, ObjectHypothesisWithPose
    except ImportError:
        Detection2DArray = None  # detections still published as JSON on `inference`
    try:
        from tf2_ros import TransformBroadcaster
    except ImportError:
        TransformBroadcaster = None

    rclpy.init()

    class Bridge(Node):
        def __init__(self) -> None:
            super().__init__("flexml_bridge", namespace=namespace)
            self.pub_json = self.create_publisher(String, "inference", 10)
            self.pub_dets = self.create_publisher(Detection2DArray, "detections", 10) if Detection2DArray else None
            self.pub_odom = self.create_publisher(Odometry, "odom", 20)
            self.pub_points = self.create_publisher(PointCloud2, "points", 1)
            self.pub_objects = self.create_publisher(MarkerArray, "objects", 1)
            self.pub_reply = self.create_publisher(String, "reply", 10)
            self.tf = TransformBroadcaster(self) if TransformBroadcaster else None
            self.create_subscription(String, "command", self.on_command, 10)
            self.create_timer(1.0, self.publish_points)
            self.loop: asyncio.AbstractEventLoop | None = None
            self._published_points = -1

        def stamp(self):
            return self.get_clock().now().to_msg()

        def on_inference(self, msg: Inference) -> None:
            self.pub_json.publish(String(data=json.dumps(msg.raw)))
            if not self.pub_dets:
                return
            w, h = msg.image.get("width", 1), msg.image.get("height", 1)
            out = Detection2DArray()
            out.header.stamp, out.header.frame_id = self.stamp(), "flexml_camera"
            for d in msg.detections:
                det = Detection2D()
                det.header = out.header
                det.id = str(d.track_id)
                cx, cy = d.center
                det.bbox.center.position.x, det.bbox.center.position.y = cx * w, cy * h
                det.bbox.size_x, det.bbox.size_y = d.box[2] * w, d.box[3] * h
                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id, hyp.hypothesis.score = d.label, float(d.confidence)
                if d.world:
                    hyp.pose.pose.position.x, hyp.pose.pose.position.y, hyp.pose.pose.position.z = frames.point_to_ros(d.world)
                det.results.append(hyp)
                out.detections.append(det)
            self.pub_dets.publish(out)

        def on_pose(self, pose: Pose) -> None:
            if not pose.is_tracking:
                return
            x, y, z = frames.point_to_ros(pose.position)
            qx, qy, qz, qw = frames.orientation_to_ros(pose.orientation)
            odom = Odometry()
            odom.header.stamp, odom.header.frame_id, odom.child_frame_id = self.stamp(), map_frame, device_frame
            p, o = odom.pose.pose.position, odom.pose.pose.orientation
            p.x, p.y, p.z = x, y, z
            o.x, o.y, o.z, o.w = qx, qy, qz, qw
            self.pub_odom.publish(odom)
            if self.tf:
                t = TransformStamped()
                t.header = odom.header
                t.child_frame_id = device_frame
                t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = x, y, z
                t.transform.rotation = odom.pose.pose.orientation
                self.tf.sendTransform(t)

        def on_anchors(self, msg: Anchors) -> None:
            markers = MarkerArray()
            clear = Marker()
            clear.action = Marker.DELETEALL
            markers.markers.append(clear)
            for i, a in enumerate(msg.anchors):
                for kind in (Marker.SPHERE, Marker.TEXT_VIEW_FACING):
                    m = Marker()
                    m.header.stamp, m.header.frame_id = self.stamp(), map_frame
                    m.ns, m.id, m.type = "flexml_objects", i * 2 + (kind == Marker.TEXT_VIEW_FACING), kind
                    m.pose.position.x, m.pose.position.y, m.pose.position.z = frames.point_to_ros(a.position)
                    m.pose.orientation.w = 1.0
                    if kind == Marker.SPHERE:
                        m.scale.x = m.scale.y = m.scale.z = 0.1
                        m.color.r, m.color.g, m.color.b, m.color.a = 1.0, 0.6, 0.1, 1.0
                    else:
                        m.text = a.label
                        m.pose.position.z += 0.15
                        m.scale.z = 0.12
                        m.color.r = m.color.g = m.color.b = m.color.a = 1.0
                    markers.markers.append(m)
            self.pub_objects.publish(markers)

        def publish_points(self) -> None:
            cloud = server.map
            n = len(cloud)
            if n == 0 or n == self._published_points:
                return
            self._published_points = n
            msg = PointCloud2()
            msg.header.stamp, msg.header.frame_id = self.stamp(), map_frame
            msg.height, msg.width = 1, n
            msg.fields = [PointField(name=c, offset=o, datatype=PointField.FLOAT32, count=1)
                          for c, o in (("x", 0), ("y", 4), ("z", 8), ("rgb", 12))]
            msg.is_bigendian, msg.point_step, msg.row_step, msg.is_dense = False, 16, 16 * n, True
            try:
                import numpy as np
                xyz = np.frombuffer(bytes(cloud.xyz), dtype="<f4").reshape(-1, 3)
                rgb = np.frombuffer(bytes(cloud.rgb), dtype=np.uint8).reshape(-1, 3).astype(np.uint32)
                out = np.empty((n, 4), dtype="<f4")
                out[:, 0], out[:, 1], out[:, 2] = -xyz[:, 2], -xyz[:, 0], xyz[:, 1]
                out[:, 3] = ((rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]).view("<f4")
                msg.data = out.tobytes()
            except ImportError:
                data = bytearray()
                for i in range(n):
                    x, y, z = struct.unpack_from("<3f", cloud.xyz, i * 12)
                    r, g, b = cloud.rgb[i * 3: i * 3 + 3]
                    data += struct.pack("<3fI", -z, -x, y, (r << 16) | (g << 8) | b)
                msg.data = bytes(data)
            self.pub_points.publish(msg)

        def on_command(self, msg: String) -> None:
            if not self.loop:
                return
            future = asyncio.run_coroutine_threadsafe(server.command_text(msg.data), self.loop)

            def done(f):
                try:
                    result = {"command": msg.data, "ok": True, "result": f.result()}
                except (FlexMLError, Exception) as e:  # noqa: BLE001 - report every failure back on /reply
                    result = {"command": msg.data, "ok": False, "error": str(e)}
                self.pub_reply.publish(String(data=json.dumps(result)))
            future.add_done_callback(done)

    node = Bridge()
    server.on("inference", node.on_inference)
    server.on("pose", node.on_pose)
    server.on("anchors", node.on_anchors)

    async def main() -> None:
        node.loop = asyncio.get_running_loop()
        async with server:
            print(f"FlexML ROS 2 bridge: topics under /{namespace}; waiting for the phone at {server.address}")
            await asyncio.Future()

    spin = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin.start()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        time.sleep(0.1)
