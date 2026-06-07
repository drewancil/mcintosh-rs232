"""Protocol helpers for mcintosh_rs232."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

# Matches standard command tokens: ``(KEY VALUE)`` where KEY is all-uppercase
# letters and VALUE is an optional sign followed by digits.
_TOKEN_RE = re.compile(r"\(([A-Z]+) (-?\d+)\)")

# Matches the model identifier token, e.g. ``(MA5300)``.
_MODEL_RE = re.compile(r"\(([A-Z0-9]+)\)")

# Matches the special-format serial number, firmware, and DA version tokens.
_SERIAL_RE = re.compile(r"\(Serial Number:\s*([A-Z0-9]+)\)")
_FW_RE = re.compile(r"\(FW Version:\s*(\d+\.\d+)\)")
_DA_RE = re.compile(r"\(DA Version:\s*V(\d+\.\d+)\)")


def parse_response_packet(data: str) -> dict[str, str]:
    """Parse a response packet into a ``{key: value}`` mapping.

    Handles standard ``(KEY VALUE)`` tokens (where VALUE is an integer,
    optionally signed) as well as the special-format serial number, firmware
    version, and DA version responses.
    """
    tokens: dict[str, str] = {}

    m = _SERIAL_RE.search(data)
    if m:
        tokens["SER"] = m.group(1)

    m = _FW_RE.search(data)
    if m:
        tokens["FWV"] = m.group(1)

    m = _DA_RE.search(data)
    if m:
        tokens["DAV"] = m.group(1)

    for match in _TOKEN_RE.finditer(data):
        tokens[match.group(1)] = match.group(2)

    # Model identifier e.g. (MA5300) — single-word token with no value.
    # Only capture if it looks like a model string (letters + digits, no space).
    m = _MODEL_RE.search(data)
    if m and m.group(1) not in tokens:
        tokens["MODEL"] = m.group(1)

    return tokens


@dataclass
class PendingQuery:
    """A pending query waiting for a response with a matching key."""

    key: str
    future: asyncio.Future[str]
