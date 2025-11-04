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

# 🌟 Default discount
GLOBAL_DISCOUNT = {"percent": 12, "expires_at": None, "permanent": 12}

user_shop_data = {}
refresh_cooldown = {}

# 🧮 Discount calculator
def get_discounted_price(base_price: int):
    discount = GLOBAL_DISCOUNT["percent"]
    return int(base_price - (base_price * discount / 100)) if discount > 0 else base_price


async def discount_watcher():
    """Auto reset discount when expired"""
    while True:
        if GLOBAL_DISCOUNT["expires_at"] and datetime.utcnow() > GLOBAL_DISCOUNT["expires_at"]:
            GLOBAL_DISCOUNT["percent"] = GLOBAL_DISCOUNT["permanent"]
            GLOBAL_DISCOUNT["expires_at"] = None
            print("🕒 Discount expired → reset to default")
        await asyncio.sleep(30)


# 🌌 Shop command
@app.on_message(filters.command(["shop"]))
async def shop_menu(client, message):
    user_id = message.from_user.id
    buttons = []

    for i in range(1, 20, 3):
        row = []
        for j in range(i, min(i + 3, 20)):
            rarity = RARITY_PRICES[j]
            price = get_discounted_price(rarity["price"])
            row.append(
                InlineKeyboardButton(
                    f"{rarity['name']} ({price}💰)", callback_data=f"rarity_{j}_{user_id}"
                )
            )
        buttons.append(row)

    discount = GLOBAL_DISCOUNT["percent"]
    banner = f"🎁 **{discount}% OFF** on all rarities!\n" if discount > 0 else ""
    await message.reply(
        f"{banner}🌌 **Welcome to the Cosmic Bazaar!**\n\nChoose your rarity to explore ↓",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


@app.on_callback_query(filters.regex(r"^rarity_(\d+)_(\d+)$"))
async def show_rarity_shop(client, cq):
    rarity_id, owner_id = map(int, cq.data.split("_")[1:])
    clicker = cq.from_user.id
    if clicker != owner_id:
        return await cq.answer("❌ Only the shop owner can use these buttons!", show_alert=True)

    rarity_name = RARITY_PRICES[rarity_id]["name"]
    characters = await collection.find({"rarity": rarity_name}).to_list(length=None)
    if not characters:
        return await cq.answer("🚫 No heroes found for this rarity!", show_alert=True)

    sample = random.sample(characters, min(5, len(characters)))
    user_shop_data[owner_id] = {"rarity": rarity_id, "characters": sample, "index": 0}
    await send_character_card(cq.message, owner_id, 0)
    await cq.answer()


async def send_character_card(message, user_id, index):
    data = user_shop_data[user_id]
    chars = data["characters"]
    index %= len(chars)
    character = chars[index]
    rarity_id = data["rarity"]
    price = get_discounted_price(RARITY_PRICES[rarity_id]["price"])

    caption = (
        f"🌟 **{character['name']}**\n"
        f"🏰 Realm: {character['anime']}\n"
        f"💎 Rarity: {character['rarity']}\n"
        f"💰 Price: {price} Star Coins\n"
        f"🆔 ID: {character['id']}\n\n✨ Add this hero to your collection!"
    )

    kb = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data=f"shop_prev_{user_id}"),
            InlineKeyboardButton("💫 Claim", callback_data=f"buyshop_{index}_{user_id}"),
            InlineKeyboardButton("➡️ Next", callback_data=f"shop_next_{user_id}"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh (5000💰)", callback_data=f"shop_refresh_{user_id}"),
            InlineKeyboardButton("🏠 Back", callback_data=f"shop_back_{user_id}"),
        ],
    ]

    try:
        await message.edit_media(
            InputMediaPhoto(character["img_url"], caption=caption),
            reply_markup=InlineKeyboardMarkup(kb),
        )
    except Exception:
        await message.reply_photo(character["img_url"], caption=caption, reply_markup=InlineKeyboardMarkup(kb))

    user_shop_data[user_id]["index"] = index


@app.on_callback_query(filters.regex(r"^shop_next_(\d+)$"))
async def shop_next(client, cq):
    owner_id = int(cq.data.split("_")[2])
    if cq.from_user.id != owner_id:
        return await cq.answer("❌ Not your shop!", show_alert=True)
    data = user_shop_data.get(owner_id)
    if not data:
        return await cq.answer("⚠️ Please open the shop again!", show_alert=True)
    await send_character_card(cq.message, owner_id, data["index"] + 1)
    await cq.answer()


@app.on_callback_query(filters.regex(r"^shop_prev_(\d+)$"))
async def shop_prev(client, cq):
    owner_id = int(cq.data.split("_")[2])
    if cq.from_user.id != owner_id:
        return await cq.answer("❌ Not your shop!", show_alert=True)
    data = user_shop_data.get(owner_id)
    if not data:
        return await cq.answer("⚠️ Please open the shop again!", show_alert=True)
    await send_character_card(cq.message, owner_id, data["index"] - 1)
    await cq.answer()


