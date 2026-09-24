from TEAMZYRO import *
import importlib
import logging
from TEAMZYRO.modules import ALL_MODULES

def main() -> None:
    for module_name in ALL_MODULES:
        imported_module = importlib.import_module("TEAMZYRO.modules." + module_name)
    LOGGER("TEAMZYRO.modules").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")

    ZYRO.start()
    LOGGER("TEAMZYRO").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎MADE BY TEAMZYRO☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    send_start_message()
    application.run_polling(drop_pending_updates=True)   # ✅ ab yeh SABSE LAST hai

if __name__ == "__main__":
    main()
