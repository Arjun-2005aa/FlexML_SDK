"""`flexml` command line: serve, udp, ros2."""
from __future__ import annotations

import argparse
import asyncio
import sys

from . import __version__
from .compact import listen_udp
from .messages import Anchors, Hello, Inference, MapChunk, Reply
from .server import FlexMLError, Server


def _print_qr(url: str) -> None:
    try:
        import qrcode
    except ImportError:
        print("  (pip install 'flexml-companion[qr]' to show a scannable QR code)")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.print_ascii(invert=True)


async def _serve(args) -> None:
    server = Server(port=args.port, http_port=args.http_port, advertise=not args.no_advertise, name=args.name, log_path=args.log)
    async with server:
        print(f"FlexML companion {__version__}")
        print(f"  WebSocket: {server.address}")
        print("  FlexML finds this computer automatically" if server.advertising
              else "  Auto-discovery off (pip install 'flexml-companion[discovery]'); enter the address or scan:")
        if not server.advertising:
            _print_qr(server.address)
        print("Type commands here, e.g. `start_live ar`, `set_threshold 0.5`, `get_status`.\n")

        async def read_commands() -> None:
            while True:
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:
                    return
                if line.strip():
                    try:
                        print("→", await server.command_text(line))
                    except (FlexMLError, TimeoutError) as e:
                        print("✗", e)

        async def show() -> None:
            async for msg in server.messages():
                if isinstance(msg, Hello):
                    print(f"Connected: {msg.app} on {msg.device} ({msg.system})")
                elif isinstance(msg, Inference) and not args.quiet:
                    for d in msg.detections:
                        dist = f" {d.distance:.2f} m" if d.distance is not None else ""
                        print(f"  #{d.track_id:<4} {d.label:<14} {d.confidence:.2f} centre=({d.center[0]:.2f},{d.center[1]:.2f}){dist}")
                    for label, conf in msg.classifications[:3]:
                        print(f"  {label:<20} {conf:.2f}")
                elif isinstance(msg, Anchors) and msg.anchors and not args.quiet:
                    print(f"[map] {len(msg.anchors)} objects: " + ", ".join(a.label for a in msg.anchors[:6]))
                elif isinstance(msg, MapChunk):
                    print(f"[map] {len(server.map):,} points received (phone has {msg.total:,})")

        try:
            await asyncio.gather(read_commands(), show())
        finally:
            if args.map and len(server.map):
                print(f"Saved {server.map.save_ply(args.map):,} points to {args.map}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="flexml", description="FlexML companion: receive the phone's stream and control it.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="receive the stream, print results, send commands from the keyboard")
    s.add_argument("--port", type=int, default=8080, help="WebSocket port (default 8080)")
    s.add_argument("--http-port", type=int, default=8081, help="HTTP port (default 8081)")
    s.add_argument("--name", help="name shown in FlexML's Nearby computers list")
    s.add_argument("--no-advertise", action="store_true", help="don't advertise with Bonjour")
    s.add_argument("--log", help="append every message to this .jsonl file")
    s.add_argument("--map", help="save the received 3D point cloud to this .ply file on exit")
    s.add_argument("--quiet", action="store_true", help="don't print every detection")

    u = sub.add_parser("udp", help="print the compact microcontroller stream (UDP)")
    u.add_argument("--port", type=int, default=5005)

    c = sub.add_parser("check-model", help="check that a Core ML model will run well in FlexML (needs coremltools)")
    c.add_argument("model", help=".mlmodel or .mlpackage")
    c.add_argument("--image", help="also run a test prediction on this image (macOS)")
    c.add_argument("--json", action="store_true", help="machine-readable output (for scripts and AI agents)")

    r = sub.add_parser("ros2", help="publish the stream as ROS 2 topics (run inside a sourced ROS 2 environment)")
    r.add_argument("--port", type=int, default=8080)
    r.add_argument("--namespace", default="flexml")
    r.add_argument("--no-advertise", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "serve":
            asyncio.run(_serve(args))
        elif args.cmd == "udp":
            print(f"Listening for FlexML compact frames on UDP {args.port}…")
            for frame in listen_udp(args.port):
                objs = ", ".join(f"{o.label} {o.confidence}% ({o.cx},{o.cy})" for o in frame.objects) or "nothing"
                print(f"frame {frame.frame}: {objs}" + (f" pose={frame.pose}" if frame.pose else ""))
        elif args.cmd == "check-model":
            from .modelcheck import main as check_main
            raise SystemExit(check_main(args))
        elif args.cmd == "ros2":
            from .ros2_bridge import run
            run(Server(port=args.port, advertise=not args.no_advertise), namespace=args.namespace)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
