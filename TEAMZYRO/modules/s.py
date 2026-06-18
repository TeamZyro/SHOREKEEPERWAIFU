import os
import re
import requests
import asyncio
from pyrogram import filters
from TEAMZYRO import app as ZYRO, SUDO, OWNER_ID, collection

UPLOAD_API = "https://api.imgbb.com/1/upload"
IMGBB_API_KEY = "597b4dafe768f0e8e6a03f4e1b8b5010"

def upload_to_imgbb(file_path: str) -> str:
    """Upload a local file to ImgBB and return the public URL."""
    with open(file_path, "rb") as f:
        response = requests.post(
            UPLOAD_API,
            data={"key": IMGBB_API_KEY},
            files={"image": f},
            timeout=60,
        )
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data["data"]["url"]
            
    raise Exception(f"ImgBB upload failed ({response.status_code}): {response.text}")

async def find_char(char_id: str):
    """Try multiple ID formats for character lookup."""
    char = await collection.find_one({"id": char_id})
    if char: return char
    
    padded = char_id.zfill(2)
    if padded != char_id:
        char = await collection.find_one({"id": padded})
        if char: return char
        
    try:
        char = await collection.find_one({"id": int(char_id)})
        if char: return char
    except ValueError:
        pass
    return None

@ZYRO.on_message(filters.command(["s"]))
async def get_msg_link_image(client, message):
    if message.from_user.id not in SUDO and message.from_user.id != OWNER_ID:
        return await message.reply_text("You do not have permission to use this command.")
        
    if len(message.command) < 2:
        return await message.reply_text("Usage: /s {link}")
    
    link = message.command[1]
    
    # Regex to extract chat ID and message ID
    # Patterns: 
    # https://t.me/c/12345678/123 (private)
    # https://t.me/username/123 (public)
    pattern = r"https?://t\.me/(?:c/)?([\w.-]+)/(\d+)"
    match = re.search(pattern, link)
    
    if not match:
        return await message.reply_text("Invalid Telegram message link.")
    
    chat_identifier = match.group(1)
    message_id = int(match.group(2))
    
    # Check if it's a private chat link (contains /c/)
    if "/c/" in link:
        try:
            # Private chat IDs in telegram links are usually positive, but Pyrogram needs -100 prefix
            chat_id = int("-100" + chat_identifier)
        except ValueError:
            chat_id = chat_identifier
    else:
        # Public chat username or numeric ID
        try:
            chat_id = int(chat_identifier)
        except ValueError:
            chat_id = chat_identifier
            
    status_msg = await message.reply_text("🔄 Processing link...")
    
    try:
        # Fetch the message
        msg = await client.get_messages(chat_id, message_id)
        
        if not msg or msg.empty:
            return await status_msg.edit_text("❌ Could not find the message. Make sure the bot is a member of the chat and has access to messages.")
            
        if msg.photo:
            await status_msg.edit_text("⏬ Downloading Image...")
            photo_path = await msg.download()
            
            await message.reply_photo(
                photo=photo_path,
                caption=f"✅ Image extracted from the link provided by {message.from_user.mention}"
            )
            await status_msg.delete()
            
            # Clean up
            if os.path.exists(photo_path):
                os.remove(photo_path)
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
            # Also handle images sent as documents
            await status_msg.edit_text("⏬ Downloading Image (Document)...")
            photo_path = await msg.download()
            
            await message.reply_photo(
                photo=photo_path,
                caption=f"✅ Image extracted from the link provided by {message.from_user.mention}"
            )
            await status_msg.delete()
            
            if os.path.exists(photo_path):
                os.remove(photo_path)
        else:
            await status_msg.edit_text("ℹ️ This message doesn't contain an image.")
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)}")

@ZYRO.on_message(filters.command(["xupdate"]))
async def xupdate_command(client, message):
    if message.from_user.id not in SUDO and message.from_user.id != OWNER_ID:
        return await message.reply_text("You do not have permission to use this command.")

    if len(message.command) < 3:
        return await message.reply_text("Usage: /xupdate {link} {character_id}")

    link = message.command[1]
    char_id = message.command[2]

    pattern = r"https?://t\.me/(?:c/)?([\w.-]+)/(\d+)"
    match = re.search(pattern, link)

    if not match:
        return await message.reply_text("Invalid Telegram message link.")

    chat_identifier = match.group(1)
    msg_id = int(match.group(2))

    if "/c/" in link:
        try:
            chat_id = int("-100" + chat_identifier)
        except ValueError:
            chat_id = chat_identifier
    else:
        try:
            chat_id = int(chat_identifier)
        except ValueError:
            chat_id = chat_identifier

    status_msg = await message.reply_text(f"⏳ Processing update for Character ID: `{char_id}`...")

    try:
        # 1. Fetch character from DB
        char = await find_char(char_id)
        if not char:
            return await status_msg.edit_text(f"❌ Character ID `{char_id}` not found in database.")

        stored_id = char.get("id")
        char_name = char.get("name", "Unknown")

        # 2. Fetch the message with image
        msg = await client.get_messages(chat_id, msg_id)
        if not msg or msg.empty:
            return await status_msg.edit_text("❌ Could not find the message link content.")

        path = None
        if msg.photo:
            await status_msg.edit_text("⏬ Downloading Image...")
            path = await msg.download()
        elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
            await status_msg.edit_text("⏬ Downloading Image (Doc)...")
            path = await msg.download()
        else:
            return await status_msg.edit_text("❌ The provided link does not contain an image.")

        # 3. Upload to ImgBB
        await status_msg.edit_text("📤 Uploading to ImgBB...")
        new_url = upload_to_imgbb(path)

        # 4. Update Database
        await status_msg.edit_text("💾 Updating Database...")
        update_result = await collection.update_one(
            {"id": stored_id},
            {"$set": {"img_url": new_url, "status": "working"}}
        )

        if update_result.modified_count > 0:
            await status_msg.edit_text(
                f"✅ **Update Successful!**\n\n"
                f"👤 **Name:** {char_name}\n"
                f"🆔 **ID:** `{stored_id}`\n"
                f"🔗 **New URL:** [Open Image]({new_url})",
                disable_web_page_preview=False
            )
        else:
            await status_msg.edit_text(f"⚠️ Character `{char_id}` found, but DB update failed (maybe same URL?).")

        # Cleanup
        if path and os.path.exists(path):
            os.remove(path)

    except Exception as e:
        await status_msg.edit_text(f"❌ Error encountered: {str(e)}")
