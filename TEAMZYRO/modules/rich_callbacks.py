from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from TEAMZYRO import app, user_collection
from TEAMZYRO.unit.rich_ui import rich_button, send_rich_card


async def _replace(client, query, title, body, buttons):
    await send_rich_card(client, query.message.chat.id, title, body, buttons=buttons)
    try:
        await query.message.delete()
    except Exception:
        pass
    await query.answer()


@app.on_callback_query(filters.regex("^rich_balance$"))
async def rich_balance(client: Client, query: CallbackQuery):
    user = await user_collection.find_one({"id": query.from_user.id}) or {}
    await _replace(
        client,
        query,
        "YOUR BALANCE",
        "💰 Coins: " + str(user.get("balance", 0)) + "\n🪙 Tokens: " + str(user.get("tokens", 0)),
        [[rich_button("⬅ Menu", callback_data="rich_home", style="link")]],
    )


@app.on_callback_query(filters.regex("^rich_home$"))
async def rich_home(client: Client, query: CallbackQuery):
    await _replace(
        client,
        query,
        "SHOREKEEPER • RICH UI",
        "Bot API 10.3 Rich Messages are enabled.",
        [[
            rich_button("💰 Balance", callback_data="rich_balance", style="success"),
            rich_button("🏆 Rankings", callback_data="rich_rank", style="primary"),
        ]],
    )
