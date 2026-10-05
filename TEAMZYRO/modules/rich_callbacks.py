from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from TEAMZYRO import app, user_collection
from TEAMZYRO.unit.rich_ui import rich_button, rich_card


@app.on_callback_query(filters.regex("^rich_balance$"))
async def rich_balance(client: Client, query: CallbackQuery):
    user = await user_collection.find_one({"id": query.from_user.id}) or {}
    card = rich_card(
        "YOUR BALANCE",
        "💰 Coins: " + str(user.get("balance", 0)) + "\n🪙 Tokens: " + str(user.get("tokens", 0)),
        [[
            rich_button("⬅ Menu", callback_data="rich_home", style="link"),
        ]],
    )
    await query.message.edit_text(rich_message=card)
    await query.answer()


@app.on_callback_query(filters.regex("^rich_home$"))
async def rich_home(client: Client, query: CallbackQuery):
    card = rich_card(
        "SHOREKEEPER • RICH UI",
        "Bot API 10.3 Rich Messages are enabled.",
        [[
            rich_button("💰 Balance", callback_data="rich_balance", style="success"),
        ]],
    )
    await query.message.edit_text(rich_message=card)
    await query.answer()
