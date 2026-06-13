import asyncio

from mcintosh_rs232 import InputSource, McIntoshReceiver


async def main() -> int:
    receiver = McIntoshReceiver("/dev/ttyS0")
    try:
        await receiver.connect()
    except FileNotFoundError as ex:
        print(f"Connection failed with message {ex}")
        return 1

    await receiver.query_state()
    # State is fully populated after query_state()
    print(f"Power:  {receiver.state.power}")
    print(f"Volume: {receiver.state.volume}")
    print(f"Input:  {receiver.state.input_source}\n")

    # Control the receiver
    await receiver.set_volume(35)
    await receiver.select_input(InputSource.USB)

    await receiver.power_off()
    power = await receiver.query_power()  # bool
    print(f"Result: {power}\n")

    await receiver.query_state()
    print(f"Power:  {receiver.state.power}")
    print(f"Volume: {receiver.state.volume}")
    print(f"Input:  {receiver.state.input_source}")
    print("")

    await receiver.disconnect()
    return 0


asyncio.run(main())
