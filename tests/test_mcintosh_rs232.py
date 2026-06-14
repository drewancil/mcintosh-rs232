"""Tests for mcintosh_rs232 query, control, and event handling."""

import asyncio
from unittest.mock import patch

import pytest
from conftest import (
    DEFAULT_QUERY_RESPONSES,
    MockSerialConnection,
    connect_with_defaults,
)

from mcintosh_rs232 import (
    _QUERYABLE_PARAMS,
    InputSource,
    McIntoshReceiver,
    ReceiverState,
    ToneMode,
    _parse_response_packet,
    format_ascii_bar,
)

# ---------------------------------------------------------------------------
# Protocol parsing tests
# ---------------------------------------------------------------------------


def test_parse_single_token() -> None:
    assert _parse_response_packet("(VOL 50)") == {"VOL": "50"}


def test_parse_multiple_tokens() -> None:
    result = _parse_response_packet("(VOL 50)(INP 3)(MUT 0)")
    assert result == {"VOL": "50", "INP": "3", "MUT": "0"}


def test_parse_negative_value() -> None:
    result = _parse_response_packet("(TBA -30)")
    assert result == {"TBA": "-30"}


def test_parse_compact_token_without_space() -> None:
    result = _parse_response_packet("(VOL75)")
    assert result == {"VOL": "75"}


def test_parse_compact_negative_token_without_space() -> None:
    result = _parse_response_packet("(TIN-6)")
    assert result == {"TIN": "-6"}


def test_parse_all_negative_params() -> None:
    result = _parse_response_packet("(TTB -6)(TTT -3)(TIN -12)")
    assert result == {"TTB": "-6", "TTT": "-3", "TIN": "-12"}


def test_parse_firmware_version() -> None:
    result = _parse_response_packet("(FW Version: 2.05)")
    assert result == {"FWV": "2.05"}


def test_parse_serial_number() -> None:
    result = _parse_response_packet("(Serial Number: AFP2999)")
    assert result == {"SER": "AFP2999"}


def test_parse_da_version() -> None:
    result = _parse_response_packet("(DA Version: V1.23)")
    assert result == {"DAV": "1.23"}


def test_parse_power_on_dump() -> None:
    """Simulate the multi-token dump the unit sends on power-on."""
    data = (
        "(MA5300)(Serial Number: AFP2999)(FW Version: 2.05)"
        "(PWR 1)(VOL 43)(MUT 0)(INP 11)(STA 1)(TBA 0)(TIN 0)"
        "(TTN 1)(TTB 3)(TTT 1)(TMO 0)(TML 1)(TDB 3)"
    )
    result = _parse_response_packet(data)
    assert result["SER"] == "AFP2999"
    assert result["FWV"] == "2.05"
    assert result["PWR"] == "1"
    assert result["VOL"] == "43"
    assert result["INP"] == "11"
    assert result["TTB"] == "3"
    assert result["MODEL"] == "MA5300"


def test_parse_full_dump_with_null_prefix_suffix() -> None:
    data = (
        "\x00\x00(MA5300)(Serial Number: AFP2999)(FW Version: 2.08)"
        "(DA Version: V5.11)(PWR 1)(VOL 25)(MUT 0)(INP 11)(STA 1)"
        "(TBA 0)(TIN 0)(TTN 1)(TTB 4)(TTT 0)(TMO 0)(TML 0)(TDB 4)"
        "(THH 1)(HPS 0)\x00\x00"
    )
    result = _parse_response_packet(data)

    assert result["MODEL"] == "MA5300"
    assert result["SER"] == "AFP2999"
    assert result["FWV"] == "2.08"
    assert result["DAV"] == "5.11"
    assert result["TML"] == "0"


def test_parse_empty_packet() -> None:
    assert _parse_response_packet("") == {}


def test_parse_unknown_tokens_ignored() -> None:
    # Model identifier tokens with no value should still be captured.
    result = _parse_response_packet("(MA5300)")
    assert result == {"MODEL": "MA5300"}


