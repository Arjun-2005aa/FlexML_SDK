"""Bonjour advertising so the FlexML app finds this computer without an IP address."""
from __future__ import annotations

import socket
from typing import Optional

SERVICE_TYPE = "_flexml._tcp.local."


def local_ip() -> str:
    """Best guess at this computer's LAN address (no traffic is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Advertiser:
    """Publishes `_flexml._tcp` with the WebSocket/HTTP ports in the TXT record.

    Requires the optional `zeroconf` package (`pip install "flexml-companion[discovery]"`). Without it,
    advertising is skipped and the app can still connect by IP or QR code.
    """

    def __init__(self, ws_port: int, http_port: int, name: Optional[str] = None) -> None:
        self.ws_port = ws_port
        self.http_port = http_port
        self.name = name or socket.gethostname().split(".")[0]
        self._zc = None
        self._info = None

    def start(self) -> bool:
        try:
            from zeroconf import ServiceInfo, Zeroconf
        except ImportError:
            return False
        ip = local_ip()
        self._info = ServiceInfo(
            SERVICE_TYPE,
            f"{self.name} FlexML.{SERVICE_TYPE}",
            addresses=[socket.inet_aton(ip)],
            port=self.ws_port,
            properties={"ip": ip, "ws": str(self.ws_port), "http": str(self.http_port), "name": self.name, "v": "2"},
            server=f"{self.name.replace(' ', '-')}.local.",
        )
        self._zc = Zeroconf()
        self._zc.register_service(self._info)
        return True

    def stop(self) -> None:
        if self._zc and self._info:
            self._zc.unregister_service(self._info)
            self._zc.close()
        self._zc = None
