"""SSRF-safe URL validation for user-influenced URLs (webhooks, LLM endpoints)."""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

from packages.logging.structured import get_logger

logger = get_logger("url_validation")

# Private/reserved IP ranges that should never be fetched
_BLOCKED_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # private Class A
    ipaddress.ip_network("172.16.0.0/12"),      # private Class B
    ipaddress.ip_network("192.168.0.0/16"),     # private Class C
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / cloud metadata
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("0.0.0.0/8"),         # "this" network
]

# Allowed URL schemes
_ALLOWED_SCHEMES = {"https"}

# Hostname-based allowlist (optional, for webhook endpoints)
_ALLOWED_HOSTS: set[str] = set()


def configure_allowed_hosts(hosts: list[str]) -> None:
    """Configure the allowlist of allowed external hosts."""
    global _ALLOWED_HOSTS
    _ALLOWED_HOSTS = set(hosts)


def validate_url(url: str, *, require_https: bool = True) -> urlparse:
    """Validate a URL against SSRF risks.

    Checks:
    - Valid URL format
    - Scheme is https (if require_https=True)
    - Hostname is not a private/reserved IP
    - Hostname is in allowlist (if configured)

    Raises ValueError with a descriptive message on failure.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError(f"Invalid URL: {url}")

    if not parsed.scheme:
        raise ValueError("URL must have a scheme")

    if require_https and parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed; use https"
        )

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must have a hostname")

    # Check against private/reserved IP ranges
    try:
        ip = ipaddress.ip_address(hostname)
        for blocked in _BLOCKED_RANGES:
            if ip in blocked:
                raise ValueError(
                    f"URL hostname '{hostname}' resolves to a private/reserved IP range"
                )
    except ValueError:
        raise
    except ValueError:
        # hostname is not an IP address (it's a domain name), which is fine
        pass

    # Check hostname allowlist (if configured)
    if _ALLOWED_HOSTS and hostname not in _ALLOWED_HOSTS:
        raise ValueError(f"URL hostname '{hostname}' is not in the allowlist")

    return parsed


def is_safe_url(url: str, *, require_https: bool = True) -> bool:
    """Return True if the URL passes SSRF validation, False otherwise."""
    try:
        validate_url(url, require_https=require_https)
        return True
    except ValueError:
        return False
