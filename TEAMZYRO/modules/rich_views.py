from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from TEAMZYRO import app
from TEAMZYRO.unit.rich_ui import rich_button, rich_card


@app.on_callback_query(filters.regex("^rich_rank$"))
async def rich_rank(client: Client, query: CallbackQuery):
    card = rich_card(
        "USER RANKING",
        "Open /rank for the full ranking screen.",
        [[
            rich_button("⬅ Menu", callback_data="rich_home", style="link"),
        ]],
    )
    await query.message.edit_text(rich_message=card)
    await query.answer()


@app.on_callback_query(filters.regex("^rich_hmode$"))
async def rich_hmode(client: Client, query: CallbackQuery):
    card = rich_card(
        "HAREM FILTER",
        "Open /hmode to use the full rarity filter.",
        [[
            rich_button("⬅ Menu", callback_data="rich_home", style="link"),
        ]],
    )
    await query.message.edit_text(rich_message=card)
    await query.answer()
