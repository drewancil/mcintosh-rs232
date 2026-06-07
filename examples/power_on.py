#!/usr/bin/env python3

import asyncio

from mcintosh_rs232 import McIntoshReceiver


async def main() -> int:
    receiver = McIntoshReceiver("/dev/ttyS0")
    
    await receiver.connect()

    #try:
    #  await receiver.connect()
    #except (FileNotFoundError, OSError) as ex:
    #  print(f"Connection failed with message {ex}")
    #  return 1

    

    await receiver.query_state()
    # state is fully populated after query_state()
    print(f"Power:  {receiver.state.power}")
    print(f"Volume: {receiver.state.volume}")
    print(f"Input:  {receiver.state.input_source}")

    await receiver.power_on()
    #await receiver.meter_lights_off()
    #await receiver.power_off()
    # power = await receiver.query_power()
    # print(f"Result: {power}\n")


    #await receiver.query_state()
    #print(f"Power:  {receiver.state.power}")
    #print(f"Volume: {receiver.state.volume}")
    #print(f"Input:  {receiver.state.input_source}")

    await receiver.disconnect()
    return 0

asyncio.run(main())
