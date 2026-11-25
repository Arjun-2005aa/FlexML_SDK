"""FlexML companion server: receives the phone's stream and sends it commands."""
from __future__ import annotations

import asyncio
import itertools
import json
from typing import Any, Callable, Dict, List, Optional

from .discovery import Advertiser, local_ip
from .messages import Anchors, Hello, MapChunk, PointCloud, Pose, Reply, parse

try:  # websockets >= 13
    from websockets.asyncio.server import serve as _ws_serve
except ImportError:  # pragma: no cover - older websockets
    from websockets import serve as _ws_serve  # type: ignore


class MessageStream:
    """Async iterator over incoming messages. When the consumer falls behind, the oldest
    queued message is dropped (newest wins)."""

    def __init__(self, server: "Server", maxsize: int) -> None:
        self._server = server
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        server._queues.append(self._queue)

    def __aiter__(self) -> "MessageStream":
        return self

    async def __anext__(self) -> Any:
        return await self._queue.get()

    def close(self) -> None:
        if self._queue in self._server._queues:
            self._server._queues.remove(self._queue)


class FlexMLError(RuntimeError):
    """A command was rejected by the phone."""


class Server:
    """Accepts a FlexML phone over WebSocket (and HTTP POST), advertises itself with Bonjour,
    and exposes the stream as typed messages.

        async with flexml_companion.Server() as phone:
            await phone.wait_for_phone()
            await phone.command("start_live", mode="ar")
            async for msg in phone.messages():
                ...

    (`import flexml_companion`.) Latest state is kept for convenience: `pose`, `objects`, `map` (a PointCloud), `hello`.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, http_port: Optional[int] = 8081,
                 advertise: bool = True, name: Optional[str] = None, log_path: Optional[str] = None) -> None:
        self.host, self.port, self.http_port = host, port, http_port
        self.advertise = advertise
        self._advertiser = Advertiser(port, http_port or 0, name)
        self._log = open(log_path, "a") if log_path else None
        self._ws = None
        self._ws_server = None
        self._http_server = None
        self._queues: List[asyncio.Queue] = []
        self._callbacks: Dict[str, List[Callable[[Any], None]]] = {}
        self._pending: Dict[str, asyncio.Future] = {}
        self._ids = itertools.count(1)
        self._connected = asyncio.Event()
        self.hello: Optional[Hello] = None
        self.pose: Optional[Pose] = None
        self.objects: Dict[str, Any] = {}
        self.map = PointCloud()
        self.advertising = False

    # ---- lifecycle ----

    async def __aenter__(self) -> "Server":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def start(self) -> None:
        self._ws_server = await _ws_serve(self._handle_ws, self.host, self.port, max_size=16 * 1024 * 1024)
        if self.http_port:
            self._http_server = await asyncio.start_server(self._handle_http, self.host, self.http_port)
        if self.advertise:
            self.advertising = await asyncio.to_thread(self._advertiser.start)

    async def stop(self) -> None:
        if self.advertising:
            await asyncio.to_thread(self._advertiser.stop)
        if self._ws_server:
            self._ws_server.close()
            await self._ws_server.wait_closed()
        if self._http_server:
            self._http_server.close()
            await self._http_server.wait_closed()
        if self._log:
            self._log.close()

    @property
    def address(self) -> str:
        return f"ws://{local_ip()}:{self.port}"

    @property
    def connected(self) -> bool:
        return self._ws is not None

    async def wait_for_phone(self, timeout: Optional[float] = None) -> None:
        await asyncio.wait_for(self._connected.wait(), timeout)

    # ---- receiving ----

    def on(self, kind: str, callback: Callable[[Any], None]) -> None:
        """Calls `callback(message)` for each message of `kind` ("inference", "pose", "map", ...)."""
        self._callbacks.setdefault(kind, []).append(callback)

    def messages(self, maxsize: int = 256) -> "MessageStream":
        """Every message from the phone, typed (see flexml.messages). Listening starts as soon as
        this is called, so nothing is missed between creating the stream and iterating it."""
        return MessageStream(self, maxsize)

    def _dispatch(self, text: str) -> None:
        if self._log:
            self._log.write(text.strip() + "\n")
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return
        msg = parse(raw)
        kind = raw.get("type", "")
        if isinstance(msg, Hello):
            self.hello = msg
        elif isinstance(msg, Pose):
            self.pose = msg
        elif isinstance(msg, Anchors):
            self.objects = {a.id: a for a in msg.anchors}
        elif isinstance(msg, MapChunk):
            self.map.add(msg)
        elif isinstance(msg, Reply):
            fut = self._pending.pop(str(msg.id), None)
            if fut and not fut.done():
                fut.set_result(msg)
        for cb in self._callbacks.get(kind, []):
            cb(msg)
        for q in self._queues:
            if q.full():  # newest wins, like the phone's own backpressure
                q.get_nowait()
            q.put_nowait(msg)

    async def _handle_ws(self, ws) -> None:
        self._ws = ws
        self._connected.set()
        try:
            async for text in ws:
                self._dispatch(text if isinstance(text, str) else text.decode())
        finally:
            if self._ws is ws:
                self._ws = None
                self._connected.clear()

    async def _handle_http(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Minimal HTTP: HEAD / for the app's reachability check, POST / with one JSON message."""
        try:
            request = await reader.readline()
            headers = {}
            while (line := await reader.readline()) not in (b"\r\n", b"\n", b""):
                k, _, v = line.decode().partition(":")
                headers[k.strip().lower()] = v.strip()
            if request.startswith(b"POST"):
                body = await reader.readexactly(int(headers.get("content-length", "0")))
                self._dispatch(body.decode("utf-8", "replace"))
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()

    # ---- commands ----

    async def command(self, name: str, timeout: float = 10.0, **params: Any) -> Dict[str, Any]:
        """Sends a command (see docs/robot-integration.md) and returns its result.

        Raises FlexMLError if the phone rejects it, TimeoutError if it doesn't answer.
        """
        if self._ws is None:
            raise FlexMLError("No phone connected")
        cid = str(next(self._ids))
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[cid] = fut
        await self._ws.send(json.dumps({"type": "command", "id": cid, "command": name, **params}))
        try:
            reply: Reply = await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(cid, None)
        if not reply.ok:
            raise FlexMLError(f"{name}: {reply.error}")
        return reply.result or {}

    async def command_text(self, line: str, timeout: float = 10.0) -> Dict[str, Any]:
        """Text form, e.g. ``"set_threshold 0.5"`` or ``"start_live ar"``."""
        name, _, value = line.strip().partition(" ")
        return await self.command(name, timeout=timeout, **({"value": value} if value else {}))
