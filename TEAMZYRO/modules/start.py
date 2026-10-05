import os
import importlib.util
import random
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from TEAMZYRO import *
from TEAMZYRO.unit.zyro_help import HELP_DATA
from TEAMZYRO.unit.rich_ui import rich_button, rich_message  

# 🔹 Function to Calculate Uptime
START_TIME = time.time()

def get_uptime():
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

# 🔹 START_MEDIA (Fixed: Direct URLs inside code)
START_MEDIA = [
    "https://files.catbox.moe/zufhkk.mp4",
    "https://files.catbox.moe/zufhkk.mp4"
]

# 🔹 Function to Generate Private Start Message & Buttons
async def generate_start_message(client, message):
    bot_user = await client.get_me()
    bot_name = bot_user.first_name
    ping = round(time.time() - message.date.timestamp(), 2)
    uptime = get_uptime()
    
    caption = (
        f"🍃 𝖦𝗋𝖾𝖾𝗍𝗂𝗇𝗀𝗌, 𝖨'𝗆 <b>{bot_name}</b> 🫧\n\n"
        f"<blockquote>━━━━━━━▧▣▧━━━━━━━\n"
        f"⦾ <b>𝖶𝖧𝖤𝖱𝖤:</b> 𝖨 𝗌𝗉𝖺𝗐𝗇 𝗐𝖺𝗂𝖿𝗎𝗌 𝗂𝗇 𝗒𝗈𝗎𝗋 𝖼𝗁𝖺𝗍 𝖿𝗈𝗋 𝗎𝗌𝖾𝗋𝗌 𝗍𝗈 𝗀𝗋𝖺𝖻.\n"
        f"⦾ <b>𝖧𝖮𝖶 𝖳𝖮 𝖴𝖲𝖤:</b> 𝖠𝖽𝖽 𝗆𝖾 𝗍𝗈 𝗒𝗈𝗎𝗋 𝗀𝗋𝗈𝗎𝗉 𝖺𝗇𝖽 𝗎𝗌𝖾 /help 𝖿𝗈𝗋 𝖼𝗈𝗆𝗆𝖺𝗇𝖽𝗌.\n"
        f"━━━━━━━▧▣▧━━━━━━━\n"
        f"⚡ <b>𝖯𝖨𝖭𝖦:</b> {ping} ms\n"
        f"⏳ <b>𝖴𝖯𝖳𝖨𝖬𝖤:</b> {uptime}</blockquote>"
    )

    buttons = [
        [rich_button("Aᴅᴅ Tᴏ Yᴏᴜʀ Gʀᴏᴜᴘ", url=f"https://t.me/{bot_user.username}?startgroup=true", style="success")],
        [
            rich_button("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_CHAT, style="primary"),
            rich_button("Cʜᴀɴɴᴇʟ", url=UPDATE_CHAT, style="primary"),
        ],
        [rich_button("Hᴇʟᴘ", callback_data="open_help", style="primary")],
        [rich_button("Owner", url="https://t.me/xeno_kakarot", style="danger")],
    ]
    return caption, buttons

# 🔹 Function to Generate Group Start Message & Buttons
async def generate_group_start_message(client):
    bot_user = await client.get_me()
    caption = (
        f"🍃 𝖨'𝗆 <b>{bot_user.first_name}</b> 🫧\n\n"
        f"<blockquote>𝖨 𝗌𝗉𝖺𝗐𝗇 𝗐𝖺𝗂𝖿𝗎𝗌 𝗂𝗇 𝗒𝗈𝗎𝗋 𝗀𝗋𝗈𝗎𝗉 𝗐𝗂𝗍𝗁 𝗆𝖾𝗌𝗌𝖺𝗀𝖾 𝖼𝗈𝗎𝗇𝗍𝗌 𝖿𝗈𝗋 𝗉𝗅𝖺𝗒𝖾𝗋𝗌 𝗍𝗈 /guess.\n"
        f"𝖴𝗌𝖾 /help 𝖿𝗈ʀ ᴍᴏʀᴇ ɪɴғᴏ.</blockquote>"
    )
    buttons = [[
        rich_button("Aᴅᴅ Mᴇ", url=f"https://t.me/{bot_user.username}?startgroup=true", style="success"),
        rich_button("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_CHAT, style="primary"),
    ]]
    return caption, buttons

# 🔹 Send Media (Helper)
async def send_media_message(client, message, media, caption, buttons):
    """Send the start UI as one Rich Message with embedded media and Rich buttons."""
    safe_media = str(media).replace("&", "&amp;").replace('"', "&quot;")
    if media.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        media_html = f'<img src="{safe_media}"/>'
    else:
        media_html = f'<video src="{safe_media}"></video>'

    return await client.send_rich_message(
        chat_id=message.chat.id,
        rich_message=rich_message(
            media_html + caption,
            buttons=buttons,
        ),
    )

# 🔹 Private Start Command Handler
@app.on_message(filters.command("start") & filters.private)
async def start_private_command(client, message):
    existing_user = await user_collection.find_one({"id": message.from_user.id})
    
    if not existing_user:
        user_data = {
            "id": message.from_user.id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "start_time": time.time()
        }
        await user_collection.insert_one(user_data)

    caption, buttons = await generate_start_message(client, message)
    media = random.choice(START_MEDIA)

    await app.send_message(
        chat_id=GLOG,
        text=f"{message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ᴄʜᴇᴄᴋ <b>sᴜᴅᴏʟɪsᴛ</b>.\n\n<b>ᴜsᴇʀ ɪᴅ :</b> <code>{message.from_user.id}</code>\n<b>ᴜsᴇʀɴᴀᴍᴇ :</b> @{message.from_user.username}",
    )

    await send_media_message(client, message, media, caption, buttons)

# 🔹 Group Start Command Handler
@app.on_message(filters.command("start") & filters.group)
async def start_group_command(client, message):
    caption, buttons = await generate_group_start_message(client)
    media = random.choice(START_MEDIA)
    await send_media_message(message, media, caption, buttons)

# 🔹 Function to Find Help Modules
def find_help_modules():
    buttons = []
    for module_name, module_data in HELP_DATA.items():
        button_name = module_data.get("HELP_NAME", "Unknown")
        buttons.append(rich_button(button_name, callback_data=f"help_{module_name}", style="primary"))
    return [buttons[i : i + 3] for i in range(0, len(buttons), 3)]

# 🔹 Help Button Click Handler
@app.on_callback_query(filters.regex("^open_help$"))
async def show_help_menu(client, query: CallbackQuery):
    time.sleep(1)
    buttons = find_help_modules()
    buttons.append([rich_button("⬅ Back", callback_data="back_to_home", style="link")])

    text = (
        "⚙️ <b>𝖧𝖤𝖫𝖯 𝖬𝖤𝖭𝖴</b>\n\n"
        "<blockquote>ᴄʜᴏᴏsᴇ ᴛʜᴇ ᴄᴀᴛᴇɢᴏʀʏ ғᴏʀ ᴡʜɪᴄʜ ʏᴏᴜ ᴡᴀɴɴᴀ ɢᴇᴛ ʜᴇʟᴩ.\n\n"
        "ᴀʟʟ ᴄᴏᴍᴍᴀɴᴅs ᴄᴀɴ ʙᴇ ᴜsᴇᴅ ᴡɪᴛʜ : /</blockquote>"
    )

    try:
        await query.message.edit_text(
            rich_message=rich_message(text, buttons=buttons)
        )
    except Exception:
        await query.message.edit_text(rich_message=rich_message(text, buttons=buttons))

# 🔹 Individual Module Help Handler
@app.on_callback_query(filters.regex(r"^help_(.+)"))
async def show_help(client, query: CallbackQuery):
    time.sleep(1)
    module_name = query.data.split("_", 1)[1]
    try:
        module_data = HELP_DATA.get(module_name, {})
        help_text = module_data.get("HELP", "Is module ka koi help nahi hai.")
        buttons = [[rich_button("⬅ Back", callback_data="open_help", style="link")]]
        
        full_text = f"<b>{module_name.upper()} Help:</b>\n\n{help_text}"
        
        try:
            await query.message.edit_text(
                rich_message=rich_message(full_text, buttons=buttons)
            )
        except Exception:
            await query.message.edit_text(rich_message=rich_message(full_text, buttons=buttons))
    except Exception as e:
        await query.answer("Help load karne me error aayi!")

# 🔹 Back to Home
@app.on_callback_query(filters.regex("^back_to_home$"))
async def back_to_home(client, query: CallbackQuery):
    time.sleep(1)
    caption, buttons = await generate_start_message(client, query.message)
    try:
        await query.message.edit_text(
            rich_message=rich_message(caption, buttons=buttons)
        )
    except Exception:
        await query.message.edit_text(rich_message=rich_message(caption, buttons=buttons))
