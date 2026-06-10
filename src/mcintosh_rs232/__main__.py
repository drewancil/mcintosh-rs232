"""CLI for controlling a McIntosh amplifier over RS232.

Usage::

    # Print current state
    python -m mcintosh_rs232 --port /dev/ttyS0

    # Power on/off
    python -m mcintosh_rs232 --port /dev/ttyS0 --power on
    python -m mcintosh_rs232 --port /dev/ttyS0 --power off

    # Set volume, mute, input, tone controls
    python -m mcintosh_rs232 --port /dev/ttyS0 --volume 35
    python -m mcintosh_rs232 --port /dev/ttyS0 --volume-up
    python -m mcintosh_rs232 --port /dev/ttyS0 --volume-down
    python -m mcintosh_rs232 --port /dev/ttyS0 --mute on
    python -m mcintosh_rs232 --port /dev/ttyS0 --input USB
    python -m mcintosh_rs232 --port /dev/ttyS0 --bass 4 --treble -2
    python -m mcintosh_rs232 --port /dev/ttyS0 --balance 10
    python -m mcintosh_rs232 --port /dev/ttyS0 --tone on --tone-mode stereo
    python -m mcintosh_rs232 --port /dev/ttyS0 --input-trim -3
    python -m mcintosh_rs232 --port /dev/ttyS0 --meter-lights on
    python -m mcintosh_rs232 --port /dev/ttyS0 --display-brightness 3

    # Combine multiple commands in one call
    python -m mcintosh_rs232 --port /dev/ttyS0 --volume 40 --input BALANCED --mute off
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import AmplifierState, McIntoshReceiver
from .const import (
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
    InputSource,
    ToneMode,
)


def _fmt_bool(val: bool | None, on: str = "ON", off: str = "OFF") -> str:
    if val is None:
        return "?"
    return on if val else off


def _fmt_int(val: int | None) -> str:
    if val is None:
        return "?"
    return str(val)


def _fmt_enum(val: object | None) -> str:
    if val is None:
        return "?"
    if hasattr(val, "name"):
        return str(val.name)  # type: ignore[unused-ignore]
    return str(val)


def _print_state(state: AmplifierState) -> None:
    print()
    print("===== McIntosh Component Status =====")
    print()
    print(f"  Power:               {_fmt_bool(state.power)}")
    print(f"  Volume:              {_fmt_int(state.volume)}")
    print(f"  Mute:                {_fmt_bool(state.mute)}")
    print(f"  Input Source:        {_fmt_enum(state.input_source)}")
    print(f"  Balance:             {_fmt_int(state.balance)}")
    print()
    print(f"  Tone Controls:       {_fmt_bool(state.tone_enabled)}")
    print(f"    Bass:              {_fmt_int(state.bass)}")
    print(f"    Treble:            {_fmt_int(state.treble)}")
    print(f"    Input Trim:        {_fmt_int(state.input_trim)}")
    print(f"    Tone Mode:         {_fmt_enum(state.tone_mode)}")
    print()
    print(f"  Meter Lights:        {_fmt_bool(state.meter_lights)}")
    print(f"  Display Brightness:  {_fmt_int(state.display_brightness)}")

    if state.serial_number or state.firmware_version or state.da_version or state.model:
        print()
        print("  Device Info:")
        if state.model:
            print(f"    Model:             {state.model}")
        if state.serial_number:
            print(f"    Serial Number:     {state.serial_number}")
        if state.firmware_version:
            print(f"    Firmware:          {state.firmware_version}")
        if state.da_version:
            print(f"    DA Version:        {state.da_version}")
    print()


def _on_off(value: str) -> bool:
    """Convert an on/off string argument to bool."""
    if value.lower() in ("on", "1", "true", "yes"):
        return True
    if value.lower() in ("off", "0", "false", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Expected on/off, got: {value!r}")


async def _main(args: argparse.Namespace) -> int:
    receiver = McIntoshReceiver(args.port, max_volume=args.max_volume)
    try:
        print(f"Connecting to {args.port} ...")
        await receiver.connect()
    except ConnectionError as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1

    try:
        any_command = False

        if args.power is not None:
            any_command = True
            if args.power:
                print("Powering on ...")
                await receiver.power_on()
            else:
                print("Powering off ...")
                await receiver.power_off()

        if args.volume is not None:
            any_command = True
            print(f"Setting volume to {args.volume} ...")
            await receiver.set_volume(args.volume)

        if args.volume_up:
            any_command = True
            print("Volume up ...")
            await receiver.volume_up()

        if args.volume_down:
            any_command = True
            print("Volume down ...")
            await receiver.volume_down()

        if args.mute is not None:
            any_command = True
            if args.mute:
                print("Muting ...")
                await receiver.mute_on()
            else:
                print("Unmuting ...")
                await receiver.mute_off()

        if args.input is not None:
            any_command = True
            try:
                source = InputSource[args.input.upper()]
            except KeyError:
                names = ", ".join(s.name for s in InputSource)
                print(f"Unknown input {args.input!r}. Valid inputs: {names}", file=sys.stderr)
                return 1
            print(f"Setting input to {source.name} ...")
            await receiver.select_input(source)

        if args.balance is not None:
            any_command = True
            print(f"Setting balance to {args.balance} ...")
            await receiver.set_balance(args.balance)

        if args.tone is not None:
            any_command = True
            if args.tone:
                print("Enabling tone controls ...")
                await receiver.tone_on()
            else:
                print("Disabling tone controls ...")
                await receiver.tone_off()

        if args.bass is not None:
            any_command = True
            print(f"Setting bass to {args.bass} ...")
            await receiver.set_bass(args.bass)

        if args.treble is not None:
            any_command = True
            print(f"Setting treble to {args.treble} ...")
            await receiver.set_treble(args.treble)

        if args.tone_mode is not None:
            any_command = True
            mode = ToneMode[args.tone_mode.upper()]
            print(f"Setting tone mode to {mode.name} ...")
            await receiver.set_tone_mode(mode)

        if args.input_trim is not None:
            any_command = True
            print(f"Setting input trim to {args.input_trim} ...")
            await receiver.set_input_trim(args.input_trim)

        if args.meter_lights is not None:
            any_command = True
            if args.meter_lights:
                print("Meter lights on ...")
                await receiver.meter_lights_on()
            else:
                print("Meter lights off ...")
                await receiver.meter_lights_off()

        if args.display_brightness is not None:
            any_command = True
            print(f"Setting display brightness to {args.display_brightness} ...")
            await receiver.set_display_brightness(args.display_brightness)

        if not any_command:
            print("Querying state ...")
        await receiver.query_state()

        _print_state(receiver.state)

    except (ValueError, TimeoutError) as exc:
        print(f"Command failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if receiver.connected:
            await receiver.disconnect()

    return 0


def main() -> None:
    input_names = ", ".join(s.name for s in InputSource)
    tone_mode_names = ", ".join(m.name.lower() for m in ToneMode)

    parser = argparse.ArgumentParser(
        description="McIntosh RS232 CLI — control and query the amplifier.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=str, required=True, help="Serial port (e.g. /dev/ttyS0 or COM3)"
    )

    parser.add_argument(
        "--max-volume",
        type=int,
        default=MAX_VOLUME,
        metavar="N",
        help=f"Maximum volume limit (default: {MAX_VOLUME})",
    )

    parser.add_argument(
        "--power",
        type=_on_off,
        metavar="on|off",
        help="Turn the amplifier on or off",
    )

    vol_group = parser.add_mutually_exclusive_group()
    vol_group.add_argument(
        "--volume",
        type=int,
        metavar="N",
        help=f"Set volume ({MIN_VOLUME}–max-volume)",
    )
    vol_group.add_argument(
        "--volume-up",
        action="store_true",
        help="Increase volume by one step",
    )
    vol_group.add_argument(
        "--volume-down",
        action="store_true",
        help="Decrease volume by one step",
    )

    parser.add_argument(
        "--mute",
        type=_on_off,
        metavar="on|off",
        help="Mute or unmute",
    )

    parser.add_argument(
        "--input",
        metavar="SOURCE",
        help=f"Select input source: {input_names}",
    )

    parser.add_argument(
        "--balance",
        type=int,
        metavar="N",
        help=f"Set balance ({MIN_BALANCE} to {MAX_BALANCE}, negative=left, positive=right)",
    )

    parser.add_argument(
        "--tone",
        type=_on_off,
        metavar="on|off",
        help="Enable or disable tone controls",
    )
    parser.add_argument(
        "--bass",
        type=int,
        metavar="N",
        help=f"Set bass ({MIN_BASS} to {MAX_BASS})",
    )
    parser.add_argument(
        "--treble",
        type=int,
        metavar="N",
        help=f"Set treble ({MIN_TREBLE} to {MAX_TREBLE})",
    )
    parser.add_argument(
        "--tone-mode",
        metavar="MODE",
        help=f"Set tone mode: {tone_mode_names}",
    )
    parser.add_argument(
        "--input-trim",
        type=int,
        metavar="N",
        help=f"Set input trim ({MIN_INPUT_TRIM} to {MAX_INPUT_TRIM})",
    )

    parser.add_argument(
        "--meter-lights",
        type=_on_off,
        metavar="on|off",
        help="Turn meter lights on or off",
    )

    parser.add_argument(
        "--display-brightness",
        type=int,
        metavar="N",
        help=f"Set display brightness ({MIN_DISPLAY_BRIGHTNESS}–{MAX_DISPLAY_BRIGHTNESS})",
    )

    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
