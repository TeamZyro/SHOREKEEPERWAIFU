# TEAMZYRO/modules/rarity.py
from TEAMZYRO import app, collection, db
from pyrogram import filters

custom_art_collection = db["custom_characters"]

@app.on_message(filters.command("rarity"))
async def rarity_count(client, message):
    try:
        distinct_rarities = await collection.distinct("rarity")
        response_message = "✨ Character Count by Rarity ✨\n\n"
        total_count = 0

        for rarity in sorted(distinct_rarities):
            count = await collection.count_documents({"rarity": rarity})
            total_count += count
            response_message += f"◈ {rarity} — {count} character(s)\n"

        # Creator Studio characters are stored separately from the normal drop pool.
        custom_count = await custom_art_collection.count_documents({"status": "approved"})
        response_message += f"◈ 🎨 Customise — {custom_count} character(s)\n"
        total_count += custom_count
        response_message += f"\n💠 Total Characters: {total_count}"
        await message.reply_text(response_message)

    except Exception as e:
        await message.reply_text(f"⚠️ Error: {str(e)}")
