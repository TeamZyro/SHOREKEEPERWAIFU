from TEAMZYRO import *
import importlib
import asyncio
from pyrogram import idle
import logging
from TEAMZYRO.modules import ALL_MODULES


def main() -> None:
    for module_name in ALL_MODULES:
        importlib.import_module("TEAMZYRO.modules." + module_name)

    LOGGER("TEAMZYRO.modules").info(
        "𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳..."
    )

    loop = asyncio.get_event_loop()

    # PTB Application is used for InlineQueryHandler processing only.
    # It is intentionally NOT started with run_polling(), because Pyrogram
    # is the single Telegram update receiver for the bot token.
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())

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


if __name__ == "__main__":
    main()