def test_format_ascii_bar_center_position() -> None:
    assert format_ascii_bar(range(-6, 7), 2) == "[--------||----]"


def test_format_ascii_bar_clamps_to_bounds() -> None:
    assert format_ascii_bar(range(-6, 7), -99) == "[||------------]"
    assert format_ascii_bar(range(-6, 7), 99) == "[------------||]"


def test_format_ascii_bar_descending_range() -> None:
    assert format_ascii_bar(range(6, -7, -1), 2) == "[--------||----]"


# ---------------------------------------------------------------------------
# Initial state tests
# ---------------------------------------------------------------------------


def test_initial_state_defaults() -> None:
    state = ReceiverState()
    assert state.power is None
    assert state.volume is None
    assert state.mute is None
    assert state.input_source is None
    assert state.balance is None
    assert state.tone_enabled is None
    assert state.bass is None
    assert state.treble is None
    assert state.input_trim is None
    assert state.tone_mode is None
    assert state.meter_lights is None
    assert state.display_brightness is None
    assert state.firmware_version is None
    assert state.serial_number is None
    assert state.da_version is None


def test_state_copy_is_independent() -> None:
    state = ReceiverState(power=True, volume=42, input_source=InputSource.USB)
    copy = state.copy()
    assert copy.power is True
    assert copy.volume == 42
    assert copy.input_source == InputSource.USB

    copy.power = False
    copy.volume = 0
    assert state.power is True
    assert state.volume == 42


async def test_initial_state_after_connect(receiver: McIntoshReceiver) -> None:
    state = receiver.state
    assert state.power is True
    assert state.volume == 50
    assert state.mute is False
    assert state.input_source == InputSource.UNBALANCED2  # INP=3
    assert state.balance == 0
    assert state.tone_enabled is True
    assert state.bass == 0
    assert state.treble == 0
    assert state.input_trim == 0
    assert state.tone_mode == ToneMode.STEREO
    assert state.meter_lights is True
    assert state.display_brightness == 2


# ---------------------------------------------------------------------------
# Query method tests
# ---------------------------------------------------------------------------


