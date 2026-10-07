from TEAMZYRO import *
from telegram import Update
from telegram.ext import CallbackContext, MessageHandler, filters
from pyrogram import filters as pyro_filters
import asyncio
import time


async def message_counter(update: Update, context: CallbackContext) -> None:
    if not update.effective_chat or not update.effective_user:
        return

    chat_id = str(update.effective_chat.id)
    user_id = update.effective_user.id
    current_time = time.time()

    existing_group = await group_user_totals_collection.find_one(
        {"group_id": chat_id}
    )
    if not existing_group:
        await group_user_totals_collection.update_one(
            {"group_id": chat_id},
            {"$set": {"group_id": chat_id, "ctime": 80}},
            upsert=True,
        )
        ctime = 80
    else:
        ctime = existing_group.get("ctime", 80)

    if chat_id not in locks:
        locks[chat_id] = asyncio.Lock()
    lock = locks[chat_id]

    async with lock:
        if user_id in user_cooldowns:
            cooldown_end = user_cooldowns[user_id]
            if current_time < cooldown_end:
                return
            del user_cooldowns[user_id]

        if chat_id in last_user and last_user[chat_id]["user_id"] == user_id:
            last_user[chat_id]["count"] += 1

            if last_user[chat_id]["count"] >= 10:
                if (
                    user_id not in warned_users
                    or current_time - warned_users[user_id] >= 600
                ):
                    cooldown_end = current_time + 600
                    user_cooldowns[user_id] = cooldown_end
                    warned_users[user_id] = current_time

                    await update.message.reply_text(
                        f"⚠️ Don't Spam {update.effective_user.first_name}...\n"
                        "Your Messages Will be ignored for 10 Minutes..."
                    )
                return
        else:
            last_user[chat_id] = {"user_id": user_id, "count": 1}

        normal_message_counts[chat_id] = (
            normal_message_counts.get(chat_id, 0) + 1
        )

        if normal_message_counts[chat_id] % ctime == 0:
            await send_image(update, context)
            normal_message_counts[chat_id] = 0


# PTB remains responsible for the message-counter logic.
ptb_message_handler = MessageHandler(
    ~filters.COMMAND,
    message_counter,
    block=False,
)
application.add_handler(ptb_message_handler)


def _pyrogram_message_to_update(message):
    """Build the minimal PTB Update needed by message_counter."""
    chat = message.chat
    user = message.from_user

    if not chat or not user:
        return None

    chat_data = {
        "id": chat.id,
        "type": str(chat.type),
    }

    if getattr(chat, "title", None):
        chat_data["title"] = chat.title
    if getattr(chat, "username", None):
        chat_data["username"] = chat.username

    user_data = {
        "id": user.id,
        "is_bot": bool(getattr(user, "is_bot", False)),
        "first_name": getattr(user, "first_name", None) or "User",
    }

    if getattr(user, "last_name", None):
        user_data["last_name"] = user.last_name
    if getattr(user, "username", None):
        user_data["username"] = user.username

    message_data = {
        "message_id": message.id,
        "date": int(message.date.timestamp()) if message.date else int(time.time()),
        "chat": chat_data,
        "from": user_data,
    }

    if getattr(message, "text", None):
        message_data["text"] = message.text
    elif getattr(message, "caption", None):
        message_data["caption"] = message.caption

    return Update.de_json(
        {
            "update_id": int(time.time() * 1000000) % 2147483647,
            "message": message_data,
        },
        application.bot,
    )


@app.on_message(pyro_filters.all)
async def _forward_pyrogram_message_to_ptb(client, message):
    """Pyrogram receives Telegram updates; PTB processes this module's handler."""
    if getattr(message, "from_user", None) is None:
        return

    # Keep the original non-command messages only behavior.
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    if text.startswith("/"):
        return

    update = _pyrogram_message_to_update(message)
    if update is None:
        return

    await application.process_update(update)
