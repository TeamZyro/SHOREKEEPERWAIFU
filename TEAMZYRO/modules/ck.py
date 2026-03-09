import asyncio
import aiohttp
from pyrogram import filters
from pyrogram.errors import FloodWait
from TEAMZYRO import app as ZYRO, collection


@ZYRO.on_message(filters.command(["addcheckimg"]))
async def addcheckimg_command(client, message):
    if message.from_user.id != 7018103039:
        return await message.reply_text("You do not have permission to use this command.")

    status_msg = await message.reply_text("Starting image check... This may take a while.")
    
    broken_chars = []
    total = await collection.count_documents({})
    checked = 0
    broken_count = 0
    
    cursor = collection.find({})
    
    async with aiohttp.ClientSession() as session:
        async for char in cursor:
            checked += 1
            img_url = char.get("img_url")
            char_id = char.get("id", "Unknown")
            name = char.get("name", "Unknown")
            anime = char.get("anime", "Unknown")
            rarity = char.get("rarity", "Unknown")
            
            is_broken = False

            if not img_url:
                is_broken = True
            else:
                try:
                    async with session.get(img_url, timeout=10) as response:
                        # Consider OK status or redirects OK
                        if response.status not in [200, 301, 302]:
                            is_broken = True
                except Exception:
                    is_broken = True

            if is_broken:
                broken_count += 1
                broken_chars.append(char)
                
                info_text = (
                    f"**⚠️ Broken Image Detected**\n"
                    f"**ID:** `{char_id}`\n"
                    f"**Name:** {name}\n"
                    f"**Anime:** {anime}\n"
                    f"**Rarity:** {rarity}\n"
                    f"**Image URL:** {img_url if img_url else 'None'}"
                )
                try:
                    await message.reply_text(info_text, disable_web_page_preview=True)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await message.reply_text(info_text, disable_web_page_preview=True)
                except Exception as e:
                    pass

            if checked % 50 == 0:
                try:
                    await status_msg.edit_text(f"Checking images... {checked}/{total}\nBroken found so far: {broken_count}")
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception:
                    pass
                
            await asyncio.sleep(0.05)

    try:
        await status_msg.edit_text(f"**✅ Image check complete!**\nTotal Checked: {checked}\nTotal Broken Images: {broken_count}")
    except:
        pass
