"""Constants and enums for mcintosh_rs232."""

from enum import Enum

BAUD_RATE = 115200
COMMAND_TIMEOUT = 2.0  # seconds to wait for a query response
POWER_ON_TIMEOUT = 10.0  # seconds to wait for amp to finish booting
POWER_ON_SELFTEST_DELAY = 5.0  # seconds to wait for amp self-test after power-on echo
QUERY_STATE_DELAY = 0.3  # seconds to wait for QRY responses to arrive
TERMCHAR = b"\x00"

# Volume range
MIN_VOLUME = 0
MAX_VOLUME = 100

# Balance range
MIN_BALANCE = -50
MAX_BALANCE = 50

# Bass/Treble range
MIN_BASS = -6
MAX_BASS = 6
MIN_TREBLE = -6
MAX_TREBLE = 6

# Input trim range
MIN_INPUT_TRIM = -12
MAX_INPUT_TRIM = 12

# Display brightness range
MIN_DISPLAY_BRIGHTNESS = 1
MAX_DISPLAY_BRIGHTNESS = 4

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
