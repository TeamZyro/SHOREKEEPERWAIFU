import random, time, asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from TEAMZYRO import *  # TEAMZYRO = Owner ID here

TEAMZYRO = 7078181502

# 💰 Base rarity prices
RARITY_PRICES = {
    1: {"name": "⚪️ Common", "price": 2000},
    2: {"name": "🟣 Rare", "price": 5000},
    3: {"name": "🟡 Legendary", "price": 12000},
    4: {"name": "🟢 Medium", "price": 3000},
    5: {"name": "💮 Special Edition", "price": 15000},
    6: {"name": "🔮 Limited Edition", "price": 20000},
    7: {"name": "💸 Premium Edition", "price": 25000},
    8: {"name": "🌤 Summer", "price": 8000},
    9: {"name": "🎐 Celestial", "price": 18000},
    10: {"name": "❄️ Winter", "price": 9000},
    11: {"name": "💝 Valentine", "price": 9500},
    12: {"name": "🎃 Halloween", "price": 10000},
    13: {"name": "🎄 Christmas Special", "price": 11000},
    14: {"name": "🪐 Omniversal", "price": 30000},
    15: {"name": "🎭 Cosplay Master 🎭", "price": 35000},
    16: {"name": "🧧 Events", "price": 7000},
    17: {"name": "🍑 Echhi", "price": 17000},
    18: {"name": "🎗️ AMV Edition", "price": 13000},
    19: {"name": "🌟 Luminous", "price": 22000},
}

# 🌟 Default discount = 12%
GLOBAL_DISCOUNT = {"percent": 12, "expires_at": None, "permanent": 12}

user_shop_data = {}
refresh_cooldown = {}

# 🧮 Helper: calculate discounted price
def get_discounted_price(base_price: int):
    discount = GLOBAL_DISCOUNT["percent"]
    if discount > 0:
        new_price = int(base_price - (base_price * discount / 100))
        return new_price
    return base_price


async def discount_watcher():
    """Auto reset discount when expired"""
    while True:
        if GLOBAL_DISCOUNT["expires_at"]:
            if datetime.utcnow() > GLOBAL_DISCOUNT["expires_at"]:
                GLOBAL_DISCOUNT["percent"] = GLOBAL_DISCOUNT["permanent"]
                GLOBAL_DISCOUNT["expires_at"] = None
                print(f"🕒 Discount expired, reset to {GLOBAL_DISCOUNT['permanent']}% default")
        await asyncio.sleep(30)


@app.on_message(filters.command(["shop"]))
async def shop_menu(client, message):
    """Main shop menu"""
    buttons = []
    for i in range(1, 20, 3):
        row = []
        for j in range(i, min(i + 3, 20)):
            rarity = RARITY_PRICES[j]
            price = get_discounted_price(rarity["price"])
            row.append(
                InlineKeyboardButton(
                    f"{rarity['name']} ({price}💰)", callback_data=f"rarity_{j}"
                )
            )
        buttons.append(row)

    discount = GLOBAL_DISCOUNT["percent"]
    banner = f"🎁 **{discount}% OFF** on all rarities!\n" if discount > 0 else ""
    await message.reply(
        f"{banner}🌌 **Welcome to the Cosmic Bazaar!**\n\nChoose your rarity to explore below ↓",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex(r"^rarity_(\d+)$"))
async def show_rarity_shop(client, callback_query):
    rarity_id = int(callback_query.data.split("_")[1])
    user_id = callback_query.from_user.id

    rarity_name = RARITY_PRICES[rarity_id]["name"]
    characters_cursor = collection.find({"rarity": rarity_name})
    characters = await characters_cursor.to_list(length=None)

    if not characters:
        await callback_query.answer("🚫 No heroes found for this rarity!", show_alert=True)
        return

    sample = random.sample(characters, min(5, len(characters)))
    user_shop_data[user_id] = {"rarity": rarity_id, "characters": sample, "index": 0}
    await send_character_card(callback_query.message, user_id, 0)
    await callback_query.answer()


