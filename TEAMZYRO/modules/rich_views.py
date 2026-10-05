from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from TEAMZYRO import app
from TEAMZYRO.unit.rich_ui import rich_button, send_rich_card


@app.on_callback_query(filters.regex("^rich_rank$"))
async def rich_rank(client: Client, query: CallbackQuery):
    await send_rich_card(
        client,
        query.message.chat.id,
        "USER RANKING",
        "Open /rank for the full ranking screen.",
        buttons=[[rich_button("⬅ Menu", callback_data="rich_home", style="link")]],
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()


@app.on_callback_query(filters.regex("^rich_hmode$"))
async def rich_hmode(client: Client, query: CallbackQuery):
    await send_rich_card(
        client,
        query.message.chat.id,
        "HAREM FILTER",
        "Open /hmode to use the full rarity filter.",
        buttons=[[rich_button("⬅ Menu", callback_data="rich_home", style="link")]],
    )
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()
