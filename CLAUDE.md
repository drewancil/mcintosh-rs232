# mcintosh-rs232

Async Python library to control McIntosh Audio receivers over RS232 serial.

## Project structure

```
src/mcintosh_rs232/
  __init__.py    -- Main library: enums, ReceiverState, DenonReceiver class
  models.py      -- ReceiverModel dataclass and per-model definitions
  __main__.py    -- CLI: python -m denon_rs232 PORT [--probe] [--zone3-prefix Z1|Z3]

tests/
  conftest.py          -- MockSerialConnection, fixtures (receiver, mock_serial), DEFAULT_QUERY_RESPONSES
  test_denon_rs232.py  -- Query, control, event, and teardown tests
  test_probe.py        -- Source probing tests
  test_models.py       -- Model definition tests
```

## Architecture

- Uses `serialx` (`open_serial_connection`) for async serial I/O (115200 baud, 8N1).
- McIntosh RS232 protocol: `( + FUNCTION + VALUE + )`. Query with `QRY`. Responses within 200ms.
- `connect()` only opens/verifies the serial connection via `QRY`.
- `query_state()` fetches current receiver state (single-response via `_query()`, multi-response via fire-and-forget + `asyncio.sleep(MULTI_RESPONSE_DELAY)`).
- After querying, state is kept current via a background `_read_loop` that processes events.
- `state` property returns a deep copy of `ReceiverState`.
- Subscribers get `ReceiverState` on changes, `None` on disconnect.
