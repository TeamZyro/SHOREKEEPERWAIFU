import os
import re
from pyrogram import filters
from TEAMZYRO import app as ZYRO, SUDO, OWNER_ID

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
