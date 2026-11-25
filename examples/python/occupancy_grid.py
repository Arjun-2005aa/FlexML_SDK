"""Turn FlexML's point cloud into a 2D obstacle (occupancy) map.

Points between MIN_HEIGHT and MAX_HEIGHT above the floor become obstacles on a top-down grid.
Writes a PGM image (black = obstacle, white = seen floor, grey = unknown) and a .npy array you
can use for path planning. Needs numpy (`pip install numpy`).

    python occupancy_grid.py --seconds 30 --out map          # live from the phone
    python occupancy_grid.py --ply room.ply --out map         # from a saved PLY / Space

ARKit's world frame is y-up, so the top-down plane is x (right) / z (towards the start position).
"""
import argparse
import asyncio
import struct

import numpy as np

CELL = 0.05          # metres per grid cell
MIN_HEIGHT = 0.10    # ignore the floor itself
MAX_HEIGHT = 1.50    # ignore ceilings and things above the robot


def load_ply(path: str) -> np.ndarray:
    """Reads FlexML's binary PLY (float x, y, z + uchar r, g, b)."""
    with open(path, "rb") as f:
        n = 0
        while True:
            line = f.readline().decode().strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            if line == "end_header":
                break
        data = np.frombuffer(f.read(n * 15), dtype=np.dtype([("xyz", "<f4", 3), ("rgb", "u1", 3)]))
    return data["xyz"].astype(np.float32)


def build_grid(xyz: np.ndarray) -> np.ndarray:
    floor = np.percentile(xyz[:, 1], 2)             # lowest points ≈ floor
    h = xyz[:, 1] - floor
    x, z = xyz[:, 0], xyz[:, 2]
    x0, z0 = x.min(), z.min()
    w = int((x.max() - x0) / CELL) + 1
    d = int((z.max() - z0) / CELL) + 1
    grid = np.full((d, w), 128, np.uint8)          # unknown
    ix, iz = ((x - x0) / CELL).astype(int), ((z - z0) / CELL).astype(int)
    floor_pts = h < MIN_HEIGHT
    grid[iz[floor_pts], ix[floor_pts]] = 255        # free floor
    obstacle = (h >= MIN_HEIGHT) & (h <= MAX_HEIGHT)
    grid[iz[obstacle], ix[obstacle]] = 0            # obstacle wins
    print(f"grid {w}×{d} cells ({w * CELL:.1f} × {d * CELL:.1f} m), origin x={x0:.2f} z={z0:.2f}, floor y={floor:.2f}")
    return grid


def save(grid: np.ndarray, out: str) -> None:
    with open(out + ".pgm", "wb") as f:
        f.write(b"P5\n%d %d\n255\n" % (grid.shape[1], grid.shape[0]))
        f.write(grid.tobytes())
    np.save(out + ".npy", grid)
    print(f"wrote {out}.pgm and {out}.npy")


async def live(seconds: float) -> np.ndarray:
    import flexml_companion as flexml
    async with flexml.Server() as phone:
        print(f"Waiting for FlexML at {phone.address} …")
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        print(f"Scanning for {seconds:.0f} s…")
        await asyncio.sleep(seconds)
        xyz, _ = phone.map.to_numpy()
        return xyz.copy()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ply", help="use a saved PLY instead of the live stream")
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--out", default="occupancy")
    a = p.parse_args()
    points = load_ply(a.ply) if a.ply else asyncio.run(live(a.seconds))
    if len(points) < 100:
        raise SystemExit("Too few points: use AR mode and scan for longer.")
    save(build_grid(points), a.out)
