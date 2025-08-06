import asyncio
from pyrogram import Client, filters, types as t
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from TEAMZYRO import ZYRO as bot
from TEAMZYRO import user_collection, collection, SUPPORT_CHAT_ID as chat, SUPPORT_CHAT

async def get_unique_characters(user_id, target_rarities):
    try:
        user_data = await user_collection.find_one({'id': user_id}, {'characters.id': 1})
        claimed_ids = [char['id'] for char in user_data.get('characters', [])] if user_data else []

        pipeline = [
            {'$match': {'rarity': {'$in': target_rarities}, 'id': {'$nin': claimed_ids}}},
            {'$sample': {'size': 1}}  # Randomly sample one character
        ]
        cursor = collection.aggregate(pipeline)
        characters = await cursor.to_list(length=None)
        return characters if characters else []
    except Exception as e:
        print(f"Error retrieving unique characters: {e}")
        return []

# Helper function to format time
@bot.on_message(filters.command(["valentine"]))
async def valentine(_, message: t.Message):
    try:
        user_id = message.from_user.id
        mention = message.from_user.mention

        if str(message.chat.id) != chat:
            join_button = InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Here", url=SUPPORT_CHAT)]
            ])
            return await message.reply_text(
                "🔔 ᴊᴏɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴛᴏ ᴄʟᴀɪᴍ ʏᴏᴜʀ ᴅᴀɪʟʏ ᴄʜᴀʀᴀᴄᴛᴇʀ",
                reply_markup=join_button
            )

        # Get current date
        today = datetime.utcnow().date()
        start_date = datetime(today.year, 2, 7).date()
        end_date = datetime(today.year, 2, 14).date()

        # Check if today's date is between Feb 7 and Feb 14
        if not (start_date <= today <= end_date):
            return await message.reply_text("❌ *You can only claim this between 7th and 14th February!*")

        # Fetch user data from database
        user_data = await user_collection.find_one({'id': user_id})
        if not user_data:
            user_data = {
                'id': user_id,
                'username': message.from_user.username,
                'characters': [],
                'last_valentine_reward': None
            }
            await user_collection.insert_one(user_data)

        last_claimed_date = user_data.get('last_valentine_reward')
        if last_claimed_date:
            last_claimed_date = last_claimed_date.replace(tzinfo=None)
            if last_claimed_date.year == today.year:
                return await message.reply_text("❌ *You have already claimed your Valentine character this year!*")

        # Fetch a unique Valentine character
        valentine_characters = await get_unique_characters(user_id, target_rarities=['💖 Valentine'])
        if not valentine_characters:
            return await message.reply_text("❌ *No Valentine characters found!*")

        # Update user record
        await user_collection.update_one(
            {'id': user_id},
            {
                '$push': {'characters': {'$each': valentine_characters}},
                '$set': {'last_valentine_reward': datetime.utcnow()}
            }
        )

        # Send character images and info
        for character in valentine_characters:
            await message.reply_photo(
                photo=character['img_url'],
                caption=(
                    f"💖 **Happy Valentine's Day!** {mention}\n\n"
                    f"🌟 **Name**: `{character['name']}`  \n"
                    f"💖 **Rarity**: `{character['rarity']}`  \n"
                    f"📺 **Anime**: `{character['anime']}`  \n"
                    f"🆔 **ID**: `{character['id']}`  \n\n"
                    f"💕 **Come back next Valentine's season for another special character!** 💕"
                )
            )

    except Exception as e:
        print(f"Error in valentine command: {e}")
        await message.reply_text("❌ *An unexpected error occurred.*")
