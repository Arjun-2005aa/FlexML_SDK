"""Control the FlexML app from your computer: a tiny command prompt.

Type commands in the same text form the Bluetooth link uses, for example:

    get_status
    list_models
    start_live ar
    set_model yolo
    set_classes person,cup
    set_threshold 0.5
    set_stream_rate 10
    start_recording / stop_recording
    reset_map
    save_space Kitchen
    screen off

The full list is in docs/robot-integration.md. Commands must be allowed in the app
(Network Setup › Remote control › Accept commands from robots).

    python remote_control.py
"""
import asyncio
import json

import flexml_companion as flexml


async def main() -> None:
    async with flexml.Server() as phone:
        print(f"Waiting for FlexML at {phone.address} …")
        await phone.wait_for_phone()
        print("Connected. Type a command (Ctrl-D to quit).")
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, input, "flexml> ")
            except EOFError:
                break
            if not line.strip():
                continue
            try:
                result = await phone.command_text(line)
                print(json.dumps(result, indent=2))
            except flexml.FlexMLError as e:
                print("error:", e)
            except asyncio.TimeoutError:
                print("no reply (is the phone still connected?)")


if __name__ == "__main__":
    asyncio.run(main())
