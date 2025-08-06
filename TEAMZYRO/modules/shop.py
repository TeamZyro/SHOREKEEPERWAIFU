import urllib.request
import uuid
import requests
import random
import html
import logging
from pymongo import ReturnDocument
from typing import List
from bson import ObjectId
from datetime import datetime, timedelta
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from motor.motor_asyncio import AsyncIOMotorClient

from TEAMZYRO import *

shops_collection = db["shops"]

user_data = {}

async def get_user_data(user_id):
    return await user_collection.find_one({"id": user_id})

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

@app.on_message(filters.command(["shop", "hshopmenu", "hshop"]))
async def show_shop(client, message):
    user_id = message.from_user.id
    message_id = message.id

    characters_cursor = shops_collection.find()
    characters = await characters_cursor.to_list(length=None)

    if not characters:
        await message.reply("🌌 The Cosmic Bazaar is empty! No legendary heroes are available yet.")
        return

    current_index = 0
    character = characters[current_index]

    caption_message = (
        f"🌟 **Welcome to the Cosmic Bazaar!** 🌟\n\n"
        f"**Hero:** {character['name']}\n"
        f"**Realm:** {character['anime']}\n"
        f"**Legend Tier:** {character['rarity']}\n"
        f"**Cost:** {character['price']} Star Coins\n"
        f"**ID:** {character['id']}\n\n"
        f"✨ Summon this epic hero to join your cosmic collection! ✨"
    )

    keyboard = [
        [InlineKeyboardButton("Claim Hero!", callback_data=f"buy_{current_index}"),
         InlineKeyboardButton("Next Hero", callback_data="next")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_photo(
        photo=character['img_url'],
        caption=caption_message,
        reply_markup=reply_markup
    )

    user_data[user_id] = {"current_index": current_index, "shop_message_id": message_id}

@app.on_callback_query(filters.regex(r"^buy_\d+$"))
async def buy_character(client, callback_query):
    user_id = callback_query.from_user.id
    current_index = int(callback_query.data.split("_")[1])

    characters_cursor = shops_collection.find()
    characters = await characters_cursor.to_list(length=None)

    if current_index >= len(characters):
        await callback_query.answer("🚫 This hero has vanished from the Cosmic Bazaar!", show_alert=True)
        return

    character = characters[current_index]

    user = await user_collection.find_one({"id": user_id})
    if not user:
        await callback_query.answer("🚫 Traveler, you must register in the Cosmos to claim heroes!", show_alert=True)
        return

    price = character['price']
    current_balance = user.get("balance", 0)

    if current_balance < price:
        await callback_query.answer(
            f"🌠 You need {price - current_balance} more Star Coins to claim this hero!",
            show_alert=True
        )
        return

    new_balance = current_balance - price
    character_data = {
        "_id": ObjectId(),
        "img_url": character["img_url"],
        "name": character["name"],
        "anime": character["anime"],
        "rarity": character["rarity"],
        "id": character["id"]
    }

    user["characters"].append(character_data)
    await user_collection.update_one(
        {"id": user_id},
        {"$set": {"balance": new_balance, "characters": user["characters"]}}
    )

    await callback_query.answer("🎉 Hero claimed! Your new legend joins the Cosmos!")

@app.on_callback_query(filters.regex("^next$"))
async def next_item(client, callback_query):
    user_id = callback_query.from_user.id

    user_state = user_data.get(user_id, {})
    current_index = user_state.get("current_index", 0)

    characters_cursor = shops_collection.find()
    characters = await characters_cursor.to_list(length=None)

    if not characters:
        await callback_query.answer("🌌 No more heroes remain in the Cosmic Bazaar!", show_alert=True)
        return

    next_index = (current_index + 1) % len(characters)
    character = characters[next_index]

    caption_message = (
        f"🌟 **Discover the Cosmic Bazaar!** 🌟\n\n"
        f"**Hero:** {character['name']}\n"
        f"**Realm:** {character['anime']}\n"
        f"**Legend Tier:** {character['rarity']}\n"
        f"**Cost:** {character['price']} Star Coins\n"
        f"**ID:** {character['id']}\n\n"
        f"✨ Add this legendary hero to your cosmic collection! ✨"
    )

    keyboard = [
        [InlineKeyboardButton("Claim Hero!", callback_data=f"buy_{next_index}"),
         InlineKeyboardButton("Next Hero", callback_data="next")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await callback_query.message.edit_media(
        media=InputMediaPhoto(media=character['img_url'], caption=caption_message),
        reply_markup=reply_markup
    )

    user_data[user_id]["current_index"] = next_index
    await callback_query.answer()

@app.on_message(filters.command("addshop"))
@require_power("add_character")
async def add_to_shop(client, message):
    args = message.text.split()[1:]

    if len(args) != 2:
        await message.reply("🌌 Usage: /addshop <id> <price> to add a hero to the Cosmic Bazaar!")
        return

    character_id, price = args

    try:
        price = int(price)
    except ValueError:
        await message.reply("🚫 The price must be a valid number of Star Coins!")
        return

    character = await collection.find_one({"id": character_id})
    if not character:
        await message.reply("🚫 This hero doesn't exist in the Cosmos!")
        return

    character["price"] = price
    await shops_collection.insert_one(character)

    await message.reply(f"🎉 {character['name']} has been added to the Cosmic Bazaar for {price} Star Coins!")

@app.on_message(filters.command("removeshop"))
@require_power("remove_character")
async def remove_from_shop(client, message):
    args = message.text.split()[1:]

    if len(args) != 1:
        await message.reply("🌌 Usage: /removeshop <id> to remove a hero from the Cosmic Bazaar!")
        return

    character_id = args[0]

    character = await shops_collection.find_one({"id": character_id})
    if not character:
        await message.reply("🚫 This hero is not in the Cosmic Bazaar!")
        return

    await shops_collection.delete_one({"id": character_id})
    await message.reply(f"🌠 {character['name']} has been removed from the Cosmic Bazaar!")
