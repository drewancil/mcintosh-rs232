"""Shared test fixtures for mcintosh_rs232."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mcintosh_rs232
import mcintosh_rs232.receiver as mcintosh_receiver
from mcintosh_rs232 import McIntoshReceiver

# Speed up tests by reducing delays.
mcintosh_rs232.COMMAND_TIMEOUT = 0.1
mcintosh_rs232.QUERY_STATE_DELAY = 0.01
mcintosh_receiver.COMMAND_TIMEOUT = 0.1

# Default responses for all query keys during startup.
# Each value is a list of packet-content strings (without the trailing '}').
DEFAULT_QUERY_RESPONSES: dict[str, list[str]] = {
    "PWR": ["(PWR 1)"],
    "VOL": ["(VOL 50)"],
    "MUT": ["(MUT 0)"],
    "INP": ["(INP 3)"],
    "TBA": ["(TBA 0)"],
    "TTN": ["(TTN 1)"],
    "TTB": ["(TTB 0)"],
    "TTT": ["(TTT 0)"],
    "TIN": ["(TIN 0)"],
    "TMO": ["(TMO 0)"],
    "TML": ["(TML 1)"],
    "TDB": ["(TDB 2)"],
}


class MockSerialConnection:
    """Mock the serialx reader/writer pair with auto-response support.

    Responses are injected as complete term-char terminated packets so that the
    receiver's ``_read_loop`` can process them exactly as it would real data.
    """

    def __init__(self) -> None:
        self.reader = asyncio.StreamReader()
        self.writer = MagicMock()
        self.writer.write = MagicMock()
        self.writer.drain = AsyncMock()
        self.writer.close = MagicMock()
        self.writer.wait_closed = AsyncMock()
        self.written_data: list[bytes] = []
        self._query_responses: dict[str, list[str]] = {}
        self._command_handler: Callable[[str], None] | None = None
        self.writer.write.side_effect = self._on_write

    def _on_write(self, data: bytes) -> None:
        """Track written data and auto-respond to queries."""
        self.written_data.append(data)
        text = data.decode("ascii").strip()

        # Commands must be wrapped in parentheses: ``(KEY)`` or ``(KEY VALUE)``.
        if not (text.startswith("(") and text.endswith(")")):
            return

        inner = text[1:-1]
        parts = inner.split(maxsplit=1)
        if not parts:
            return

        key = parts[0]
        is_query = len(parts) == 1

        if is_query:
            for packet_content in self._query_responses.get(key, []):
                self.inject_response(packet_content)
        elif self._command_handler is not None:
            self._command_handler(text)

    def inject_response(self, packet_content: str) -> None:
        """Simulate the receiver sending a term-char terminated response packet."""
        self.reader.feed_data(packet_content.encode("ascii") + mcintosh_rs232.TERMCHAR)


@pytest.fixture
async def mock_serial() -> MockSerialConnection:
    return MockSerialConnection()


@pytest.fixture
async def receiver(mock_serial: MockSerialConnection) -> McIntoshReceiver:  # type: ignore[misc]
    """Create a connected McIntoshReceiver with mocked serial."""
    recv = McIntoshReceiver("/dev/ttyUSB0")
    mock_serial._query_responses = dict(DEFAULT_QUERY_RESPONSES)

    async def fake_open(*args: object, **kwargs: object) -> tuple[asyncio.StreamReader, MagicMock]:
        return mock_serial.reader, mock_serial.writer

    with patch(
        "mcintosh_rs232.receiver.serialx.open_serial_connection",
        side_effect=fake_open,
    ):
        await recv.connect()
        await recv.query_state()

    # Clear auto-responses so individual tests control exactly what the mock returns.
    mock_serial._query_responses.clear()

    yield recv

    if recv.connected:
        await recv.disconnect()


async def connect_with_defaults(mock: MockSerialConnection) -> McIntoshReceiver:
    """Helper: connect a receiver with all default query responses."""
    mock._query_responses = dict(DEFAULT_QUERY_RESPONSES)
    recv = McIntoshReceiver("/dev/ttyUSB0")

    async def fake_open(*args: object, **kwargs: object) -> tuple[asyncio.StreamReader, MagicMock]:
        return mock.reader, mock.writer

    with patch(
        "mcintosh_rs232.receiver.serialx.open_serial_connection",
        side_effect=fake_open,
    ):
        await recv.connect()
        await recv.query_state()

    return recv
