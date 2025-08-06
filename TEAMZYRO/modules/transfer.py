from pyrogram import Client, filters
from pyrogram.types import Message
from TEAMZYRO import app as Client, user_collection, require_power


@Client.on_message(filters.command("transfer"))
@require_power("VIP")
async def transfer_collection(client: Client, message: Message):
    try:
        # Get the user ID and owner ID from command arguments
        args = message.command[1:]  # Skip the command itself
        if len(args) != 2:
            await message.reply_text('Incorrect format. Please use: /transfer user_id owner_id')
            return

        user_id = int(args[0])
        owner_id = int(args[1])

        # Check if the user exists
        user = await user_collection.find_one({'id': user_id})
        if not user:
            await message.reply_text('User not found.')
            return

        # Check if the owner exists
        owner = await user_collection.find_one({'id': owner_id})
        if not owner:
            await message.reply_text('Owner not found.')
            return

        # Get the user's and owner's character collections
        user_characters = user.get('characters', [])
        owner_characters = owner.get('characters', [])

        if user_characters:
            # Transfer characters from user to owner
            await user_collection.update_one(
                {'id': owner_id},
                {'$push': {'characters': {'$each': user_characters}}}
            )

            # Clear the user's character collection after transfer
            await user_collection.update_one(
                {'id': user_id},
                {'$set': {'characters': []}}
            )

            await message.reply_text(
                f"Successfully transferred {len(user_characters)} characters from user with ID {user_id} to owner with ID {owner_id}."
            )
        elif owner_characters:
            # If the user has no characters, transfer from owner back to user
            await user_collection.update_one(
                {'id': user_id},
                {'$push': {'characters': {'$each': owner_characters}}}
            )

            # Clear the owner's character collection after transfer
            await user_collection.update_one(
                {'id': owner_id},
                {'$set': {'characters': []}}
            )

            await message.reply_text(
                f"Successfully transferred {len(owner_characters)} characters from owner with ID {owner_id} back to user with ID {user_id}."
            )
        else:
            await message.reply_text('Neither the user nor the owner have any characters to transfer.')

    except Exception as e:
        await message.reply_text(f'An error occurred: {str(e)}')
