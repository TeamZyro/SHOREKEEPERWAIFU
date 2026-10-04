import re
import time
from html import escape
from cachetools import TTLCache

from telegram import (
    Update,
    User,
    InlineQuery,
    InlineQueryResultPhoto,
    InlineQueryResultVideo,
)
from telegram.ext import InlineQueryHandler, ContextTypes

from TEAMZYRO import app, application
from TEAMZYRO.unit.zyro_inline import *

all_characters_cache = TTLCache(maxsize=10000, ttl=36000)
user_collection_cache = TTLCache(maxsize=10000, ttl=60)


async def inlinequery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    inline_query = update.inline_query
    query = inline_query.query
    offset = int(inline_query.offset) if inline_query.offset else 0

    if query.startswith("collection."):
        user_id, *search_terms = (
            query.split(" ")[0].split(".")[1],
            " ".join(query.split(" ")[1:]),
        )
        if user_id.isdigit():
            user = user_collection_cache.get(user_id) or await get_user_collection(user_id)
            if user:
                user_collection_cache[user_id] = user
                all_characters = list(
                    {
                        char["id"]: char
                        for char in user["characters"]
                        if "id" in char
                    }.values()
                )
                if search_terms:
                    regex = re.compile(" ".join(search_terms), re.IGNORECASE)
                    all_characters = [
                        char
                        for char in all_characters
                        if regex.search(char.get("name", ""))
                        or regex.search(char.get("anime", ""))
                    ]
            else:
                all_characters = []
        else:
            all_characters = []
    else:
        user = None
        if query:
            all_characters = await search_characters(query)
        else:
            all_characters = (
                all_characters_cache.get("all_characters")
                or await get_all_characters()
            )
            all_characters_cache["all_characters"] = all_characters

    if ".AMV" in query:
        all_characters = [char for char in all_characters if "vid_url" in char]
    else:
        all_characters = [char for char in all_characters if "img_url" in char]

    characters = all_characters[offset : offset + 50]
    next_offset = str(offset + len(characters)) if len(characters) == 50 else ""

    results = []
    for character in characters:
        if user:
            user_character_count = sum(
                1
                for char in user["characters"]
                if "id" in char and char["id"] == character["id"]
            )
            caption = (
                f"<b>👤 Check out <a href='tg://user?id={user['id']}'>"
                f"{escape(user.get('first_name', 'User'))}</a>'s character:</b>\n\n"
                f"🌸 <b>{escape(str(character.get('name', 'Unknown')))} "
                f"(x{user_character_count})</b>\n"
                f"🏖️ From: <b>{escape(str(character.get('anime', 'Unknown')))}</b>\n"
                f"🔮 Rarity: <b>{escape(str(character.get('rarity', 'Unknown')))}</b>\n\n"
                f"🆔️ <b>{character.get('id', 'Unknown')}</b>\n\n"
            )
        else:
            caption = (
                "<b>Discover this amazing character:</b>\n\n"
                f"🌸 <b>{escape(str(character.get('name', 'Unknown')))}</b>\n"
                f"🏖️ From: <b>{escape(str(character.get('anime', 'Unknown')))}</b>\n"
                f"🔮 Rarity: <b>{escape(str(character.get('rarity', 'Unknown')))}</b>\n"
                f"🆔️ <b>{character.get('id', 'Unknown')}</b>\n\n"
            )

        result_id = f"{character.get('id', 'unknown')}_{time.time_ns()}"

        if "vid_url" in character:
            results.append(
                InlineQueryResultVideo(
                    id=result_id,
                    video_url=character["vid_url"],
                    mime_type="video/mp4",
                    thumbnail_url=character.get(
                        "thum_url", "https://envs.sh/6Y3.jpg"
                    ),
                    title=str(character.get("name", "Unknown")),
                    description=(
                        f"From: {character.get('anime', 'Unknown')} | "
                        f"Rarity: {character.get('rarity', 'Unknown')}"
                    ),
                    caption=caption,
                    parse_mode="HTML",
                )
            )
        elif "img_url" in character:
            results.append(
                InlineQueryResultPhoto(
                    id=result_id,
                    photo_url=character["img_url"],
                    thumbnail_url=character["img_url"],
                    caption=caption,
                    parse_mode="HTML",
                )
            )

    await inline_query.answer(
        results=results,
        next_offset=next_offset,
        cache_time=5,
    )


# PTB Application owns the InlineQueryHandler.
application.add_handler(InlineQueryHandler(inlinequery, block=False))


@app.on_inline_query(group=100)
async def bridge_pyrogram_inline_to_ptb(client, inline_query):
    """
    Pyrogram remains the single Telegram update receiver.
    The actual inline handler is executed by python-telegram-bot Application.
    This avoids a second polling consumer for the same bot token.
    """
    from_user = inline_query.from_user
    ptb_user = User(
        id=from_user.id,
        first_name=from_user.first_name or "User",
        is_bot=bool(from_user.is_bot),
        last_name=from_user.last_name,
        username=from_user.username,
        language_code=from_user.language_code,
    )

    ptb_inline_query = InlineQuery(
        id=inline_query.id,
        from_user=ptb_user,
        query=inline_query.query or "",
        offset=inline_query.offset or "",
        chat_type=(getattr(inline_query.chat_type, "value", inline_query.chat_type) if inline_query.chat_type else None),
    )

    ptb_update = Update(
        update_id=abs(hash(inline_query.id)) % 2147483647,
        inline_query=ptb_inline_query,
    )
    ptb_update.set_bot(application.bot)

    await application.update_queue.put(ptb_update)
