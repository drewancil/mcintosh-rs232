"""McIntosh amplifier controller for mcintosh_rs232."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable

import serialx

from .const import (
    BAUD_RATE,
    COMMAND_TIMEOUT,
    MAX_BALANCE,
    MAX_BASS,
    MAX_DISPLAY_BRIGHTNESS,
    MAX_INPUT_TRIM,
    MAX_TREBLE,
    MAX_VOLUME,
    MIN_BALANCE,
    MIN_BASS,
    MIN_DISPLAY_BRIGHTNESS,
    MIN_INPUT_TRIM,
    MIN_TREBLE,
    MIN_VOLUME,
    POWER_ON_SELFTEST_DELAY,
    POWER_ON_TIMEOUT,
    TERMCHAR,
    InputSource,
    ToneMode,
)
from .protocol import PendingQuery, parse_response_packet
from .state import AmplifierState

_LOGGER = logging.getLogger(__name__)

# Explicitly listed so test code can override them at module level.
__all__ = [
    "McIntoshReceiver",
    "StateCallback",
    "COMMAND_TIMEOUT",
]

StateCallback = Callable[[AmplifierState | None], None]


class McIntoshReceiver:
    """Async controller for a McIntosh amplifier over RS232.

    Typical usage::

        receiver = McIntoshReceiver("/dev/serial0")
        await receiver.connect()
        await receiver.query_state()
        print(receiver.state)
        await receiver.disconnect()
    """

    def __init__(self, port: str, max_volume: int = MAX_VOLUME) -> None:
        self._port = port
        self._max_volume = max_volume
        self._reader: asyncio.StreamReader | None = None
        self._writer: serialx.SerialStreamWriter[serialx.BaseSerialTransport] | None = (
            None
        )
        self._read_task: asyncio.Task[None] | None = None
        self._state = AmplifierState()
        self._subscribers: list[StateCallback] = []
        self._pending_queries: list[PendingQuery] = []
        self._write_lock = asyncio.Lock()
        self._connected = False
        self._batching = False
        self._batch_changed = False

    # -- Properties --

    @property
    def state(self) -> AmplifierState:
        """Return a copy of the current amplifier state."""
        return self._state.copy()

    @property
    def connected(self) -> bool:
        """Return ``True`` if currently connected to the amplifier."""
        return self._connected

    @property
    def power(self) -> bool | None:
        """Return the current power state."""
        return self._state.power

    @property
    def max_volume(self) -> int:
        """Return the configured maximum volume."""
        return self._max_volume

    # -- Subscription --

    def subscribe(self, callback: StateCallback) -> Callable[[], None]:
        """Subscribe to state changes.

        The callback receives a copy of :class:`AmplifierState` on every
        change, and ``None`` when the connection is lost.  Returns an
        unsubscribe callable.
        """
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    # -- Connection --

    async def connect(self) -> None:
        """Open the serial connection and verify the amplifier is responding.

        Raises :exc:`ConnectionError` if the amplifier does not respond within
        the command timeout.
        """
        #if sys.platform.startswith("linux"):
        #    from serialx.platforms import serial_linux

            # The TIOCSSERIAL ioctl requires elevated permissions on some Linux
            # serial devices (e.g. Raspberry Pi).  Nulling it out disables the
            # low-latency ioctl call inside serialx so the connection proceeds
            # without needing special permissions.
        #    serial_linux.TIOCSSERIAL = None
        

        connect_kwargs: dict[str, object] = {"baudrate": BAUD_RATE}
        #if sys.platform.startswith("linux"):
        #    connect_kwargs["low_latency"] = False
        if True:
            connect_kwargs["key"] = "bhMn8ROVmBv46hf6PxoR1zcRXsNW59McTrOzsYpXluI="
            connect_kwargs["url"] = "esphome://192.168.4.160:6053/?port_name=mcintosh_proxy"

        #self._reader, self._writer = await serialx.open_serial_connection(
        #    self._port,
        #    **connect_kwargs,
        #)
        self._reader, self._writer = await serialx.open_serial_connection(
            **connect_kwargs,
        )
        self._connected = True
        self._read_task = asyncio.create_task(self._read_loop())

        try:
            await self._query_all()
        except TimeoutError:
            await self.disconnect()
            raise ConnectionError(
                f"No response from amplifier on {self._port}"
            ) from None

        # Enable unsolicited status updates from the amplifier.
        await self._send_command("STA", "1")

        _LOGGER.info("Connected to McIntosh amplifier on %s", self._port)

    async def disconnect(self) -> None:
        """Close the serial connection and notify subscribers."""
        await self._teardown()
        _LOGGER.info("Disconnected from McIntosh amplifier")

    # -- Power --

    async def power_on(self) -> None:
        """Turn the amplifier on and wait for it to finish booting."""
        await self._send_command_and_wait("PWR", "1", timeout=POWER_ON_TIMEOUT)
        # Amp runs a self-test after the boot echo; commands are queued but
        # not echoed back until it completes.
        await asyncio.sleep(POWER_ON_SELFTEST_DELAY)

    async def power_off(self) -> None:
        """Turn the amplifier off."""
        await self._send_command_and_wait("PWR", "0")

    async def query_power(self) -> bool:
        """Query and return the current power state."""
        await self._query_all()
        return self._state.power is True

    # -- Volume --

    async def set_volume(self, volume: int) -> None:
        """Set the volume level (``MIN_VOLUME`` to ``max_volume``)."""
        if not MIN_VOLUME <= volume <= self._max_volume:
            raise ValueError(
                f"Volume must be between {MIN_VOLUME} and {self._max_volume}"
            )
        await self._send_command("VOL", str(volume))

    async def volume_up(self) -> None:
        """Increment the volume by one step."""
        current = self._state.volume
        if current is None:
            _LOGGER.warning("volume_up called but volume state is unknown")
            return
        await self.set_volume(min(current + 1, self._max_volume))

    async def volume_down(self) -> None:
        """Decrement the volume by one step."""
        current = self._state.volume
        if current is None:
            _LOGGER.warning("volume_down called but volume state is unknown")
            return
        await self.set_volume(max(current - 1, MIN_VOLUME))

    async def query_volume(self) -> int:
        """Query and return the current volume level."""
        await self._query_all()
        return self._state.volume or 0

    # -- Mute --

    async def mute_on(self) -> None:
        """Mute the amplifier."""
        await self._send_command("MUT", "1")

    async def mute_off(self) -> None:
        """Unmute the amplifier."""
        await self._send_command("MUT", "0")

    async def query_mute(self) -> bool:
        """Query and return the current mute state."""
        await self._query_all()
        return self._state.mute is True

    # -- Input source --

    async def select_input(self, source: InputSource) -> None:
        """Select an input source."""
        await self._send_command("INP", str(source.value))

    async def query_input(self) -> InputSource:
        """Query and return the current input source."""
        await self._query_all()
        return self._state.input_source or InputSource(1)

    # -- Balance --

    async def set_balance(self, balance: int) -> None:
        """Set balance (``MIN_BALANCE`` to ``MAX_BALANCE``).

        Negative values pan left; positive values pan right.
        """
        if not MIN_BALANCE <= balance <= MAX_BALANCE:
            raise ValueError(f"Balance must be between {MIN_BALANCE} and {MAX_BALANCE}")
        await self._send_command("TBA", str(balance))

    async def query_balance(self) -> int:
        """Query and return the current balance."""
        await self._query_all()
        return self._state.balance or 0

    # -- Tone controls --

    async def tone_on(self) -> None:
        """Enable tone controls."""
        await self._send_command("TTN", "1")

    async def tone_off(self) -> None:
        """Disable tone controls."""
        await self._send_command("TTN", "0")

    async def query_tone(self) -> bool:
        """Query and return whether tone controls are enabled."""
        await self._query_all()
        return self._state.tone_enabled is True

    async def set_bass(self, bass: int) -> None:
        """Set bass level (``MIN_BASS`` to ``MAX_BASS``)."""
        if not MIN_BASS <= bass <= MAX_BASS:
            raise ValueError(f"Bass must be between {MIN_BASS} and {MAX_BASS}")
        await self._send_command("TTB", str(bass))

    async def query_bass(self) -> int:
        """Query and return the current bass level."""
        await self._query_all()
        return self._state.bass or 0

    async def set_treble(self, treble: int) -> None:
        """Set treble level (``MIN_TREBLE`` to ``MAX_TREBLE``)."""
        if not MIN_TREBLE <= treble <= MAX_TREBLE:
            raise ValueError(f"Treble must be between {MIN_TREBLE} and {MAX_TREBLE}")
        await self._send_command("TTT", str(treble))

    async def query_treble(self) -> int:
        """Query and return the current treble level."""
        await self._query_all()
        return self._state.treble or 0

    # -- Input trim --

    async def set_input_trim(self, trim: int) -> None:
        """Set input trim (``MIN_INPUT_TRIM`` to ``MAX_INPUT_TRIM``)."""
        if not MIN_INPUT_TRIM <= trim <= MAX_INPUT_TRIM:
            raise ValueError(
                f"Input trim must be between {MIN_INPUT_TRIM} and {MAX_INPUT_TRIM}"
            )
        await self._send_command("TIN", str(trim))

    async def query_input_trim(self) -> int:
        """Query and return the current input trim."""
        await self._query_all()
        return self._state.input_trim or 0

    # -- Tone mode --

    async def set_tone_mode(self, mode: ToneMode) -> None:
        """Set tone mode (stereo or mono)."""
        await self._send_command("TMO", str(mode.value))

    async def query_tone_mode(self) -> ToneMode:
        """Query and return the current tone mode."""
        await self._query_all()
        return self._state.tone_mode or ToneMode(0)

    # -- Meter lights --

    async def meter_lights_on(self) -> None:
        """Turn the VU meter lights on."""
        await self._send_command("TML", "1")

    async def meter_lights_off(self) -> None:
        """Turn the VU meter lights off."""
        await self._send_command("TML", "0")

    # -- Display brightness --

    async def set_display_brightness(self, level: int) -> None:
        """Set display brightness (``MIN_DISPLAY_BRIGHTNESS`` to
        ``MAX_DISPLAY_BRIGHTNESS``)."""
        if not MIN_DISPLAY_BRIGHTNESS <= level <= MAX_DISPLAY_BRIGHTNESS:
            raise ValueError(
                f"Display brightness must be between "
                f"{MIN_DISPLAY_BRIGHTNESS} and {MAX_DISPLAY_BRIGHTNESS}"
            )
        await self._send_command("TDB", str(level))

    # -- Full state query --

    async def query_state(self) -> None:
        """Query all current state from the amplifier.

        Sends ``(QRY)`` which returns the full state in a single response.
        Subscriber notifications are suppressed while the query runs and
        fired once at the end if any value changed.
        """
        self._batching = True
        self._batch_changed = False
        try:
            await self._query_all()
        except TimeoutError:
            _LOGGER.debug("No response to QRY")
        finally:
            self._batching = False

        if self._batch_changed:
            self._notify_subscribers()

    # -- Internal helpers --

    async def _query_all(self) -> None:
        """Send ``(QRY)`` and wait for the amplifier's full state response.

        Registers a pending query on ``PWR`` (which is always present in the
        QRY response) so the caller can ``await`` the round-trip.
        """
        assert self._writer is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        pending = PendingQuery(key="PWR", future=future)
        self._pending_queries.append(pending)
        try:
            msg = b"(QRY)"
            _LOGGER.debug("Sending: %s", msg)
            try:
                async with self._write_lock:
                    self._writer.write(msg)
                    await self._writer.drain()
            except Exception:
                _LOGGER.exception("Error writing to serial port")
                await self._teardown()
                raise
            await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        finally:
            if pending in self._pending_queries:
                self._pending_queries.remove(pending)

    async def _send_command_and_wait(
        self, key: str, value: str, timeout: float = COMMAND_TIMEOUT
    ) -> None:
        """Send a ``(KEY VALUE)`` command and wait for the echo from the amp."""
        assert self._writer is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        pending = PendingQuery(key=key, future=future)
        self._pending_queries.append(pending)
        try:
            msg = f"({key} {value})".encode("ascii")
            _LOGGER.debug("Sending: %s", msg)
            try:
                async with self._write_lock:
                    self._writer.write(msg)
                    await self._writer.drain()
            except Exception:
                _LOGGER.exception("Error writing to serial port")
                await self._teardown()
                raise
            await asyncio.wait_for(future, timeout=timeout)
        finally:
            if pending in self._pending_queries:
                self._pending_queries.remove(pending)

    async def _send_command(self, key: str, value: str) -> None:
        """Write a ``(KEY VALUE)`` command to the amplifier."""
        assert self._writer is not None
        msg = f"({key} {value})".encode("ascii")
        _LOGGER.debug("Sending: %s", msg)
        try:
            async with self._write_lock:
                self._writer.write(msg)
                await self._writer.drain()
        except Exception:
            _LOGGER.exception("Error writing to serial port")
            await self._teardown()
            raise

    async def _query(self, key: str) -> str:
        """Send a ``(KEY)`` query and wait for the matching response value."""
        assert self._writer is not None
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str] = loop.create_future()
        pending = PendingQuery(key=key, future=future)
        self._pending_queries.append(pending)
        try:
            msg = f"({key})".encode("ascii")
            _LOGGER.debug("Querying: %s", msg)
            try:
                async with self._write_lock:
                    self._writer.write(msg)
                    await self._writer.drain()
            except Exception:
                _LOGGER.exception("Error writing to serial port")
                await self._teardown()
                raise
            return await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        finally:
            if pending in self._pending_queries:
                self._pending_queries.remove(pending)

    async def _teardown(self) -> None:
        """Tear down the connection and notify subscribers."""
        if not self._connected:
            return
        self._connected = False

        current = asyncio.current_task()

        if self._read_task is not None and self._read_task is not current:
            self._read_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._read_task
        self._read_task = None

        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None

        self._notify_subscribers()

    async def _read_loop(self) -> None:
        """Continuously read and process packets from the amplifier."""
        assert self._reader is not None
        buf = b""

        while self._connected:
            try:
                data = await asyncio.wait_for(self._reader.read(256), timeout=0.2)
            except TimeoutError:
                # No data for 200ms — flush any unterminated packet in the buffer.
                # This handles the power-off case where the amp responds to (QRY)
                # without a trailing null terminator.
                if buf:
                    text = buf.lstrip(TERMCHAR).decode("ascii", 
                                                       errors="replace").strip()
                    if text:
                        self._process_packet(text)
                    buf = b""
                continue
            except Exception:
                if not self._connected:
                    return
                _LOGGER.exception("Error reading from serial port")
                await self._teardown()
                return

            if not data:
                _LOGGER.warning("Serial connection closed")
                await self._teardown()
                return

            buf += data

            while TERMCHAR in buf:
                packet, buf = buf.split(TERMCHAR, 1)
                text = packet.decode("ascii", errors="replace").strip()
                if text:
                    self._process_packet(text)

    @staticmethod
    def _set_attr_value(target: object, attr: str, new_value: object) -> bool:
        """Set an attribute only when its value changes. Returns ``True`` if changed."""
        if getattr(target, attr) == new_value:
            return False
        setattr(target, attr, new_value)
        return True

    def _set_state_value(self, attr: str, new_value: object) -> bool:
        """Set an :class:`AmplifierState` attribute only when its value changes."""
        return self._set_attr_value(self._state, attr, new_value)

    def _process_packet(self, packet: str) -> None:
        """Parse a response packet and dispatch each token to :meth:`_process_token`."""
        _LOGGER.debug("Received packet: %s", packet)
        tokens = parse_response_packet(packet)
        changed = False

        for key, value in tokens.items():
            if self._process_token(key, value):
                changed = True

            # Resolve any pending query that is waiting for this key.
            for pending in list(self._pending_queries):
                if pending.key == key and not pending.future.done():
                    pending.future.set_result(value)

        if changed:
            if self._batching:
                self._batch_changed = True
            else:
                self._notify_subscribers()

    def _process_token(self, key: str, value: str) -> bool:
        """Update state for a single ``(key, value)`` token.

        Returns ``True`` if state changed.
        """
        try:
            if key == "PWR":
                return self._set_state_value("power", int(value) != 0)
            if key == "VOL":
                return self._set_state_value("volume", int(value))
            if key == "MUT":
                return self._set_state_value("mute", int(value) != 0)
            if key == "INP":
                return self._set_state_value("input_source", InputSource(int(value)))
            if key == "TBA":
                return self._set_state_value("balance", int(value))
            if key == "TTN":
                return self._set_state_value("tone_enabled", int(value) != 0)
            if key == "TTB":
                return self._set_state_value("bass", int(value))
            if key == "TTT":
                return self._set_state_value("treble", int(value))
            if key == "TIN":
                return self._set_state_value("input_trim", int(value))
            if key == "TMO":
                return self._set_state_value("tone_mode", ToneMode(int(value)))
            if key == "TML":
                return self._set_state_value("meter_lights", int(value) != 0)
            if key == "TDB":
                return self._set_state_value("display_brightness", int(value))
            if key == "SER":
                return self._set_state_value("serial_number", value)
            if key == "FWV":
                return self._set_state_value("firmware_version", value)
            if key == "DAV":
                return self._set_state_value("da_version", value)
            if key == "MODEL":
                return self._set_state_value("model", value)
        except ValueError:
            _LOGGER.warning("Could not parse token %s=%s", key, value)
            return False

        _LOGGER.debug("Unknown token key: %s", key)
        return False

    def _notify_subscribers(self) -> None:
        """Notify all subscribers of a state change or disconnect."""
        state = self._state.copy() if self._connected else None
        for callback in self._subscribers:
            try:
                callback(state)
            except Exception:
                _LOGGER.exception("Error in state change callback %s", callback)