async def test_query_power_on(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial._query_responses["PWR"] = ["(PWR 1)"]
    assert await receiver.query_power() is True


async def test_query_power_off(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial._query_responses["PWR"] = ["(PWR 0)"]
    assert await receiver.query_power() is False


async def test_query_volume(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["VOL"] = ["(VOL 75)"]
    assert await receiver.query_volume() == 75


async def test_query_mute_on(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["MUT"] = ["(MUT 1)"]
    assert await receiver.query_mute() is True


async def test_query_mute_off(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial._query_responses["MUT"] = ["(MUT 0)"]
    assert await receiver.query_mute() is False


async def test_query_input(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["INP"] = ["(INP 6)"]
    assert await receiver.query_input() == InputSource.PHONO


async def test_query_balance(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["TBA"] = ["(TBA -20)"]
    assert await receiver.query_balance() == -20


async def test_query_tone(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["TTN"] = ["(TTN 0)"]
    assert await receiver.query_tone() is False


async def test_query_bass(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["TTB"] = ["(TTB -3)"]
    assert await receiver.query_bass() == -3


async def test_query_treble(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial._query_responses["TTT"] = ["(TTT 4)"]
    assert await receiver.query_treble() == 4


async def test_query_input_trim(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial._query_responses["TIN"] = ["(TIN -6)"]
    assert await receiver.query_input_trim() == -6


async def test_query_tone_mode(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial._query_responses["TMO"] = ["(TMO 1)"]
    assert await receiver.query_tone_mode() == ToneMode.MONO


# ---------------------------------------------------------------------------
# Command (set) tests
# ---------------------------------------------------------------------------


async def test_power_on(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.power_on()
    assert b"(PWR 1)" in mock_serial.written_data


async def test_power_off(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.power_off()
    assert b"(PWR 0)" in mock_serial.written_data


async def test_set_volume(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.set_volume(42)
    assert b"(VOL 42)" in mock_serial.written_data


async def test_set_volume_min(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_volume(0)
    assert b"(VOL 0)" in mock_serial.written_data


async def test_set_volume_max(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_volume(100)
    assert b"(VOL 100)" in mock_serial.written_data


async def test_set_volume_above_max_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_volume(101)


async def test_set_volume_below_min_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_volume(-1)


async def test_set_volume_respects_max_volume_limit() -> None:
    """A receiver configured with max_volume=80 should reject volume 81."""
    mock = MockSerialConnection()
    recv = await connect_with_defaults(mock)
    # Override max_volume after connect to simulate a configured limit.
    recv._max_volume = 80
    with pytest.raises(ValueError):
        await recv.set_volume(81)
    await recv.disconnect()


async def test_volume_up(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    # state.volume starts at 50 from DEFAULT_QUERY_RESPONSES
    await receiver.volume_up()
    assert b"(VOL 51)" in mock_serial.written_data


async def test_volume_down(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.volume_down()
    assert b"(VOL 49)" in mock_serial.written_data


async def test_volume_up_at_max_clamps(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial.inject_response("(VOL 100)")
    await asyncio.sleep(0.05)
    await receiver.volume_up()
    assert b"(VOL 100)" in mock_serial.written_data


async def test_volume_down_at_zero_clamps(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial.inject_response("(VOL 0)")
    await asyncio.sleep(0.05)
    await receiver.volume_down()
    assert b"(VOL 0)" in mock_serial.written_data


async def test_mute_on(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.mute_on()
    assert b"(MUT 1)" in mock_serial.written_data


async def test_mute_off(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.mute_off()
    assert b"(MUT 0)" in mock_serial.written_data


async def test_select_input(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.select_input(InputSource.PHONO)
    assert b"(INP 6)" in mock_serial.written_data


async def test_select_input_hdmi(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.select_input(InputSource.HDMI)
    assert b"(INP 13)" in mock_serial.written_data


async def test_set_balance(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.set_balance(-10)
    assert b"(TBA -10)" in mock_serial.written_data


async def test_set_balance_center(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_balance(0)
    assert b"(TBA 0)" in mock_serial.written_data


async def test_set_balance_above_max_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_balance(51)


async def test_set_balance_below_min_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_balance(-51)


async def test_tone_on(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.tone_on()
    assert b"(TTN 1)" in mock_serial.written_data


async def test_tone_off(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.tone_off()
    assert b"(TTN 0)" in mock_serial.written_data


async def test_set_bass(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.set_bass(3)
    assert b"(TTB 3)" in mock_serial.written_data


async def test_set_bass_negative(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_bass(-4)
    assert b"(TTB -4)" in mock_serial.written_data


async def test_set_bass_above_max_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_bass(7)


async def test_set_bass_below_min_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_bass(-7)


async def test_set_treble(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    await receiver.set_treble(2)
    assert b"(TTT 2)" in mock_serial.written_data


async def test_set_treble_above_max_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_treble(7)


async def test_set_input_trim(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_input_trim(-6)
    assert b"(TIN -6)" in mock_serial.written_data


async def test_set_input_trim_above_max_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_input_trim(13)


async def test_set_input_trim_below_min_raises(receiver: McIntoshReceiver) -> None:
    with pytest.raises(ValueError):
        await receiver.set_input_trim(-13)


async def test_set_tone_mode_mono(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_tone_mode(ToneMode.MONO)
    assert b"(TMO 1)" in mock_serial.written_data


async def test_set_tone_mode_stereo(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_tone_mode(ToneMode.STEREO)
    assert b"(TMO 0)" in mock_serial.written_data


async def test_meter_lights_on(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.meter_lights_on()
    assert b"(TML 1)" in mock_serial.written_data


async def test_meter_lights_off(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.meter_lights_off()
    assert b"(TML 0)" in mock_serial.written_data


async def test_set_display_brightness(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    await receiver.set_display_brightness(4)
    assert b"(TDB 4)" in mock_serial.written_data


async def test_set_display_brightness_above_max_raises(
    receiver: McIntoshReceiver,
) -> None:
    with pytest.raises(ValueError):
        await receiver.set_display_brightness(5)


async def test_set_display_brightness_below_min_raises(
    receiver: McIntoshReceiver,
) -> None:
    with pytest.raises(ValueError):
        await receiver.set_display_brightness(0)


# ---------------------------------------------------------------------------
# Unsolicited event tests (receiver pushes state without being asked)
# ---------------------------------------------------------------------------


async def test_event_volume(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    states: list[ReceiverState | None] = []
    receiver.subscribe(states.append)

    mock_serial.inject_response("(VOL 75)")
    await asyncio.sleep(0.05)

    assert receiver.state.volume == 75
    assert len(states) == 1
    assert states[0] is not None
    assert states[0].volume == 75


async def test_event_volume_compact_token_fires_callback(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    states: list[ReceiverState | None] = []
    receiver.subscribe(states.append)

    mock_serial.inject_response("(VOL76)")
    await asyncio.sleep(0.05)

    assert receiver.state.volume == 76
    assert len(states) == 1
    assert states[0] is not None
    assert states[0].volume == 76


async def test_event_mute(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial.inject_response("(MUT 1)")
    await asyncio.sleep(0.05)
    assert receiver.state.mute is True


async def test_event_input(receiver: McIntoshReceiver, mock_serial: MockSerialConnection) -> None:
    mock_serial.inject_response("(INP 6)")
    await asyncio.sleep(0.05)
    assert receiver.state.input_source == InputSource.PHONO


async def test_event_power_off(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial.inject_response("(PWR 0)")
    await asyncio.sleep(0.05)
    assert receiver.state.power is False


async def test_event_balance_negative(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial.inject_response("(TBA -25)")
    await asyncio.sleep(0.05)
    assert receiver.state.balance == -25


async def test_event_multi_token_packet(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    """Multiple tokens in one packet should update all matching state fields."""
    mock_serial.inject_response("(VOL 60)(MUT 1)(INP 11)")
    await asyncio.sleep(0.05)

    state = receiver.state
    assert state.volume == 60
    assert state.mute is True
    assert state.input_source == InputSource.USB


async def test_event_firmware_and_serial(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    mock_serial.inject_response("(Serial Number: AFP2999)(FW Version: 2.05)")
    await asyncio.sleep(0.05)

    state = receiver.state
    assert state.serial_number == "AFP2999"
    assert state.firmware_version == "2.05"


async def test_event_power_on_dump(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    """Simulate the full state dump the MA5300 sends when powered on."""
    mock_serial.inject_response(
        "(Serial Number: AFP2999)(FW Version: 2.05)"
        "(PWR 1)(VOL 43)(MUT 0)(INP 11)(TBA 0)(TIN 0)"
        "(TTN 1)(TTB 3)(TTT 1)(TMO 0)(TML 1)(TDB 3)"
    )
    await asyncio.sleep(0.05)

    state = receiver.state
    assert state.serial_number == "AFP2999"
    assert state.firmware_version == "2.05"
    assert state.power is True
    assert state.volume == 43
    assert state.input_source == InputSource.USB
    assert state.bass == 3
    assert state.treble == 1
    assert state.meter_lights is True
    assert state.display_brightness == 3


async def test_event_no_change_no_notification(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    """Injecting the same value should not trigger a subscriber callback."""
    states: list[ReceiverState | None] = []
    receiver.subscribe(states.append)

    # Inject the same volume that is already in state (50 from fixture).
    mock_serial.inject_response("(VOL 50)")
    await asyncio.sleep(0.05)

    assert len(states) == 0


async def test_event_unknown_key_ignored(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    """Unknown token keys should not crash and should not change state."""
    original = receiver.state
    mock_serial.inject_response("(XYZ 99)")
    await asyncio.sleep(0.05)

    state = receiver.state
    assert state.volume == original.volume
    assert state.power == original.power


# ---------------------------------------------------------------------------
# Subscriber tests
# ---------------------------------------------------------------------------


async def test_subscribe_unsubscribe(
    receiver: McIntoshReceiver, mock_serial: MockSerialConnection
) -> None:
    states: list[ReceiverState | None] = []
    unsubscribe = receiver.subscribe(states.append)

    mock_serial.inject_response("(VOL 60)")
    await asyncio.sleep(0.05)
    assert len(states) == 1

    unsubscribe()

    mock_serial.inject_response("(VOL 70)")
    await asyncio.sleep(0.05)
    # No new callbacks after unsubscribe.
    assert len(states) == 1


async def test_subscriber_receives_none_on_disconnect(
    receiver: McIntoshReceiver,
) -> None:
    states: list[ReceiverState | None] = []
    receiver.subscribe(states.append)

    await receiver.disconnect()

    assert not receiver.connected
    assert len(states) == 1
    assert states[0] is None


# ---------------------------------------------------------------------------
# Connection tests
# ---------------------------------------------------------------------------


async def test_connect_sends_sta_enable() -> None:
    """connect() must enable unsolicited status updates before anything else."""
    mock = MockSerialConnection()
    mock._query_responses = dict(DEFAULT_QUERY_RESPONSES)

    async def fake_open(*args: object, **kwargs: object) -> tuple[asyncio.StreamReader, object]:
        return mock.reader, mock.writer

    with patch(
        "mcintosh_rs232.receiver.serialx.open_serial_connection",
        side_effect=fake_open,
    ):
        recv = McIntoshReceiver("/dev/ttyUSB0")
        await recv.connect()

    assert b"(STA 1)" in mock.written_data
    await recv.disconnect()


async def test_connect_no_response_raises() -> None:
    """connect() must raise ConnectionError when the receiver does not respond."""
    mock = MockSerialConnection()
    # No responses configured → query_power() will time out.

    async def fake_open(*args: object, **kwargs: object) -> tuple[asyncio.StreamReader, object]:
        return mock.reader, mock.writer

    with patch(
        "mcintosh_rs232.receiver.serialx.open_serial_connection",
        side_effect=fake_open,
    ):
        recv = McIntoshReceiver("/dev/ttyUSB0")
        with pytest.raises(ConnectionError):
            await recv.connect()

    assert not recv.connected


async def test_connect_populates_state() -> None:
    mock = MockSerialConnection()
    recv = await connect_with_defaults(mock)

    assert recv.connected
    assert recv.state.power is True
    assert recv.state.volume == 50
    await recv.disconnect()


async def test_query_state_populates_all_params() -> None:
    """query_state() should query every param in _QUERYABLE_PARAMS."""
    mock = MockSerialConnection()
    recv = await connect_with_defaults(mock)

    for param in _QUERYABLE_PARAMS:
        assert f"({param})" in {d.decode("ascii") for d in mock.written_data}, (
            f"Expected ({param}) to have been queried"
        )

    await recv.disconnect()


async def test_disconnect_closes_connection(receiver: McIntoshReceiver) -> None:
    assert receiver.connected
    await receiver.disconnect()
    assert not receiver.connected


async def test_state_property_returns_copy(receiver: McIntoshReceiver) -> None:
    s1 = receiver.state
    s2 = receiver.state
    assert s1 is not s2
    s1.volume = 999
    assert receiver.state.volume == 50  # original unmodified


# ---------------------------------------------------------------------------
# Enum coverage tests
# ---------------------------------------------------------------------------


def test_all_input_sources_have_unique_values() -> None:
    values = [src.value for src in InputSource]
    assert len(values) == len(set(values))


def test_input_source_round_trip() -> None:
    for src in InputSource:
        assert InputSource(src.value) is src


def test_tone_mode_round_trip() -> None:
    for mode in ToneMode:
        assert ToneMode(mode.value) is mode
