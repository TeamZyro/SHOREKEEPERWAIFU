import os
import requests
from pyrogram import Client, filters
from pymongo import ReturnDocument
from gridfs import GridFS
from TEAMZYRO import application, CHARA_CHANNEL_ID, SUPPORT_CHAT, OWNER_ID, collection, user_collection, db, SUDO, rarity_map, ZYRO, require_power

# Define the wrong format message and rarity map
WRONG_FORMAT_TEXT = """Wrong ❌ format...  eg. /upload reply to photo muzan-kibutsuji Demon-slayer 3

format:- /upload reply character-name anime-name rarity-number

use rarity number accordingly rarity Map

rarity_map = {
    1: "⚪️ Common",
    2: "🟣 Rare",
    3: "🟡 Legendary",      
    4: "🟢 Medium",  
    5: "💮 Special Edition", 
    6: "🔮 Limited Edition", 
    7: "💸 Premium Edition", 
    8: "🌤 Summer",
    9: "🎐 Celestial", 
    10: "❄️ Winter", 
    11: "💝 Valentine", 
    12: "🎃 Halloween", 
    13: "🎄 Christmas Special", 
    14: "🪐 Omniversal", 
    15: "🎭 Cosplay Master 🎭",
    16: "🧧 Events",
    17: "🍑 Echhi",
    18: "🎗️ AMV Edition",
    19: "🌟 Luminous",
    20: "🌧 Rainy",
    22: "🍭 Winter event",
}
"""

async def _used_character_ids():
    ids = set()
    async for doc in collection.find({}, {"id": 1}):
        try:
            ids.add(int(doc["id"]))
        except (KeyError, TypeError, ValueError):
            continue

    # Approved creator-shop characters reserve IDs too, but stay in a separate
    # collection so the normal character drop system never spawns them.
    custom_art_collection = db["custom_characters"]
    async for doc in custom_art_collection.find({"character_id": {"$exists": True}}, {"character_id": 1}):
        try:
            ids.add(int(doc["character_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return ids


async def find():
    ids = await _used_character_ids()
    candidate = 1
    while candidate in ids:
        candidate += 1
    return str(candidate).zfill(2)


async def find_available_id():
    return await find()


def upload_to_catbox(file_path=None, file_url=None, expires=None, secret=None):
    """Upload a local file to Catbox with authenticated-upload support and retries."""
    if not file_path or not os.path.isfile(file_path):
        raise Exception(f"Invalid file path: {file_path}")

    url = "https://catbox.moe/user/api.php"
    user_hash = os.getenv("CATBOX_USER_HASH", "").strip()
    filename = os.path.basename(file_path)

    data = {"reqtype": "fileupload"}
    if user_hash:
        data["userhash"] = user_hash

    last_error = "Unknown Catbox error"
    for attempt in range(2):
        try:
            with open(file_path, "rb") as file:
                response = requests.post(
                    url,
                    data=data,
                    files={
                        "fileToUpload": (
                            filename,
                            file,
                            "application/octet-stream",
                        )
                    },
                    headers={"User-Agent": "SHOREKEEPERWAIFU/1.0"},
                    timeout=120,
                )

            result = response.text.strip()
            if response.status_code == 200 and result.startswith("https://"):
                return result

            last_error = result or f"HTTP {response.status_code}"
            if "invalid uploader" not in last_error.lower() and attempt == 0:
                break
        except requests.RequestException as exc:
            last_error = str(exc)

    raise Exception(f"Error uploading to Catbox: {last_error}")

def upload_to_telegraph(file_path: str) -> str:
    """Upload an image to Telegraph as a keyless image-host fallback."""
    if not file_path or not os.path.isfile(file_path):
        raise Exception(f"Invalid file path: {file_path}")

    url = "https://telegra.ph/upload"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as file:
        response = requests.post(
            url,
            files={"file": (filename, file, "application/octet-stream")},
            headers={"User-Agent": "SHOREKEEPERWAIFU/1.0"},
            timeout=120,
        )

    if response.status_code != 200:
        raise Exception(f"HTTP Error: {response.status_code} | {response.text}")

    try:
        data = response.json()
        if isinstance(data, list) and data and data[0].get("src"):
            return "https://telegra.ph" + data[0]["src"]
    except ValueError:
        pass

    raise Exception(f"Invalid Telegraph response: {response.text}")


IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "7ff491f6f7076787ff4e5dab51b502a9")

def upload_to_imgbb(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise Exception(f"Invalid file path: {file_path}")
    url = "https://api.imgbb.com/1/upload"
    with open(file_path, "rb") as f:
        response = requests.post(
            url,
            data={"key": IMGBB_API_KEY},
            files={"image": f}
        )
    if response.status_code == 200:
        data = response.json()
        return data["data"]["url"]
    else:
        raise Exception(f"HTTP Error: {response.status_code} | {response.text}")


server_collection = db["user_upload_servers"]

async def get_user_server(user_id: int) -> str:
    doc = await server_collection.find_one({"user_id": user_id})
    if doc:
        return doc.get("server", "imgbb")
    return "imgbb"

async def set_user_server(user_id: int, server: str):
    await server_collection.update_one(
        {"user_id": user_id},
        {"$set": {"server": server}},
        upsert=True
    )


@ZYRO.on_message(filters.command(["find"]))
@require_power("add_character")
async def ul(client, message):
    available_id = await find()
    await message.reply_text(
                f"new id {available_id}"
            )


from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@ZYRO.on_message(filters.command("server"))
@require_power("add_character")
async def select_server(client, message):
    current_server = await get_user_server(message.from_user.id)
    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("ImgBB ✅" if current_server == "imgbb" else "ImgBB", callback_data="set_server_imgbb"),
            InlineKeyboardButton("Catbox ✅" if current_server == "catbox" else "Catbox", callback_data="set_server_catbox")
        ]]
    )
    await message.reply(f"Your current upload server is **{current_server.upper()}**.\nSelect upload server:", reply_markup=buttons)


