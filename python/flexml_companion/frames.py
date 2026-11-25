"""Coordinate conversion between ARKit and ROS (REP 103).

ARKit world: x right, y up, z towards the viewer (the camera looks down -z).
ROS world:   x forward, y left, z up.

A point maps as (x, y, z)_ARKit -> (-z, -x, y)_ROS. Orientations are conjugated with the same
change of basis, so the device's forward axis (ARKit -z) becomes ROS +x.
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

# Rows: ROS axes expressed in ARKit coordinates.
C = ((0.0, 0.0, -1.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def point_to_ros(p: Sequence[float]) -> Tuple[float, float, float]:
    x, y, z = p
    return (-z, -x, y)


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _transpose(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def quat_to_matrix(q: Sequence[float]) -> List[List[float]]:
    x, y, z, w = q
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def matrix_to_quat(m: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    """Rotation matrix -> quaternion (x, y, z, w)."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        w, x, y, z = 0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        w, x, y, z = (m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        w, x, y, z = (m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        w, x, y, z = (m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s
    return (x, y, z, w)


def orientation_to_ros(q: Sequence[float]) -> Tuple[float, float, float, float]:
    """ARKit device orientation (x, y, z, w) -> ROS orientation of a body frame with x forward, z up."""
    r = _matmul(_matmul(C, quat_to_matrix(q)), _transpose(C))
    return matrix_to_quat(r)
