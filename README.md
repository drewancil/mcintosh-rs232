# mcintosh-rs232

Async Python library to control McIntosh integrated amplifiers over RS232 serial, built on [serialx](https://github.com/puddly/serialx).

Developed and tested against the **MA5300** Integrated Amplifier. The RS232 protocol is common across McIntosh's integrated amplifier line, so other models should work with little or no changes.

## Installation

```bash
pip install mcintosh-rs232
```

Requires Python 3.12+.

## Quick start

```python
import asyncio
from mcintosh_rs232 import McIntoshReceiver, InputSource

async def main():
    receiver = McIntoshReceiver("/dev/ttyUSB0")
    await receiver.connect()
    await receiver.query_state()

    # State is fully populated after query_state()
    print(f"Power:  {receiver.state.power}")
    print(f"Volume: {receiver.state.volume}")
    print(f"Input:  {receiver.state.input_source}")

    # Control the amplifier
    await receiver.set_volume(45)
    await receiver.select_input(InputSource.USB)

    await receiver.disconnect()

asyncio.run(main())
```

## CLI

A built-in CLI lets you quickly test your serial connection:

```bash
# Query and print amplifier status
python -m mcintosh_rs232 /dev/ttyUSB0

# Set a maximum volume limit
python -m mcintosh_rs232 /dev/ttyUSB0 --max-volume 80
```

## Features

### Full state after query

`connect()` opens the serial connection, enables unsolicited status updates from the amplifier (`STA 1`), and verifies the connection by querying power state. Call `query_state()` to populate all remaining state fields. After that, state is kept up to date automatically via push events from the amplifier.

```python
receiver = McIntoshReceiver("/dev/ttyUSB0")
await receiver.connect()
await receiver.query_state()

state = receiver.state
state.power               # bool — True = on, False = off
state.volume              # int 0–100
state.mute                # bool
state.input_source        # InputSource enum
state.balance             # int -50 to +50 (negative = left, positive = right)
state.tone_enabled        # bool
state.bass                # int -6 to +6
state.treble              # int -6 to +6
state.input_trim          # int -12 to +12
state.tone_mode           # ToneMode enum (STEREO or MONO)
state.meter_lights        # bool
state.display_brightness  # int 1–4
state.serial_number       # str or None (populated on power-on or QRY)
state.firmware_version    # str or None
state.da_version          # str or None
```

`state` always returns a snapshot copy — mutations to it do not affect the receiver's internal state.

### Event subscription

Subscribe to state changes to react in real-time. Callbacks receive an `AmplifierState` snapshot on updates, or `None` when the connection is lost.

```python
def on_state_change(state):
    if state is None:
        print("Disconnected!")
        return
    print(f"Volume: {state.volume}, Source: {state.input_source}")

unsub = receiver.subscribe(on_state_change)
# Later:
unsub()  # stop receiving events
```

### Power

```python
await receiver.power_on()
await receiver.power_off()
power = await receiver.query_power()  # bool
```

### Volume

Volume is an integer from 0 to 100. An optional `max_volume` limit can be configured when creating the receiver:

```python
receiver = McIntoshReceiver("/dev/ttyUSB0", max_volume=80)
```

```python
await receiver.set_volume(50)
await receiver.volume_up()          # increments by 1
await receiver.volume_down()        # decrements by 1
vol = await receiver.query_volume() # int
```

`set_volume()` raises `ValueError` if the value is outside 0–`max_volume`. `volume_up()` and `volume_down()` clamp at the limits without raising.

### Mute

```python
await receiver.mute_on()
await receiver.mute_off()
muted = await receiver.query_mute()  # bool
```

### Input source

```python
from mcintosh_rs232 import InputSource

await receiver.select_input(InputSource.USB)
await receiver.select_input(InputSource.PHONO)
source = await receiver.query_input()  # InputSource enum
```

See [Input sources](#input-sources) below for the full list.

### Balance

Range is -50 (full left) to +50 (full right). 0 is centre.

```python
await receiver.set_balance(0)     # centre
await receiver.set_balance(-15)   # left
await receiver.set_balance(10)    # right
bal = await receiver.query_balance()  # int
```

### Tone controls

```python
await receiver.tone_on()
await receiver.tone_off()
enabled = await receiver.query_tone()  # bool

await receiver.set_bass(3)          # -6 to +6
await receiver.set_treble(-2)       # -6 to +6
bass = await receiver.query_bass()
treble = await receiver.query_treble()
```

### Input trim

Per-input gain trim, -12 to +12.

```python
await receiver.set_input_trim(-3)
trim = await receiver.query_input_trim()  # int
```

### Tone mode

```python
from mcintosh_rs232 import ToneMode

await receiver.set_tone_mode(ToneMode.STEREO)
await receiver.set_tone_mode(ToneMode.MONO)
mode = await receiver.query_tone_mode()  # ToneMode enum
```

### Meter lights

```python
await receiver.meter_lights_on()
await receiver.meter_lights_off()
```

### Display brightness

Range is 1 (dim) to 4 (brightest).

```python
await receiver.set_display_brightness(3)
```

### Connection handling

- If the amplifier does not respond during `connect()`, a `ConnectionError` is raised and the connection is closed cleanly.
- If the serial connection is lost (cable unplugged, device error), all subscribers receive `None` and `connected` becomes `False`.
- Write errors during commands propagate the exception and tear down the connection.

```python
try:
    await receiver.connect()
except ConnectionError:
    print("Amplifier not responding")
```

## Input sources

| Constant | Input number | Description |
|----------|-------------|-------------|
| `BALANCED` | 1 | Balanced XLR |
| `UNBALANCED1` | 2 | Unbalanced RCA 1 |
| `UNBALANCED2` | 3 | Unbalanced RCA 2 |
| `UNBALANCED3` | 4 | Unbalanced RCA 3 |
| `UNBALANCED4` | 5 | Unbalanced RCA 4 |
| `PHONO` | 6 | Phono (MM) |
| `COAX1` | 7 | Coaxial digital 1 |
| `COAX2` | 8 | Coaxial digital 2 |
| `OPTICAL1` | 9 | Optical (TOSLINK) 1 |
| `OPTICAL2` | 10 | Optical (TOSLINK) 2 |
| `USB` | 11 | USB Audio |
| `MCT` | 12 | MCT (McIntosh disc transport) |
| `HDMI` | 13 | HDMI |

## Serial connection

The library uses [serialx](https://github.com/puddly/serialx) for async serial I/O. The MA5300 communicates at **115200 baud, 8 data bits, no parity, 1 stop bit**.

The RS232 port on the MA5300 is a standard DB-9 connector.

The McIntosh RS232 protocol wraps commands in parentheses: `(KEY VALUE)`. Responses are terminated with `}`. The amplifier sends a full state dump on power-on and whenever `(QRY)` is issued.

## Development

Install dev dependencies (requires [uv](https://github.com/astral-sh/uv)):

```bash
cd mcintosh-rs232
uv sync
```

Or with pip into a virtualenv:

```bash
pip install pytest pytest-asyncio pytest-timeout serialx
```

### Running tests

```bash
# Run all tests
uv run pytest

# Verbose output with test names
uv run pytest -v

# Run a specific test
uv run pytest tests/test_mcintosh_rs232.py::test_event_power_on_dump -v
```

All tests use a `MockSerialConnection` — no real hardware is required. The mock feeds `}`-terminated response packets directly into `asyncio.StreamReader`, exercising the full receive path.

### Linting and type checking

```bash
uv run ruff check src/ tests/
uv run mypy src/
```

## License

MIT
