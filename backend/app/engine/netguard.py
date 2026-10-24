"""Outbound URL validation for customer agent endpoints (SSRF protection)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeURLError(ValueError):
    pass


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_agent_url(url: str, *, allow_private: bool = False, resolve: bool = True) -> str:
    """Validate an agent endpoint URL; raise ``UnsafeURLError`` if it is not allowed.

    Rejects non-HTTP(S) schemes, embedded credentials, and (unless
    ``allow_private``) any host that is or resolves to a private, loopback,
    link-local or otherwise non-public address.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURLError("Agent endpoint must use http or https.")
    if not parts.hostname:
        raise UnsafeURLError("Agent endpoint must include a host.")
    if parts.username or parts.password:
        raise UnsafeURLError("Put credentials in the auth token field, not the URL.")
    if allow_private:
        return url

    host = parts.hostname
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        if host.lower() in ("localhost",) or host.lower().endswith(
            (".localhost", ".internal", ".local")
        ):
            raise UnsafeURLError("Agent endpoint must be a public host.") from None
        if not resolve:
            return url
        try:
            infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
        except socket.gaierror as exc:
            raise UnsafeURLError(f"Could not resolve agent host '{host}'.") from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]

    if not addresses or not all(_is_public(a) for a in addresses):
        raise UnsafeURLError("Agent endpoint must be a public host.")
    return url
