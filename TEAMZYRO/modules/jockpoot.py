# TEAMZYRO/commands/jackpot.py
from TEAMZYRO import app, user_collection
from pyrogram import filters
from pymongo import ReturnDocument
import datetime

@app.on_message(filters.command("jackpot"))
async def basket(bot, message):
    user_id = message.from_user.id
    today = datetime.date.today()

    # Check if user exists in the database
    user_data = await user_collection.find_one({"id": user_id})
    if not user_data:
        # Initialize user data
        user_data = {
            "user_id": user_id,
            "balance": 0,
            "last_played": None,
            "plays_today": 0
        }
        await collection.insert_one(user_data)

    # Check play limits
    last_played = user_data.get("last_played")
    plays_today = user_data.get("plays_today", 0)

    if last_played == str(today):
        if plays_today >= 2:
            await message.reply_text("You can only play the jackpot twice per day. Try again tomorrow!")
            return
    else:
        # Reset the play count for a new day
        plays_today = 0

    # Send dice and calculate score
    dice_message = await bot.send_dice(message.chat.id, "🎰")
    dice_score = dice_message.dice.value

    # Calculate rewards
    if dice_score == 64:
        coins_earned = 2000
    else:
        coins_earned = 5 * dice_score

    # Update user's balance and play count
    updated_user = await user_collection.find_one_and_update(
        {"id": user_id},
        {
            "$set": {"last_played": str(today)},
            "$inc": {"balance": coins_earned, "plays_today": 1}
        },
        return_document=ReturnDocument.AFTER
    )

    # Send response
    await message.reply_text(
        f"Hey {message.from_user.mention}, your score is: {dice_score}.\n"
        f"You earned **{coins_earned} coins**! 🎉\n"
        f"Your new balance is **{updated_user['balance']} coins**.",
        quote=True
    )
