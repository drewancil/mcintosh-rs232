"""Constants and enums for mcintosh_rs232."""

from enum import Enum

VERSION = "0.1.4"

BAUD_RATE = 115200
COMMAND_TIMEOUT = 2.0  # seconds to wait for a query response
POWER_ON_TIMEOUT = 10.0  # seconds to wait for amp to finish booting
POWER_ON_SELFTEST_DELAY = 5.0  # seconds to wait for amp self-test after power-on echo
QUERY_STATE_DELAY = 0.3  # seconds to wait for QRY responses to arrive
TERMCHAR = b"\x00"

MIN_VOLUME = 0
MAX_VOLUME = 100

MIN_BALANCE = -50
MAX_BALANCE = 50

MIN_BASS = -6
MAX_BASS = 6
MIN_TREBLE = -6
MAX_TREBLE = 6

MIN_INPUT_TRIM = -12
MAX_INPUT_TRIM = 12

MIN_DISPLAY_BRIGHTNESS = 1
MAX_DISPLAY_BRIGHTNESS = 4


def format_ascii_bar(value_range: range, value: int, marker: str = "||", fill: str = "-") -> str:
    """Render an inclusive integer range as a simple ASCII bar.

    The marker is placed at the position corresponding to ``value`` within the
    inclusive bounds of ``value_range``. Values outside the range are clamped.
    """
    if value_range.step not in (1, -1):
        raise ValueError("value_range must use a step of 1 or -1")
    if len(marker) == 0:
        raise ValueError("marker must not be empty")
    if len(fill) != 1:
        raise ValueError("fill must be a single character")

    start = value_range.start
    stop = value_range.stop - 1 if value_range.step > 0 else value_range.stop + 1
    low = min(start, stop)
    high = max(start, stop)

    clamped = max(low, min(high, value))
    width = high - low + 1
    position = clamped - low

    left = fill * position
    right = fill * (width - position - 1)
    return f"[{left}{marker}{right}]"


# Parameters that can be individually queried by sending ``(KEY)`` with no value.
# PWR is queried separately during connect() and query_power().
_QUERYABLE_PARAMS: tuple[str, ...] = (
    "VOL",
    "MUT",
    "INP",
    "TBA",
    "TTN",
    "TTB",
    "TTT",
    "TIN",
    "TMO",
    "TML",
    "TDB",
)


class InputSource(Enum):
    """Input sources available on the McIntosh MA5300."""

    BALANCED = 1
    UNBALANCED1 = 2
    UNBALANCED2 = 3
    UNBALANCED3 = 4
    UNBALANCED4 = 5
    PHONO = 6
    COAX1 = 7
    COAX2 = 8
    OPTICAL1 = 9
    OPTICAL2 = 10
    USB = 11
    MCT = 12
    HDMI = 13


class ToneMode(Enum):
    """Tone mode (channel mode) setting."""

    STEREO = 0
    MONO = 1
