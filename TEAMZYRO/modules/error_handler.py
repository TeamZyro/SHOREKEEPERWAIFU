import logging
import re
import traceback

from telegram import Update
from telegram.ext import ContextTypes

from TEAMZYRO import OWNER_ID, TOKEN, app

LOGGER = logging.getLogger("TEAMZYRO.error_handler")

MAX_MESSAGE_LENGTH = 3900


def _command_from_update(update) -> str:
    if update is None:
        return "UNKNOWN"

    message = getattr(update, "message", None) or getattr(update, "edited_message", None)
    if message:
        raw = getattr(message, "text", None) or getattr(message, "caption", None) or ""
        match = re.match(r"^/([A-Za-z0-9_]+)", raw.strip())
        if match:
            return "/" + match.group(1)
        if raw:
            return "MESSAGE"

    callback = getattr(update, "callback_query", None)
    if callback:
        return "CALLBACK: " + str(getattr(callback, "data", "") or "NO_DATA")[:120]

    inline_query = getattr(update, "inline_query", None)
    if inline_query:
        return "INLINE: " + str(getattr(inline_query, "query", "") or "<empty>")[:120]

    return type(update).__name__.upper()


def _pyrogram_command(update) -> str:
    if update is None:
        return "UNKNOWN"

    raw = getattr(update, "text", None) or getattr(update, "caption", None) or ""
    match = re.match(r"^/([A-Za-z0-9_]+)", raw.strip())
    if match:
        return "/" + match.group(1)

    if getattr(update, "data", None) is not None:
        return "CALLBACK: " + str(update.data)[:120]

    if getattr(update, "query", None) is not None:
        return "INLINE: " + str(update.query)[:120]

    return type(update).__name__.upper()


def _user_chat_info(update) -> str:
    user = getattr(update, "from_user", None)
    chat = getattr(update, "chat", None)

    user_id = getattr(user, "id", "unknown")
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None)

    chat_id = getattr(chat, "id", None)
    chat_type = getattr(chat, "type", None)

    return (
        f"User: {first_name or 'Unknown'}"
        f"{f' (@{username})' if username else ''} | ID: {user_id}\n"
        f"Chat: {chat_id or 'N/A'} | Type: {chat_type or 'N/A'}"
    )


def _redact(text: str) -> str:
    # Never send the bot token to the owner log chat.
    if TOKEN:
        text = text.replace(TOKEN, "[BOT_TOKEN_REDACTED]")
    return re.sub(
        r"(bot\d+:[A-Za-z0-9_-]+)",
        "[BOT_TOKEN_REDACTED]",
        text,
        flags=re.IGNORECASE,
    )


def _chunks(text: str):
    return [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)] or [""]


async def _send_report(sender, report: str):
    try:
        for chunk in _chunks(_redact(report)):
            await sender(chat_id=OWNER_ID, text=chunk)
    except Exception:
        # Error reporting must never create another unhandled exception.
        LOGGER.exception("Failed to send error report to OWNER_ID")


def _build_pyrogram_report(error: Exception, update) -> str:
    command = _pyrogram_command(update)
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    return (
        "🚨 BOT ERROR\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Command/Action: {command}\n"
        f"{_user_chat_info(update)}\n"
        f"Error Type: {type(error).__name__}\n"
        f"Error: {error}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "TRACEBACK:\n"
        f"{traceback_text}"
    )


def _build_ptb_report(error: Exception, update) -> str:
    command = _command_from_update(update)
    traceback_text = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    return (
        "🚨 PTB BOT ERROR\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Command/Action: {command}\n"
        f"Update: {type(update).__name__ if update else 'UNKNOWN'}\n"
        f"Error Type: {type(error).__name__}\n"
        f"Error: {error}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "TRACEBACK:\n"
        f"{traceback_text}"
    )


@app.on_error()
async def global_pyrogram_error(client, error: Exception, update_handler, update, users, chats):
    """Report unexpected Pyrogram handler errors to the owner.

    Kurigram calls ErrorHandler callbacks with six arguments:
    client, exception, failed handler, raw update, users and chats.
    """
    report = _build_pyrogram_report(error, update)
    report = f"Failed Handler: {type(update_handler).__name__}\n" + report
    await _send_report(client.send_message, report)


async def global_ptb_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report unexpected python-telegram-bot errors to the owner."""
    error = context.error
    if error is None:
        return

    report = _build_ptb_report(error, update)
    await _send_report(context.bot.send_message, report)


try:
    from TEAMZYRO import application

    application.add_error_handler(global_ptb_error)
except Exception:
    LOGGER.exception("Failed to register PTB global error handler")
