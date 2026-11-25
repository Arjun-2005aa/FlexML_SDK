"""FlexML companion library: receive an iPhone/iPad's vision, pose and map stream, and control it.

    import asyncio
    import flexml_companion as flexml

    async def main():
        async with flexml.Server() as phone:
            await phone.wait_for_phone()
            await phone.command("start_live")
            async for msg in phone.messages():
                if isinstance(msg, flexml.Inference):
                    for d in msg.detections:
                        print(d.label, d.confidence, d.center, d.distance)

    asyncio.run(main())
"""

__version__ = "0.1.0"

from .compact import CompactFrame, CompactObject, listen_udp
from .compact import parse as parse_compact
from .messages import Anchor, Anchors, Detection, Hello, Inference, MapChunk, PointCloud, Pose, Reply, parse
from .server import FlexMLError, Server

__all__ = [
    "Server", "FlexMLError", "Inference", "Detection", "Pose", "Anchor", "Anchors", "MapChunk", "PointCloud",
    "Hello", "Reply", "parse", "CompactFrame", "CompactObject", "parse_compact", "listen_udp", "__version__",
]
