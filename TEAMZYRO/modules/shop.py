import random
import logging
import asyncio
from datetime import datetime, timedelta
from bson import ObjectId
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from motor.motor_asyncio import AsyncIOMotorClient
from TEAMZYRO import *

TEAMZYRO = 7078181502

# Global data
user_shop_state = {}

# Permanent default discount (12%)
DEFAULT_DISCOUNT = 12

# Rarity price map
RARITY_PRICE = {
    "⚪️ Common": 1000,
    "🟣 Rare": 5000,
    "🟡 Legendary": 15000,
    "🟢 Medium": 30000,
    "💮 Special Edition": 25000,
    "🔮 Limited Edition": 40000,
    "💸 Premium Edition": 30000,
    "🌤 Summer": 35000,
    "🎐 Celestial": 45000,
    "❄️ Winter": 20000,
    "💝 Valentine": 18000,
    "🎃 Halloween": 16000,
    "🎄 Christmas Special": 22000,
    "🪐 Omniversal": 80000,
    "🎭 Cosplay Master 🎭": 70000,
    "🧧 Events": 25000,
    "🍑 Echhi": 30000,
    "🎗️ AMV Edition": 27000,
    "🌟 Luminous": 50000,
}

async def get_active_discount():
    discount = await discounts_collection.find_one({})
    if discount and discount["expires_at"] > datetime.utcnow():
        return discount["percent"]
    return DEFAULT_DISCOUNT

def is_video(url):
    return any(url.lower().endswith(ext) for ext in [".mp4", ".mov", ".webm"])

