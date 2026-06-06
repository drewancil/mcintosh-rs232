"""CLI for testing a McIntosh amplifier over RS232.

Usage::

    python -m mcintosh_rs232 /dev/ttyUSB0
    python -m mcintosh_rs232 /dev/ttyUSB0 --max-volume 80
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from . import AmplifierState, McIntoshReceiver


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
        return str(val.name)
    return str(val)


def _print_state(state: AmplifierState) -> None:
    print()
    print("=== McIntosh Amplifier Status ===")
    print()
    print(f"  Power:              {_fmt_bool(state.power)}")
    print(f"  Volume:             {_fmt_int(state.volume)}")
    print(f"  Mute:               {_fmt_bool(state.mute)}")
    print(f"  Input source:       {_fmt_enum(state.input_source)}")
    print(f"  Balance:            {_fmt_int(state.balance)}")
    print()
    print(f"  Tone enabled:       {_fmt_bool(state.tone_enabled)}")
    print(f"  Bass:               {_fmt_int(state.bass)}")
    print(f"  Treble:             {_fmt_int(state.treble)}")
    print(f"  Tone mode:          {_fmt_enum(state.tone_mode)}")
    print(f"  Input trim:         {_fmt_int(state.input_trim)}")
    print()
    print(f"  Meter lights:       {_fmt_bool(state.meter_lights)}")
    print(f"  Display brightness: {_fmt_int(state.display_brightness)}")

    if state.serial_number or state.firmware_version or state.da_version:
        print()
        print("  Device info:")
        if state.serial_number:
            print(f"    Serial number:  {state.serial_number}")
        if state.firmware_version:
            print(f"    Firmware:       {state.firmware_version}")
        if state.da_version:
            print(f"    DA version:     {state.da_version}")
    print()


async def _main(args: argparse.Namespace) -> int:
    receiver = McIntoshReceiver(args.port, max_volume=args.max_volume)
    try:
        print(f"Connecting to {args.port} ...")
        await receiver.connect()
        print("Querying state ...")
        await receiver.query_state()
        _print_state(receiver.state)
    except ConnectionError as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if receiver.connected:
            await receiver.disconnect()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="McIntosh RS232 CLI — connect and print current state."
    )
    parser.add_argument("port", help="Serial port (e.g. /dev/ttyUSB0 or COM3)")
    parser.add_argument(
        "--max-volume",
        type=int,
        default=100,
        metavar="N",
        help="Maximum volume limit (default: 100)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
