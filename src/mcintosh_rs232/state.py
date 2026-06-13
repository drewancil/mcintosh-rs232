"""Runtime state dataclass for mcintosh_rs232."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .const import VERSION, InputSource, ToneMode


@dataclass
class AmplifierState:
    """Current state of the McIntosh receiver."""

    version: str = VERSION  # version of the mcintosh_rs232 library
    manufacturer: str = "McIntosh"
    power: bool | None = None
    volume: int | None = None
    mute: bool | None = None
    input_source: InputSource | None = None
    balance: int | None = None
    tone_enabled: bool | None = None
    bass: int | None = None
    treble: int | None = None
    input_trim: int | None = None
    tone_mode: ToneMode | None = None
    meter_lights: bool | None = None
    display_brightness: int | None = None
    firmware_version: str | None = None
    serial_number: str | None = None
    da_version: str | None = None

    model: str | None = None

    def copy(self) -> AmplifierState:
        """Return a shallow copy of this state."""
        return replace(self)
