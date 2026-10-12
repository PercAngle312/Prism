"""Bounded direct HTTPS cover downloads for PRISM Studio."""
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit
from http.client import HTTPSConnection
from prism_project import MAX_IMAGE_BYTES
MAX_DOWNLOAD = MAX_IMAGE_BYTES

def download_cover(url: str) -> bytes:
    """Direct HTTPS image download, no redirects, no private-network access."""
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Cover must be a direct HTTPS image URL")
    if parsed.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is supported")
    # Reject literal/private destinations. The connection below uses a public
    # address chosen here, avoiding a second DNS lookup / DNS rebinding.
    hosts = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    addresses = [item[4][0] for item in hosts]
    if not addresses or any(not ipaddress.ip_address(addr).is_global for addr in addresses):
        raise ValueError("Cover URL must resolve only to public internet addresses")
    import http.client

    class PinnedHTTPSConnection(HTTPSConnection):
        def connect(self):
            self.sock = socket.create_connection((addresses[0], 443), timeout=12)
            self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)

    connection = PinnedHTTPSConnection(parsed.hostname, timeout=12,
                                      context=ssl.create_default_context())
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    try:
        connection.request("GET", path, headers={"User-Agent": "PRISM-Studio/0.2"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError(f"Image request returned HTTP {response.status}; redirects are not followed")
        mime = response.getheader("Content-Type", "").split(";")[0].strip().lower()
        if mime not in ("image/png", "image/jpeg"):
            raise ValueError("Only direct PNG or JPEG image URLs are supported")
        raw = response.read(MAX_DOWNLOAD + 1)
        if len(raw) > MAX_DOWNLOAD:
            raise ValueError("Image exceeds 10 MiB import limit")
        if not (raw.startswith(b"\x89PNG\r\n\x1a\n") or
                raw.startswith(b"\xff\xd8\xff")):
            raise ValueError("Invalid PNG or JPEG file signature")
        return raw
    finally:
        connection.close()