# /discount <percent> <duration>
@app.on_message(filters.command("discount"))
async def set_discount(client, message):
    if message.from_user.id not in TEAMZYRO:
        await message.reply("🚫 Only owners can set discounts.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.reply("Usage: /discount <percent> <duration>\nExample: /discount 30 1d or /discount 25 12h")
        return

    try:
        percent = int(args[1])
    except ValueError:
        return await message.reply("❌ Invalid percent value!")

    duration = args[2].lower()
    if duration.endswith("h"):
        hours = int(duration[:-1])
        expires = datetime.utcnow() + timedelta(hours=hours)
    elif duration.endswith("d"):
        days = int(duration[:-1])
        expires = datetime.utcnow() + timedelta(days=days)
    else:
        return await message.reply("❌ Duration must end with 'h' or 'd' (e.g. 2h, 1d).")

    await discounts_collection.delete_many({})
    await discounts_collection.insert_one({"percent": percent, "expires_at": expires})

    await message.reply(f"✅ Discount of {percent}% set for {duration} successfully!")

# /shop
@app.on_message(filters.command(["shop", "hshop", "hshopmenu"]))
async def shop_menu(client, message):
    keyboard = [[InlineKeyboardButton(r, callback_data=f"rarity_{r}")] for r in RARITY_PRICE.keys()]
    await message.reply("🌟 **Choose a rarity to browse the Bazaar!**", reply_markup=InlineKeyboardMarkup(keyboard))

# Rarity selection
@app.on_callback_query(filters.regex(r"^rarity_"))
async def show_rarity_list(client, callback_query):
    rarity = callback_query.data.split("_", 1)[1]
    user_id = callback_query.from_user.id

    characters_cursor = collection.find({"rarity": rarity})
    characters = await characters_cursor.to_list(length=None)
    if not characters:
        return await callback_query.answer("No characters found in this rarity!", show_alert=True)

    random.shuffle(characters)
    user_shop_state[user_id] = {
        "rarity": rarity,
        "index": 0,
        "characters": characters[:5]
    }

    await show_character(client, callback_query.message, user_id)

async def show_character(client, msg, user_id):
    data = user_shop_state[user_id]
    chars = data["characters"]
    index = data["index"]
    char = chars[index]

    price = RARITY_PRICE.get(char["rarity"], 1000)
    discount = await get_active_discount()
    discounted_price = int(price * (100 - discount) / 100)

    caption = (
        f"🌌 **{char['name']}**\n"
        f"🏯 **Realm:** {char['anime']}\n"
        f"⭐ **Rarity:** {char['rarity']}\n"
        f"💰 **Price:** {discounted_price} Star Coins ({discount}% off!)\n"
        f"🆔 ID: `{char['id']}`"
    )

    keyboard = [
        [
            InlineKeyboardButton("⬅️ Prev", callback_data="prev_char"),
            InlineKeyboardButton("🪄 Claim", callback_data=f"claim_{index}"),
            InlineKeyboardButton("➡️ Next", callback_data="next_char"),
        ],
        [InlineKeyboardButton("🔄 Refresh (5000💫)", callback_data="refresh_chars")]
    ]

    media_type = "video" if is_video(char["img_url"]) else "photo"
    markup = InlineKeyboardMarkup(keyboard)

    try:
        if media_type == "photo":
            await msg.edit_media(
                InputMediaPhoto(media=char["img_url"], caption=caption, parse_mode="markdown"),
                reply_markup=markup
            )
        else:
            await msg.edit_media(
                InputMediaVideo(media=char["img_url"], caption=caption, parse_mode="markdown"),
                reply_markup=markup
            )

    except Exception as e:
        # If editing fails (like first message), send new one
        if media_type == "photo":
            await msg.reply_photo(photo=char["img_url"], caption=caption, reply_markup=markup)
        else:
            await msg.reply_video(video=char["img_url"], caption=caption, reply_markup=markup)

@app.on_callback_query(filters.regex("^next_char$"))
async def next_character(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in user_shop_state:
        return await callback_query.answer("Start from /shop again!", show_alert=True)

    state = user_shop_state[user_id]
    if state["index"] >= len(state["characters"]) - 1:
        return await callback_query.answer("No more heroes in this batch!", show_alert=True)

    state["index"] += 1
    await show_character(client, callback_query.message, user_id)
    await callback_query.answer()

@app.on_callback_query(filters.regex("^prev_char$"))
async def prev_character(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in user_shop_state:
        return await callback_query.answer("Start from /shop again!", show_alert=True)

    state = user_shop_state[user_id]
    if state["index"] <= 0:
        return await callback_query.answer("Already at first hero!", show_alert=True)

    state["index"] -= 1
    await show_character(client, callback_query.message, user_id)
    await callback_query.answer()


@app.on_callback_query(filters.regex("^refresh_chars$"))
async def refresh_characters(client, callback_query):
    user_id = callback_query.from_user.id
    user = await user_collection.find_one({"id": user_id})
    if not user:
        return await callback_query.answer("Register first to use the shop!", show_alert=True)

    balance = user.get("balance", 0)
    if balance < 5000:
        return await callback_query.answer("Not enough coins to refresh (Need 5000)!", show_alert=True)

    await user_collection.update_one({"id": user_id}, {"$inc": {"balance": -5000}})

    rarity = user_shop_state[user_id]["rarity"]
    chars_cursor = collection.find({"rarity": rarity})
    all_chars = await chars_cursor.to_list(length=None)
    random.shuffle(all_chars)
    user_shop_state[user_id]["characters"] = all_chars[:5]
    user_shop_state[user_id]["index"] = 0

    await show_character(client, callback_query.message, user_id)
    await callback_query.answer("✨ Refreshed heroes!", show_alert=True)

@app.on_callback_query(filters.regex(r"^claim_\d+$"))
async def claim_character(client, callback_query):
    user_id = callback_query.from_user.id
    index = int(callback_query.data.split("_")[1])
    state = user_shop_state.get(user_id)
    if not state:
        return await callback_query.answer("Please open the shop again!", show_alert=True)

    char = state["characters"][index]
    user = await user_collection.find_one({"id": user_id})
    if not user:
        return await callback_query.answer("You must register first!", show_alert=True)

    price = RARITY_PRICE.get(char["rarity"], 1000)
    discount = await get_active_discount()
    discounted_price = int(price * (100 - discount) / 100)
    if user.get("balance", 0) < discounted_price:
        return await callback_query.answer("Not enough Star Coins!", show_alert=True)

    await user_collection.update_one(
        {"id": user_id},
        {
            "$inc": {"balance": -discounted_price},
            "$push": {"characters": {
                "_id": ObjectId(),
                "img_url": char["img_url"],
                "name": char["name"],
                "anime": char["anime"],
                "rarity": char["rarity"],
                "id": char["id"]
            }}
        }
    )
    await callback_query.answer(f"🎉 You claimed {char['name']}!", show_alert=True)

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
