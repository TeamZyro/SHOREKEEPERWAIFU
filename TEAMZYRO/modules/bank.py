from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from TEAMZYRO import app, db

@app.on_message(filters.command("bank"))
async def bank_command(client, message):
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 Open Bank WebApp", url=f"https://t.me/{bot_username}?startapp=true")]
    ])
    await message.reply_text(
        "🏦 **WELCOME TO SHOREKEEPER BANK** 🏦\n\n"
        "Here you can take coin loans by pledging your characters as collateral.\n\n"
        "**Loan Rules:**\n"
        "• **LTV (Loan-to-Value)**: Get up to **60%** value of your character's rarity price.\n"
        "• **Interest**: Flat **10%** interest on borrow amount.\n"
        "• **Repayment**: 5 Daily EMIs (equally split over 5 days).\n"
        "• **Seizure Alert**: If an EMI bounces 3 times, your collateral will be permanently seized!\n\n"
        "Use `/loans` to view your active loans directly here, or click the button below to visit the Bank WebApp.",
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.MARKDOWN
    )

@app.on_message(filters.command("loans"))
async def loans_command(client, message):
    user_id = message.from_user.id
    loans = await db['bank_loans'].find({"user_id": user_id, "status": "active"}).to_list(length=100)
    
    if not loans:
        await message.reply_text("ℹ️ You do not have any active bank loans currently.")
        return
        
    text = "📋 **YOUR ACTIVE BANK LOANS** 📋\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, loan in enumerate(loans, 1):
        rem = loan['total_repayable'] - loan['amount_paid']
        next_due = loan['next_emi_due'].strftime("%Y-%m-%d %H:%M UTC")
        char_names = ", ".join([c.get('name', 'Unknown') for c in loan.get('collateral_characters', [])])
        text += (
            f"**{i}. Loan ID:** `{loan['loan_id']}`\n"
            f"• **Principal Borrowed:** 💰 `{loan['principal']:,}` coins\n"
            f"• **Total Repayable:** 💰 `{loan['total_repayable']:,}` coins\n"
            f"• **Remaining Debt:** 💰 `{rem:,}` coins\n"
            f"• **EMI Amount:** 💰 `{loan['emi_amount']:,}` coins/day\n"
            f"• **EMIs Remaining:** `{loan['emis_remaining']}` of `{loan['emis_total']}`\n"
            f"• **Bounces:** `{loan['bounced_count']}/3` ⚠️\n"
            f"• **Next Due:** `{next_due}`\n"
            f"• **Collateral Pledged:** {char_names}\n\n"
        )
    await message.reply_text(text, parse_mode=enums.ParseMode.MARKDOWN)