@app.on_callback_query(filters.regex(r"^shop_refresh_(\d+)$"))
async def shop_refresh(client, cq):
    owner_id = int(cq.data.split("_")[2])
    if cq.from_user.id != owner_id:
        return await cq.answer("❌ Not your shop!", show_alert=True)

    now = time.time()
    if now - refresh_cooldown.get(owner_id, 0) < 30:
        remain = int(30 - (now - refresh_cooldown[owner_id]))
        return await cq.answer(f"⏳ Wait {remain}s before refreshing!", show_alert=True)

    user = await user_collection.find_one({"id": owner_id})
    if not user:
        return await cq.answer("🚫 You are not registered!", show_alert=True)
    if user.get("balance", 0) < 5000:
        return await cq.answer("❌ Not enough coins to refresh!", show_alert=True)

    await cq.message.edit_caption("✨ Refreshing your shop...")
    await asyncio.sleep(2.5)

    await user_collection.update_one({"id": owner_id}, {"$inc": {"balance": -5000}})
    rarity_id = user_shop_data[owner_id]["rarity"]
    rarity_name = RARITY_PRICES[rarity_id]["name"]
    characters = await collection.find({"rarity": rarity_name}).to_list(length=None)
    sample = random.sample(characters, min(5, len(characters)))
    user_shop_data[owner_id] = {"rarity": rarity_id, "characters": sample, "index": 0}
    refresh_cooldown[owner_id] = now

    await send_character_card(cq.message, owner_id, 0)
    await cq.answer("🔄 Refreshed! 5000 coins deducted.", show_alert=True)


@app.on_callback_query(filters.regex(r"^shop_back_(\d+)$"))
async def shop_back(client, cq):
    owner_id = int(cq.data.split("_")[2])
    if cq.from_user.id != owner_id:
        return await cq.answer("❌ Not your shop!", show_alert=True)
    await shop_menu(client, cq.message)
    await cq.answer()


@app.on_callback_query(filters.regex(r"^buyshop_(\d+)_(\d+)$"))
async def buyshop(client, cq):
    index, owner_id = map(int, cq.data.split("_")[1:])
    if cq.from_user.id != owner_id:
        return await cq.answer("❌ Not your shop!", show_alert=True)

    user = await user_collection.find_one({"id": owner_id})
    if not user:
        return await cq.answer("🚫 You must register first!", show_alert=True)

    data = user_shop_data.get(owner_id)
    if not data:
        return await cq.answer("⚠️ Please open the shop again!", show_alert=True)

    rarity_id = data["rarity"]
    price = get_discounted_price(RARITY_PRICES[rarity_id]["price"])
    character = data["characters"][index]
    balance = user.get("balance", 0)
    if balance < price:
        return await cq.answer(f"💰 Need {price - balance} more coins!", show_alert=True)

    await user_collection.update_one(
        {"id": owner_id},
        {
            "$inc": {"balance": -price},
            "$push": {"characters": {
                "_id": ObjectId(),
                "img_url": character["img_url"],
                "name": character["name"],
                "anime": character["anime"],
                "rarity": character["rarity"],
                "id": character["id"],
            }},
        },
    )
    await cq.answer("🎉 Hero successfully claimed!", show_alert=True)


# ⚙️ OWNER ONLY: Set global discount
@app.on_message(filters.command("discount"))
async def set_discount(client, message):
    if message.from_user.id != TEAMZYRO:
        return await message.reply("🚫 Only the owner can set discounts!")

    args = message.text.split()
    if len(args) < 2:
        return await message.reply("⚙️ Usage: /discount <percent> [minutes|Xd]\nExample: /discount 40 1d")

    try:
        percent = int(args[1])
        if not (0 <= percent <= 100):
            raise ValueError
    except ValueError:
        return await message.reply("⚠️ Provide a valid percent (0–100).")

    duration = 60
    if len(args) == 3:
        t = args[2].lower()
        if t.endswith("d"):
            days = int(t[:-1])
            duration = days * 24 * 60
        else:
            duration = int(t)

    GLOBAL_DISCOUNT["percent"] = percent
    GLOBAL_DISCOUNT["expires_at"] = datetime.utcnow() + timedelta(minutes=duration)
    asyncio.create_task(discount_watcher())

    await message.reply(
        f"🎁 Discount set to **{percent}%** for **{duration} minutes**.\n"
        f"After expiry → reset to **{GLOBAL_DISCOUNT['permanent']}%**."
    )


@app.on_message(filters.command("discountstatus"))
async def discount_status(client, message):
    percent = GLOBAL_DISCOUNT["percent"]
    expires = GLOBAL_DISCOUNT["expires_at"]
    if expires:
        left = expires - datetime.utcnow()
        if left.total_seconds() > 0:
            m = int(left.total_seconds() // 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            time_left = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        else:
            time_left = "Expired"
    else:
        time_left = "♾️ Permanent"

    await message.reply(
        f"🎟️ **Discount Status**\n\n💰 Current: **{percent}%**\n🕒 Time left: **{time_left}**\n"
        f"🏷️ Default: **{GLOBAL_DISCOUNT['permanent']}%**"
    )
