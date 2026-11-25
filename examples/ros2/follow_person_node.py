#!/usr/bin/env python3
"""ROS 2 node: follow a person using FlexML detections, publishing geometry_msgs/Twist.

Run the bridge first (`flexml ros2`), then:

    python3 follow_person_node.py --ros-args -p target:=person -p follow_distance:=1.2

Subscribes to /flexml/inference (std_msgs/String, the full JSON message, so it works without
vision_msgs) and publishes /cmd_vel. Remap /cmd_vel to your robot's topic if needed:

    python3 follow_person_node.py --ros-args -r cmd_vel:=/my_robot/cmd_vel
"""
import json
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String


class FollowPerson(Node):
    def __init__(self) -> None:
        super().__init__("flexml_follow_person")
        self.target = self.declare_parameter("target", "person").value
        self.follow_distance = float(self.declare_parameter("follow_distance", 1.2).value)
        self.turn_gain = float(self.declare_parameter("turn_gain", 1.5).value)
        self.max_speed = float(self.declare_parameter("max_speed", 0.4).value)
        self.cmd = self.create_publisher(Twist, "cmd_vel", 10)
        self.create_subscription(String, "/flexml/inference", self.on_inference, 10)
        self.create_timer(0.2, self.watchdog)
        self.locked = None
        self.last_seen = 0.0
        self.get_logger().info(f"Following '{self.target}'")

    def on_inference(self, msg: String) -> None:
        data = json.loads(msg.data)
        people = [d for d in data.get("detections", []) if d.get("label") == self.target]
        target = next((d for d in people if d.get("trackId") == self.locked), None)
        if target is None and people:
            target = max(people, key=lambda d: d["confidence"])
            self.locked = target.get("trackId")
        if target is None:
            return
        self.last_seen = time.monotonic()
        x, y, w, h = target["box"]
        error = (x + w / 2) - 0.5                       # −0.5 (left) … +0.5 (right)
        distance = target.get("distance")               # metres, AR mode only
        gap = (distance - self.follow_distance) if distance is not None else (0.6 - h)
        twist = Twist()
        twist.angular.z = -self.turn_gain * error
        twist.linear.x = max(0.0, min(self.max_speed, 0.5 * gap)) if abs(error) < 0.3 else 0.0
        self.cmd.publish(twist)

    def watchdog(self) -> None:
        if time.monotonic() - self.last_seen > 1.0:     # lost the target: stop
            self.locked = None
            self.cmd.publish(Twist())


def main() -> None:
    rclpy.init()
    node = FollowPerson()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
