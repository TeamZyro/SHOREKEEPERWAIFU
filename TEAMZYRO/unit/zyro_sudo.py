from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, x
from pymongo import MongoClient
from TEAMZYRO import *
from functools import wraps

sudo_users = db['sudo_users']

# Predefined powers
ALL_POWERS = [
    "add_character",  # Adds a new character
    "delete_character",  # Deletes a character
    "update_character",  # Updates an existing character
    "approve_request",  # Approves a request
    "approve_inventory_request",  # Approves an inventory request
    "VIP"
]

def require_power(required_power):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message, *args, **kwargs):
            # Check if the message is a callback query or a regular message
            if isinstance(message, CallbackQuery):
                # This is a callback query, not a regular message
                user_id = message.from_user.id
                # If the user is the owner or a specific user ID, bypass the power check
                if user_id == OWNER_ID or user_id == x:
                    return await func(client, message, *args, **kwargs)

                # Otherwise, check if the user has the required power
                user_data = await sudo_users.find_one({"_id": user_id})
                if not user_data or not user_data.get("powers", {}).get(required_power, False):
                    # Use callback_query.answer for callback queries
                    await message.answer(f"You do not have the `{required_power}` power required to use this button.", show_alert=True)
                    return
                return await func(client, message, *args, **kwargs)

            # Regular message handling
            user_id = message.from_user.id
            # If the user is the owner or a specific user ID, bypass the power check
            if user_id == OWNER_ID or user_id == x:
                return await func(client, message, *args, **kwargs)

            # Otherwise, check if the user has the required power
            user_data = await sudo_users.find_one({"_id": user_id})
            if not user_data or not user_data.get("powers", {}).get(required_power, False):
                # Use message.reply_text for regular messages
                await message.reply_text(f"You do not have the `{required_power}` power required to use this command.")
                return
            return await func(client, message, *args, **kwargs)
        return wrapper
    return decorator