@ZYRO.on_callback_query(filters.regex(r"^set_server_"))
@require_power("add_character")
async def server_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data
    if data == "set_server_imgbb":
        await set_user_server(user_id, "imgbb")
        buttons = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("ImgBB ✅", callback_data="set_server_imgbb"),
                InlineKeyboardButton("Catbox", callback_data="set_server_catbox")
            ]]
        )
        await callback_query.edit_message_text("Upload server set to ImgBB ✅", reply_markup=buttons)
        await callback_query.answer("Upload server set to ImgBB ✅", show_alert=True)
    elif data == "set_server_catbox":
        await set_user_server(user_id, "catbox")
        buttons = InlineKeyboardMarkup(
            [[
                InlineKeyboardButton("ImgBB", callback_data="set_server_imgbb"),
                InlineKeyboardButton("Catbox ✅", callback_data="set_server_catbox")
            ]]
        )
        await callback_query.edit_message_text("Upload server set to Catbox ✅", reply_markup=buttons)
        await callback_query.answer("Upload server set to Catbox ✅", show_alert=True)


import asyncio

upload_lock = asyncio.Lock()  # Lock for handling concurrent uploads

@ZYRO.on_message(filters.command(["gupload", "u", "upload"]))
@require_power("add_character")
async def ul_main(client, message):
    global upload_lock

    if upload_lock.locked():
        await message.reply_text("Another upload is in progress. Please wait until it is completed.")
        return

    async with upload_lock:  # Acquire lock
        reply = message.reply_to_message
        if reply and (reply.photo or reply.document or reply.video):
            args = message.text.split()
            if len(args) != 4:
                await client.send_message(chat_id=message.chat.id, text=WRONG_FORMAT_TEXT)
                return

            # Extract character details from the command arguments
            character_name = args[1].replace('-', ' ').title()
            anime = args[2].replace('-', ' ').title()
            rarity = int(args[3])

            # Validate rarity value
            if rarity not in rarity_map:
                await message.reply_text("Invalid rarity value. Please use a value between 1 and 16.")
                return

            rarity_text = rarity_map[rarity]
            available_id = await find_available_id()

            # Prepare character data
            character = {
                'name': character_name,
                'anime': anime,
                'rarity': rarity_text,
                'id': available_id
            }

            processing_message = await message.reply("<ᴘʀᴏᴄᴇꜱꜱɪɴɢ>....")
            path = await reply.download()
            try:
                # Upload image or video using user's selected server
                server = await get_user_server(message.from_user.id)
                
                # Check if it's a document/video and fallback to catbox if user has imgbb selected
                is_video = bool(reply.video)
                is_doc_non_image = False
                if reply.document:
                    mime = getattr(reply.document, "mime_type", "") or ""
                    if not mime.startswith("image/"):
                        is_doc_non_image = True

                if not is_video and not is_doc_non_image:
                    # Images: try the selected host first, then use the other
                    # image host and finally Telegraph. This prevents a Catbox
                    # uploader/IP rejection from breaking /gupload.
                    upload_errors = []

                    if server == "imgbb":
                        try:
                            file_url = upload_to_imgbb(path)
                        except Exception as e:
                            upload_errors.append(f"ImgBB: {e}")
                            try:
                                file_url = upload_to_catbox(path)
                            except Exception as e:
                                upload_errors.append(f"Catbox: {e}")
                                file_url = upload_to_telegraph(path)
                    else:
                        try:
                            file_url = upload_to_catbox(path)
                        except Exception as e:
                            upload_errors.append(f"Catbox: {e}")
                            try:
                                file_url = upload_to_imgbb(path)
                            except Exception as e:
                                upload_errors.append(f"ImgBB: {e}")
                                file_url = upload_to_telegraph(path)
                else:
                    # Videos still require a video-capable host; keep Catbox as
                    # the primary backend and expose the real error if rejected.
                    file_url = upload_to_catbox(path)

                # Update character with the image or video URL
                if reply.photo or reply.document:
                    character['img_url'] = file_url
                elif reply.video:
                    character['vid_url'] = file_url
                    # Download and upload thumbnail
                    thumbnail_path = await client.download_media(reply.video.thumbs[0].file_id)
                    try:
                        if server == "imgbb":
                            try:
                                thumbnail_url = upload_to_imgbb(thumbnail_path)
                            except Exception:
                                try:
                                    thumbnail_url = upload_to_catbox(thumbnail_path)
                                except Exception:
                                    thumbnail_url = upload_to_telegraph(thumbnail_path)
                        else:
                            try:
                                thumbnail_url = upload_to_catbox(thumbnail_path)
                            except Exception:
                                try:
                                    thumbnail_url = upload_to_imgbb(thumbnail_path)
                                except Exception:
                                    thumbnail_url = upload_to_telegraph(thumbnail_path)
                    finally:
                        try:
                            os.remove(thumbnail_path)
                        except OSError:
                            pass
                    character['thum_url'] = thumbnail_url

                # Send character details to the channel
                if reply.photo or reply.document:
                    await client.send_photo(
                        chat_id=CHARA_CHANNEL_ID,
                        photo=file_url,
                        caption=(
                            f"Character Name: {character_name}\n"
                            f"Anime Name: {anime}\n"
                            f"Rarity: {rarity_text}\n"
                            f"ID: {available_id}\n"
                            f"Added by [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
                        ),
                    )
                elif reply.video:
                    await client.send_video(
                        chat_id=CHARA_CHANNEL_ID,
                        video=file_url,
                        caption=(
                            f"Character Name: {character_name}\n"
                            f"Anime Name: {anime}\n"
                            f"Rarity: {rarity_text}\n"
                            f"ID: {available_id}\n"
                            f"Added by [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n"
                        ),
                    )

                # Insert character into the database
                await collection.insert_one(character)
                await message.reply_text(
                    f"➲ ᴀᴅᴅᴇᴅ ʙʏ» [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n"
                    f"➥ Character ID: {available_id}\n"
                    f"➥ Rarity: {rarity_text}"
                )
            except Exception as e:
                await message.reply_text(f"Character Upload Unsuccessful. Error: {str(e)}")
            finally:
                try:
                    os.remove(path)  # Clean up the downloaded file
                except:
                    pass
        else:
            await message.reply_text("Please reply to a photo, document, or video.")


