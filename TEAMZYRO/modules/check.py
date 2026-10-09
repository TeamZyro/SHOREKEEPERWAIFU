# TEAMZYRO/commands/check.py
from TEAMZYRO import app, collection as character_collection, user_collection, db
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from io import BytesIO
from bson import ObjectId
from html import escape

custom_art_collection = db["custom_characters"]
custom_art_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="custom_art_images")

@app.on_message(filters.command("check"))
async def check_character(client, message):
    args = message.command
    if len(args) < 2:
        await message.reply_text("Please provide a Character ID: `/check <character_id>`")
        return

    character_id = str(args[1])
    character = await character_collection.find_one({"id": character_id})
    custom_art = None

    if not character:
        custom_art = await custom_art_collection.find_one({
            "character_id": character_id,
            "status": "approved",
        })
        if custom_art:
            character = {
                "id": custom_art["character_id"],
                "name": custom_art.get("name", "Unknown"),
                "anime": custom_art.get("anime", "Unknown Anime"),
                "rarity": "🎨 Customise",
                "creator_id": custom_art.get("creator_id"),
                "creator_name": custom_art.get("creator_name", "Creator"),
            }

    if not character:
        await message.reply_text("Character not found.")
        return

    creator_id = character.get("creator_id")
    creator_name = escape(str(character.get("creator_name", "Creator")))
    creator_line = ""
    if creator_id:
        creator_line = (
            f"\n👤 Creator: <a href='tg://user?id={creator_id}'>"
            f"{creator_name}</a>"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Who Have It", callback_data=f"whohaveit_{character_id}")]
    ])
    text = (
        f"🌟 <b>Character Info</b>\n"
        f"🆔 ID: <code>{escape(character_id)}</code>\n"
        f"📛 Name: {escape(str(character.get('name', 'Unknown')))}\n"
        f"📺 Anime: {escape(str(character.get('anime', 'Unknown Anime')))}\n"
        f"💎 Rarity: {escape(str(character.get('rarity', 'Unknown')))}"
        f"{creator_line}"
    )

    if custom_art:
        try:
            stream = await custom_art_bucket.open_download_stream(ObjectId(custom_art["image_file_id"]))
            photo = BytesIO(await stream.read())
            content_type = (stream.metadata or {}).get("content_type", "image/jpeg")
            photo.name = {
                "image/png": "custom-art.png",
                "image/webp": "custom-art.webp",
            }.get(content_type, "custom-art.jpg")
            await message.reply_photo(
                photo, caption=text, reply_markup=keyboard,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            await message.reply_text("Could not load this custom art image right now.")
        return

    if "vid_url" in character:
        await message.reply_video(
            character["vid_url"], caption=text, reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await message.reply_photo(
            character["img_url"], caption=text, reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )


@app.on_callback_query(filters.regex("^whohaveit_"))
async def who_have_it(client, callback_query):
    character_id = callback_query.data.split("_")[1]

    # Find users who own the character
    users = await user_collection.find({'characters.id': character_id}).to_list(length=10)

    if not users:
        await callback_query.answer("No one owns this character yet!", show_alert=True)
        return

    # Generate top 10 owners list with count
    owner_text = "**🏆 Top 10 Users Who Own This Character:**\n\n"
    for i, user in enumerate(users, 1):
        user_name = user.get('first_name', 'Unknown')  # Use 'Unknown' if missing
        count = sum(1 for char in user.get("characters", []) if char["id"] == character_id)
        owner_text += f"{i}. [{user_name}](tg://user?id={user['id']}) — x{count}\n"

    # Edit message to include the owner list and remove the button
    await callback_query.message.edit_caption(
        caption=f"{callback_query.message.caption}\n\n{owner_text}",
        reply_markup=None
    )

