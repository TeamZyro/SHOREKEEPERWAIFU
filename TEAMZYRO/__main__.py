import asyncio

# Create and install the single application event loop BEFORE importing TEAMZYRO.
# Motor, Pyrogram/Kurigram and PTB must all share this same loop.
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from TEAMZYRO import *
import importlib
from pyrogram import idle
from TEAMZYRO.modules import ALL_MODULES


def main() -> None:
    for module_name in ALL_MODULES:
        importlib.import_module("TEAMZYRO.modules." + module_name)

    LOGGER("TEAMZYRO.modules").info(
        "𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳..."
    )

    # PTB Application is used for InlineQueryHandler processing only.
    # Pyrogram/Kurigram remains the single Telegram update receiver.
    loop.run_until_complete(application.initialize())

    if application.post_init:
        loop.run_until_complete(application.post_init(application))

    loop.run_until_complete(application.start())

    # Ensure the Pyrogram client explicitly uses the same loop as Motor/PTB.
    ZYRO.loop = loop
    ZYRO.start()

    LOGGER("TEAMZYRO").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎MADE BY TEAMZYRO☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    send_start_message()

    try:
        idle()
    finally:
        if ZYRO.is_connected:
            ZYRO.stop()

        if application.running:
            loop.run_until_complete(application.stop())
        loop.run_until_complete(application.shutdown())

        if not loop.is_closed():
            loop.close()


if __name__ == "__main__":
    main()
