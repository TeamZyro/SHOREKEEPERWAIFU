from pyrogram import Client, filters
from TEAMZYRO import app
from TEAMZYRO.unit.rich_ui import rich_button, send_rich_card

@app.on_message(filters.command("rich") & filters.private)
async def rich_menu(client: Client, message):
    rows = [
        [
            rich_button("💰 Balance", callback_data="rich_balance", style="success"),
            rich_button("🏆 Rankings", callback_data="rich_rank", style="primary"),
        ],
        [
            rich_button("🌸 Harem Filter", callback_data="rich_hmode", style="primary"),
            rich_button("⚙️ Help", callback_data="rich_help", style="primary"),
        ],
    ]
    await send_rich_card(
        client,
        message.chat.id,
        "SHOREKEEPER • RICH UI",
        "Bot API 10.3 Rich Messages are enabled. Choose a section below.",
        buttons=rows,
    )