async def send_character_card(message, user_id, index):
    """Send a hero card"""
    data = user_shop_data[user_id]
    chars = data["characters"]
    index = index % len(chars)
    character = chars[index]

    rarity_id = data["rarity"]
    base_price = RARITY_PRICES[rarity_id]["price"]
    price = get_discounted_price(base_price)

    caption = (
        f"🌟 **{character['name']}**\n"
        f"🏰 Realm: {character['anime']}\n"
        f"💎 Rarity: {character['rarity']}\n"
        f"💰 Price: {price} Star Coins\n"
        f"🆔 ID: {character['id']}\n\n"
        f"✨ Add this hero to your collection!"
    )

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data="shop_prev"),
            InlineKeyboardButton("💫 Claim", callback_data=f"buyshop_{index}"),
            InlineKeyboardButton("➡️ Next", callback_data="shop_next"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh (5000💰)", callback_data="shop_refresh"),
            InlineKeyboardButton("🏠 Back", callback_data="shop_back"),
        ],
    ]

    try:
        await message.edit_media(
            InputMediaPhoto(media=character["img_url"], caption=caption),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        await message.reply_photo(
            photo=character["img_url"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    user_shop_data[user_id]["index"] = index


@app.on_callback_query(filters.regex("^shop_next$"))
async def shop_next(client, callback_query):
    user_id = callback_query.from_user.id
    data = user_shop_data.get(user_id)
    if not data:
        await callback_query.answer("⚠️ Please open the shop again!", show_alert=True)
        return
    await send_character_card(callback_query.message, user_id, (data["index"] + 1))
    await callback_query.answer()


@app.on_callback_query(filters.regex("^shop_prev$"))
async def shop_prev(client, callback_query):
    user_id = callback_query.from_user.id
    data = user_shop_data.get(user_id)
    if not data:
        await callback_query.answer("⚠️ Please open the shop again!", show_alert=True)
        return
    await send_character_card(callback_query.message, user_id, (data["index"] - 1))
    await callback_query.answer()


@app.on_callback_query(filters.regex("^shop_refresh$"))
async def shop_refresh(client, callback_query):
    user_id = callback_query.from_user.id
    now = time.time()

    last_refresh = refresh_cooldown.get(user_id, 0)
    if now - last_refresh < 30:
        remain = int(30 - (now - last_refresh))
        await callback_query.answer(f"⏳ Wait {remain}s before refreshing again!", show_alert=True)
        return

    user = await user_collection.find_one({"id": user_id})
    if not user:
        await callback_query.answer("🚫 You are not registered!", show_alert=True)
        return

    balance = user.get("balance", 0)
    if balance < 5000:
        await callback_query.answer("❌ Not enough coins to refresh!", show_alert=True)
        return

    # 🌟 Refresh Animation
    await callback_query.message.edit_caption("✨ Refreshing your shop... Please wait...")
    await asyncio.sleep(2.5)

    await user_collection.update_one({"id": user_id}, {"$inc": {"balance": -5000}})
    rarity_id = user_shop_data[user_id]["rarity"]
    rarity_name = RARITY_PRICES[rarity_id]["name"]

    characters_cursor = collection.find({"rarity": rarity_name})
    characters = await characters_cursor.to_list(length=None)
    sample = random.sample(characters, min(5, len(characters)))

    user_shop_data[user_id]["characters"] = sample
    user_shop_data[user_id]["index"] = 0
    refresh_cooldown[user_id] = now

    await send_character_card(callback_query.message, user_id, 0)
    await callback_query.answer("🔄 Refreshed! 5000 coins deducted.", show_alert=True)


@app.on_callback_query(filters.regex("^shop_back$"))
async def shop_back(client, callback_query):
    await shop_menu(client, callback_query.message)
    await callback_query.answer()


@app.on_callback_query(filters.regex(r"^buyshop_\d+$"))
async def buyshop(client, callback_query):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    user = await user_collection.find_one({"id": user_id})

    if not user:
        await callback_query.answer("🚫 You must register first!", show_alert=True)
        return

    data = user_shop_data.get(user_id)
    if not data:
        await callback_query.answer("⚠️ Please open the shop again!", show_alert=True)
        return

    rarity_id = data["rarity"]
    price = get_discounted_price(RARITY_PRICES[rarity_id]["price"])
    character = data["characters"][index]
    balance = user.get("balance", 0)

    if balance < price:
        await callback_query.answer(f"💰 Need {price - balance} more coins!", show_alert=True)
        return

    await user_collection.update_one(
        {"id": user_id},
        {
            "$inc": {"balance": -price},
            "$push": {
                "characters": {
                    "_id": ObjectId(),
                    "img_url": character["img_url"],
                    "name": character["name"],
                    "anime": character["anime"],
                    "rarity": character["rarity"],
                    "id": character["id"],
                }
            },
        },
    )

    await callback_query.answer("🎉 Hero successfully claimed!", show_alert=True)


# 🌟 Global discount data
GLOBAL_DISCOUNT = {
    "percent": 12,          # current active discount
    "expires_at": None,     # expiry datetime if temporary
    "permanent": 12         # default fallback discount
}


# 🕒 Background Task: Auto-reset discount when expired
async def discount_watcher():
    while True:
        if GLOBAL_DISCOUNT["expires_at"]:
            if datetime.utcnow() > GLOBAL_DISCOUNT["expires_at"]:
                GLOBAL_DISCOUNT["percent"] = GLOBAL_DISCOUNT["permanent"]
                GLOBAL_DISCOUNT["expires_at"] = None
                print(f"🕒 Discount expired, reset to {GLOBAL_DISCOUNT['permanent']}% default")
        await asyncio.sleep(30)


# ⚙️ OWNER ONLY: Set global discount (supports minutes or days like 1d, 2d)
@Client.on_message(filters.command("discount"))
async def set_discount(client, message):
    user_id = message.from_user.id
    if user_id != TEAMZYRO:
        await message.reply("🚫 You don't have permission to set discounts!")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.reply("⚙️ Usage: /discount <percent> [minutes|Xd]\nExample: /discount 40 1d")
        return

    try:
        percent = int(args[1])
        if not (0 <= percent <= 100):
            raise ValueError
    except ValueError:
        await message.reply("⚠️ Provide a valid percent between 0–100.")
        return

    duration = 60  # default = 60 minutes
    if len(args) == 3:
        time_arg = args[2].lower()
        if time_arg.endswith("d"):  # e.g. 1d, 2d
            try:
                days = int(time_arg[:-1])
                duration = days * 24 * 60
            except ValueError:
                await message.reply("⚠️ Invalid day format! Example: /discount 40 1d")
                return
        else:
            try:
                duration = int(time_arg)
            except ValueError:
                await message.reply("⚠️ Invalid time format! Use minutes or 'd' for days.")
                return

    GLOBAL_DISCOUNT["percent"] = percent
    GLOBAL_DISCOUNT["expires_at"] = datetime.utcnow() + timedelta(minutes=duration)

    duration_text = (
        f"{duration // (60*24)} day(s)" if duration >= 1440 else f"{duration} minute(s)"
    )

    await message.reply(
        f"🎁 Global discount set to **{percent}%** for **{duration_text}**.\n"
        f"After expiry → will revert to default **{GLOBAL_DISCOUNT['permanent']}%**."
    )

    asyncio.create_task(discount_watcher())


# 🧠 Anyone can check the current discount status
@Client.on_message(filters.command("discountstatus"))
async def discount_status(client, message):
    percent = GLOBAL_DISCOUNT["percent"]
    permanent = GLOBAL_DISCOUNT["permanent"]
    expires_at = GLOBAL_DISCOUNT["expires_at"]

    if expires_at:
        remaining = expires_at - datetime.utcnow()
        total_seconds = int(remaining.total_seconds())

        if total_seconds <= 0:
            time_left = "Expired (will reset soon)"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60

            if days > 0:
                time_left = f"{days}d {hours}h {minutes}m remaining"
            elif hours > 0:
                time_left = f"{hours}h {minutes}m remaining"
            else:
                time_left = f"{minutes}m remaining"
    else:
        time_left = "♾️ Permanent default active"

    await message.reply(
        f"🎟️ **Discount Status**\n\n"
        f"💰 Current Discount: **{percent}%**\n"
        f"🕒 Remaining Time: **{time_left}**\n"
        f"🏷️ Default Discount: **{permanent}%**"
    )
