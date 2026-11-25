"""Collect FlexML's live 3D point cloud and save it as a PLY file.

Needs AR mode (this script switches the phone to it). LiDAR iPhones/iPads give a dense coloured
cloud; other devices give sparse feature points. Walk the phone slowly around the room.

    python save_point_cloud.py --seconds 30 --out room.ply

Open the result in MeshLab, CloudCompare, Open3D or Blender.
"""
import argparse
import asyncio

import flexml_companion as flexml


async def main(seconds: float, out: str, reset: bool) -> None:
    async with flexml.Server() as phone:
        print(f"Waiting for FlexML at {phone.address} …")
        await phone.wait_for_phone()
        await phone.command("start_live", mode="ar")
        if reset:
            await phone.command("reset_map")
        print(f"Scanning for {seconds:.0f} s. Move the phone slowly…")
        remaining = seconds
        while remaining > 0:
            await asyncio.sleep(min(5, remaining))
            remaining -= 5
            print(f"  {len(phone.map):,} points")
        n = phone.map.save_ply(out)
        print(f"Saved {n:,} points to {out}" if n else
              "No points received: is the phone in AR mode, and is Network Setup › Stream › 3D point cloud on?")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seconds", type=float, default=30)
    p.add_argument("--out", default="flexml_cloud.ply")
    p.add_argument("--reset", action="store_true", help="clear the phone's map before scanning")
    a = p.parse_args()
    asyncio.run(main(a.seconds, a.out, a.reset))
