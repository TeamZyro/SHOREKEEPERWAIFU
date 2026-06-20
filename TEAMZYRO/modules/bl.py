import asyncio
import traceback
import os
import random
import urllib.parse
import json
import hmac
import hashlib
import math
from datetime import datetime, timedelta
from aiohttp import web
from bson import ObjectId

from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from TEAMZYRO import app, user_collection, db, TOKEN, application
from TEAMZYRO.unit.zyro_rarity import rarity_map2

# Collections
black_market_collection = db['black_market_listings']

# Locks per user to prevent concurrent race conditions
user_locks = {}

def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]

# ----------------- Helper Functions -----------------

def verify_telegram_webapp_data(init_data: str, bot_token: str) -> dict:
    """
    Verifies the integrity and authenticity of Telegram Web App launch data.
    Allows a developer bypass: debug_user_<user_id> to ease API testing.
    """
    if not init_data:
        return None

    if init_data.startswith("debug_"):
        try:
            debug_id = int(init_data.split("_")[2])
        except (ValueError, IndexError):
            debug_id = 7078181502  # Default developer ID fallback
        return {
            "id": debug_id,
            "first_name": "DebugUser",
            "username": "debug_user"
        }

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if 'hash' not in parsed_data:
            return None
        
        received_hash = parsed_data['hash']
        
        # Sort keys and create check string
        sorted_keys = sorted([k for k in parsed_data.keys() if k != 'hash'])
        data_check_string = '\n'.join([f"{k}={parsed_data[k]}" for k in sorted_keys])
        
        # Calculate secret key with WebAppData prefix
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        
        # Calculate signature hash
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash == received_hash:
            user_data = json.loads(parsed_data['user'])
            return user_data
    except Exception as e:
        print(f"Error validating webapp data: {e}")
    return None

class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

def mongo_json_response(data, status=200):
    return web.json_response(
        data,
        status=status,
        dumps=lambda x: json.dumps(x, cls=MongoJSONEncoder),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
        }
    )

# ----------------- Bot Commands -----------------

@app.on_message(filters.command(["sell", "sellchar"]))
async def sell_character(client, message):
    user_id = message.from_user.id
    args = message.command
    if len(args) != 3:
        await message.reply_text("Usage: `/sell <character_id> <price>`\nExample: `/sell 101 5000`", parse_mode=enums.ParseMode.MARKDOWN)
        return
    
    char_id = args[1]
    try:
        price = int(args[2])
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.reply_text("Price must be a positive integer!")
        return
        
    async with get_user_lock(user_id):
        user = await user_collection.find_one({'id': user_id})
        if not user or 'characters' not in user:
            await message.reply_text("You don't have any characters in your harem!")
            return
        
        # Find character in user's collection
        character = next((c for c in user['characters'] if str(c.get('id')) == str(char_id)), None)
        if not character:
            await message.reply_text(f"You don't own character ID **{char_id}**!")
            return
            
        # Remove exactly one copy from harem
        user['characters'].remove(character)
        await user_collection.update_one({'id': user_id}, {'$set': {'characters': user['characters']}})
        
        # Generate short unique listing ID
        while True:
            listing_id = str(random.randint(100000, 999999))
            existing = await black_market_collection.find_one({"listing_id": listing_id})
            if not existing:
                break
                
        # Save listing to database
        listing = {
            "listing_id": listing_id,
            "seller_id": user_id,
            "seller_username": message.from_user.username or "",
            "seller_first_name": message.from_user.first_name or "User",
            "character": character,
            "price": price,
            "listed_at": datetime.utcnow()
        }
        await black_market_collection.insert_one(listing)
        
        # Reply with character media and details
        caption = (
            f"🛒 **Listed on Black Market!**\n\n"
            f"🌸 **{character.get('name', 'Unknown')}** (ID: `{character.get('id')}`) ({character.get('rarity', 'Unknown')})\n"
            f"⛩️ Anime: **{character.get('anime', 'Unknown')}**\n"
            f"💰 Price: **{price:,}** coins\n"
            f"🆔 Listing ID: `{listing_id}`\n\n"
            f"This character has been moved to escrow and won't show in your harem. "
            f"Use `/unsell {listing_id}` to cancel the sale."
        )
        
        bot_username = client.me.username if client.me else "shorekeeper_RoBot"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")]
        ])
        
        if character.get('vid_url'):
            await message.reply_video(video=character['vid_url'], caption=caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)
        elif character.get('img_url'):
            await message.reply_photo(photo=character['img_url'], caption=caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await message.reply_text(caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_message(filters.command("unsell"))
async def unsell_character(client, message):
    user_id = message.from_user.id
    args = message.command
    if len(args) != 2:
        await message.reply_text("Usage: `/unsell <listing_id>`", parse_mode=enums.ParseMode.MARKDOWN)
        return
        
    listing_id = args[1]
    
    async with get_user_lock(user_id):
        listing = await black_market_collection.find_one({"listing_id": listing_id})
        if not listing:
            await message.reply_text("Listing not found or already sold!")
            return
            
        if listing['seller_id'] != user_id:
            await message.reply_text("You are not the seller of this listing!")
            return
            
        # Return character to user's collection
        character = listing['character']
        await user_collection.update_one(
            {'id': user_id},
            {'$push': {'characters': character}}
        )
        
        # Remove listing
        await black_market_collection.delete_one({"listing_id": listing_id})
        
        bot_username = client.me.username if client.me else "shorekeeper_RoBot"
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")]
        ])
            
        await message.reply_text(
            f"❌ **Listing Cancelled!**\n"
            f"**{character.get('name', 'Unknown')}** has been returned to your harem.",
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )

@app.on_message(filters.command("buy"))
async def buy_character(client, message):
    buyer_id = message.from_user.id
    args = message.command
    if len(args) != 2:
        await message.reply_text("Usage: `/buy <listing_id>`", parse_mode=enums.ParseMode.MARKDOWN)
        return
        
    listing_id = args[1]
    
    listing = await black_market_collection.find_one({"listing_id": listing_id})
    if not listing:
        await message.reply_text("Listing not found or already sold!")
        return
        
    seller_id = listing['seller_id']
    price = listing['price']
    character = listing['character']
    
    if buyer_id == seller_id:
        await message.reply_text("You cannot buy your own character! Use `/unsell <listing_id>` to cancel the sale.", parse_mode=enums.ParseMode.MARKDOWN)
        return
        
    # Lock users deterministically to avoid deadlock
    lock_1, lock_2 = min(buyer_id, seller_id), max(buyer_id, seller_id)
    
    async with get_user_lock(lock_1):
        async with get_user_lock(lock_2):
            listing = await black_market_collection.find_one({"listing_id": listing_id})
            if not listing:
                await message.reply_text("Listing not found or already sold!")
                return
                
            buyer = await user_collection.find_one({'id': buyer_id})
            buyer_balance = buyer.get('balance', 0) if buyer else 0
            if buyer_balance < price:
                await message.reply_text(f"Insufficient balance! You need **{price}** coins, but you only have **{buyer_balance}**.", parse_mode=enums.ParseMode.MARKDOWN)
                return
                
            # Perform atomic balance adjustments
            await user_collection.update_one({'id': buyer_id}, {'$inc': {'balance': -price}})
            await user_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
            
            # Transfer character
            if buyer:
                await user_collection.update_one({'id': buyer_id}, {'$push': {'characters': character}})
            else:
                await user_collection.insert_one({
                    'id': buyer_id,
                    'username': message.from_user.username or "",
                    'first_name': message.from_user.first_name or "User",
                    'characters': [character],
                    'balance': 0
                })
                
            # Remove listing
            await black_market_collection.delete_one({"listing_id": listing_id})
            
            buyer_name = message.from_user.first_name or "User"
            seller_name = listing.get('seller_first_name', 'User')
            
            bot_username = client.me.username if client.me else "shorekeeper_RoBot"
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")]
            ])

            await message.reply_text(
                f"🎉 **Purchase Successful!**\n\n"
                f"You bought **{character.get('name', 'Unknown')}** (ID: `{character.get('id')}`) for **{price:,}** coins from [{seller_name}](tg://user?id={seller_id}).",
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
            # Notify seller
            try:
                await client.send_message(
                    chat_id=seller_id,
                    text=f"💰 **Character Sold!**\n\n"
                         f"Your character **{character.get('name', 'Unknown')}** (ID: `{character.get('id')}`) was bought by [{buyer_name}](tg://user?id={buyer_id}) for **{price:,}** coins!",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"Error notifying seller: {e}")

@app.on_message(filters.command(["bm", "blackmarket"]))
async def black_market_catalog(client, message):
    page = 0
    await display_black_market(client, message, page, is_initial=True)

@app.on_message(filters.command("my_listings"))
async def my_listings_command(client, message):
    user_id = message.from_user.id
    listings = await black_market_collection.find({"seller_id": user_id}).to_list(length=100)
    
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    if not listings:
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")]
        ])
        await message.reply_text("You don't have any active listings in the black market.", reply_markup=reply_markup)
        return
        
    text = "📋 **YOUR BLACK MARKET LISTINGS**\n\n"
    keyboard = []
    for i, listing in enumerate(listings, 1):
        char = listing['character']
        price = listing['price']
        rarity_emoji = rarity_map2.get(char.get('rarity'), '')
        text += (
            f"**{i}.** {rarity_emoji} **{char.get('name', 'Unknown')}** (ID: `{char.get('id')}`)\n"
            f"  Price: 💰 `{price:,}` coins\n"
            f"  Listing ID: `{listing['listing_id']}`\n\n"
        )
        keyboard.append([InlineKeyboardButton(f"❌ Cancel {char.get('name', 'Char')[:12]}...", callback_data=f"bm_cancel_conf:{listing['listing_id']}:0")])
        
    keyboard.append([InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")])
        
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await message.reply_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

# ----------------- Interactive Telegram Interface -----------------

async def display_black_market(client, message_or_query, page, is_initial=False):
    is_callback = not is_initial
    message = message_or_query.message if is_callback else message_or_query
    
    listings = await black_market_collection.find({}).sort("listed_at", -1).to_list(length=100)
    
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    if not listings:
        text = "🛒 **SHOREKEEPER BLACK MARKET**\n\nThere are no active listings at the moment."
        keyboard = [
            [InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            await message_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await message.reply_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)
        return
        
    items_per_page = 5
    total_pages = (len(listings) + items_per_page - 1) // items_per_page
    
    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1
        
    start_idx = page * items_per_page
    end_idx = start_idx + items_per_page
    page_listings = listings[start_idx:end_idx]
    
    text = f"🛒 **SHOREKEEPER BLACK MARKET** (Page {page+1}/{total_pages})\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, listing in enumerate(page_listings, 1):
        idx = start_idx + i
        char = listing['character']
        price = listing['price']
        rarity_emoji = rarity_map2.get(char.get('rarity'), '')
        seller_name = listing.get('seller_first_name', 'User')
        text += (
            f"**{idx}.** {rarity_emoji} **{char.get('name', 'Unknown')}** (ID: `{char.get('id')}`)\n"
            f"  ◈ Anime: {char.get('anime', 'Unknown')}\n"
            f"  ◈ Price: 💰 `{price:,}` coins\n"
            f"  ◈ Seller: [{seller_name}](tg://user?id={listing['seller_id']})\n"
            f"  ◈ Listing ID: `{listing['listing_id']}`\n\n"
        )
        
    text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "Click any number below to view the character details and buy it!"
    
    keyboard = []
    detail_row = []
    for i in range(len(page_listings)):
        listing = page_listings[i]
        detail_row.append(InlineKeyboardButton(f"{i+1}", callback_data=f"bm_detail:{listing['listing_id']}:{page}"))
    keyboard.append(detail_row)
    
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"bm_page:{page-1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"bm_page:{page+1}"))
    if nav_row:
        keyboard.append(nav_row)
        
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    keyboard.append([InlineKeyboardButton("🛒 Open Web App", url=f"https://t.me/{bot_username}?startapp=true")])
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await message_or_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^bm_page:"))
async def on_bm_page(client, callback_query):
    data = callback_query.data.split(":")
    page = int(data[1])
    await display_black_market(client, callback_query, page, is_initial=False)

@app.on_callback_query(filters.regex(r"^bm_detail:"))
async def on_bm_detail(client, callback_query):
    data = callback_query.data.split(":")
    listing_id = data[1]
    back_page = int(data[2])
    user_id = callback_query.from_user.id
    
    listing = await black_market_collection.find_one({"listing_id": listing_id})
    if not listing:
        await callback_query.answer("This listing is no longer available.", show_alert=True)
        await display_black_market(client, callback_query, back_page, is_initial=False)
        return
        
    char = listing['character']
    price = listing['price']
    seller_id = listing['seller_id']
    seller_name = listing.get('seller_first_name', 'User')
    rarity_emoji = rarity_map2.get(char.get('rarity'), '')
    
    caption = (
        f"🛒 **BLACK MARKET LISTING DETAILS**\n\n"
        f"🌸 **{char.get('name', 'Unknown')}** (ID: `{char.get('id')}`)\n"
        f"🔮 Rarity: {rarity_emoji} **{char.get('rarity', 'Unknown')}**\n"
        f"⛩️ Anime: **{char.get('anime', 'Unknown')}**\n"
        f"💰 Price: **{price:,}** coins\n"
        f"👤 Seller: [{seller_name}](tg://user?id={seller_id})\n"
        f"🆔 Listing ID: `{listing_id}`\n\n"
    )
    
    keyboard = []
    if user_id == seller_id:
        caption += "💡 This is your own listing. You can cancel it below."
        keyboard.append([InlineKeyboardButton("❌ Cancel Listing", callback_data=f"bm_cancel_conf:{listing_id}:{back_page}")])
    else:
        keyboard.append([InlineKeyboardButton("💰 Buy Character", callback_data=f"bm_buy_conf:{listing_id}:{back_page}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Market", callback_data=f"bm_page:{back_page}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Hide/embed preview image inside zero width space link to achieve text-edit preview swap
    img_url = char.get('img_url') or char.get('vid_url')
    if img_url:
        caption = f"[‌]({img_url})" + caption
        
    await callback_query.edit_message_text(caption, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^bm_cancel_conf:"))
async def on_bm_cancel_conf(client, callback_query):
    data = callback_query.data.split(":")
    listing_id = data[1]
    back_page = int(data[2])
    user_id = callback_query.from_user.id
    
    async with get_user_lock(user_id):
        listing = await black_market_collection.find_one({"listing_id": listing_id})
        if not listing:
            await callback_query.answer("Listing not found or already sold!", show_alert=True)
            await display_black_market(client, callback_query, back_page, is_initial=False)
            return
            
        if listing['seller_id'] != user_id:
            await callback_query.answer("Only the seller can cancel this listing!", show_alert=True)
            return
            
        character = listing['character']
        await user_collection.update_one(
            {'id': user_id},
            {'$push': {'characters': character}}
        )
        await black_market_collection.delete_one({"listing_id": listing_id})
        
        await callback_query.answer("Listing cancelled successfully!", show_alert=True)
        await display_black_market(client, callback_query, back_page, is_initial=False)

@app.on_callback_query(filters.regex(r"^bm_buy_conf:"))
async def on_bm_buy_conf(client, callback_query):
    data = callback_query.data.split(":")
    listing_id = data[1]
    back_page = int(data[2])
    
    listing = await black_market_collection.find_one({"listing_id": listing_id})
    if not listing:
        await callback_query.answer("Listing not found or already sold!", show_alert=True)
        await display_black_market(client, callback_query, back_page, is_initial=False)
        return
        
    char = listing['character']
    price = listing['price']
    
    text = (
        f"⚠️ **CONFIRM PURCHASE**\n\n"
        f"Are you sure you want to purchase **{char.get('name', 'Unknown')}** for **{price:,}** coins?\n"
        f"This action cannot be undone."
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Buy It", callback_data=f"bm_buy_exec:{listing_id}:{back_page}"),
            InlineKeyboardButton("❌ No, Cancel", callback_data=f"bm_detail:{listing_id}:{back_page}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

@app.on_callback_query(filters.regex(r"^bm_buy_exec:"))
async def on_bm_buy_exec(client, callback_query):
    data = callback_query.data.split(":")
    listing_id = data[1]
    back_page = int(data[2])
    buyer_id = callback_query.from_user.id
    
    listing = await black_market_collection.find_one({"listing_id": listing_id})
    if not listing:
        await callback_query.answer("Listing not found or already sold!", show_alert=True)
        await display_black_market(client, callback_query, back_page, is_initial=False)
        return
        
    seller_id = listing['seller_id']
    price = listing['price']
    character = listing['character']
    
    if buyer_id == seller_id:
        await callback_query.answer("You cannot buy your own character!", show_alert=True)
        return
        
    lock_1, lock_2 = min(buyer_id, seller_id), max(buyer_id, seller_id)
    
    async with get_user_lock(lock_1):
        async with get_user_lock(lock_2):
            listing = await black_market_collection.find_one({"listing_id": listing_id})
            if not listing:
                await callback_query.answer("Listing not found or already sold!", show_alert=True)
                await display_black_market(client, callback_query, back_page, is_initial=False)
                return
                
            buyer = await user_collection.find_one({'id': buyer_id})
            buyer_balance = buyer.get('balance', 0) if buyer else 0
            if buyer_balance < price:
                await callback_query.answer(f"Insufficient balance! You need {price:,} coins but only have {buyer_balance:,}.", show_alert=True)
                return
                
            # Deduct buyer, pay seller
            await user_collection.update_one({'id': buyer_id}, {'$inc': {'balance': -price}})
            await user_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
            
            # Transfer character
            if buyer:
                await user_collection.update_one({'id': buyer_id}, {'$push': {'characters': character}})
            else:
                await user_collection.insert_one({
                    'id': buyer_id,
                    'username': callback_query.from_user.username or "",
                    'first_name': callback_query.from_user.first_name or "User",
                    'characters': [character],
                    'balance': 0
                })
                
            # Remove listing
            await black_market_collection.delete_one({"listing_id": listing_id})
            
            await callback_query.answer("Purchase successful!", show_alert=True)
            
            buyer_name = callback_query.from_user.first_name or "User"
            seller_name = listing.get('seller_first_name', 'User')
            
            await callback_query.edit_message_text(
                f"🎉 **Purchase Successful!**\n\n"
                f"You have bought **{character.get('name', 'Unknown')}** (ID: `{character.get('id')}`) for **{price:,}** coins from [{seller_name}](tg://user?id={seller_id})!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Market", callback_data=f"bm_page:{back_page}")]]),
                parse_mode=enums.ParseMode.MARKDOWN
            )
            
            # Notify seller
            try:
                await client.send_message(
                    chat_id=seller_id,
                    text=f"💰 **Character Sold!**\n\n"
                         f"Your character **{character.get('name', 'Unknown')}** was bought by [{buyer_name}](tg://user?id={buyer_id}) for **{price:,}** coins!",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"Error notifying seller: {e}")

# ----------------- Web App API Endpoints -----------------

async def api_get_listings(request):
    if request.method == "OPTIONS":
        return api_options_handler(request)
    listings = await black_market_collection.find({}).sort("listed_at", -1).to_list(length=100)
    return mongo_json_response(listings)

async def api_get_balance(request):
    if request.method == "OPTIONS":
        return api_options_handler(request)
    user_info = await get_authed_user(request)
    if not user_info:
        return mongo_json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_info['id']
    user = await user_collection.find_one({'id': user_id}, {'balance': 1})
    balance = user.get('balance', 0) if user else 0
    return mongo_json_response({"balance": balance})

async def api_get_harem(request):
    if request.method == "OPTIONS":
        return api_options_handler(request)
    user_info = await get_authed_user(request)
    if not user_info:
        return mongo_json_response({"error": "Unauthorized"}, status=401)
    
    user_id = user_info['id']
    user = await user_collection.find_one({'id': user_id})
    characters = user.get('characters', []) if user else []
    return mongo_json_response({"characters": characters})

async def api_sell_character(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
        
        user_id = user_info['id']
        try:
            body = await request.json()
            char_id = str(body.get('character_id'))
            price = int(body.get('price', 0))
            if not char_id or price <= 0:
                return mongo_json_response({"error": "Invalid character_id or price"}, status=400)
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)
            
        async with get_user_lock(user_id):
            user = await user_collection.find_one({'id': user_id})
            if not user or 'characters' not in user:
                return mongo_json_response({"error": "You don't have any characters"}, status=400)
                
            character = next((c for c in user['characters'] if str(c.get('id')) == char_id), None)
            if not character:
                return mongo_json_response({"error": "Character not found in your harem"}, status=400)
                
            user['characters'].remove(character)
            await user_collection.update_one({'id': user_id}, {'$set': {'characters': user['characters']}})
            
            while True:
                listing_id = str(random.randint(100000, 999999))
                existing = await black_market_collection.find_one({"listing_id": listing_id})
                if not existing:
                    break
                    
            listing = {
                "listing_id": listing_id,
                "seller_id": user_id,
                "seller_username": user_info.get('username') or "",
                "seller_first_name": user_info.get('first_name') or "User",
                "character": character,
                "price": price,
                "listed_at": datetime.utcnow()
            }
            await black_market_collection.insert_one(listing)
            return mongo_json_response({"success": True, "listing_id": listing_id})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

async def api_buy_character(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
            
        buyer_id = user_info['id']
        try:
            body = await request.json()
            listing_id = body.get('listing_id')
            if not listing_id:
                return mongo_json_response({"error": "Invalid listing_id"}, status=400)
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)
            
        listing = await black_market_collection.find_one({"listing_id": listing_id})
        if not listing:
            return mongo_json_response({"error": "Listing not found or already sold"}, status=400)
            
        seller_id = listing['seller_id']
        price = listing['price']
        character = listing['character']
        
        if buyer_id == seller_id:
            return mongo_json_response({"error": "You cannot buy your own listing"}, status=400)
            
        lock_1, lock_2 = min(buyer_id, seller_id), max(buyer_id, seller_id)
        async with get_user_lock(lock_1):
            async with get_user_lock(lock_2):
                listing = await black_market_collection.find_one({"listing_id": listing_id})
                if not listing:
                    return mongo_json_response({"error": "Listing already sold"}, status=400)
                    
                buyer = await user_collection.find_one({'id': buyer_id})
                buyer_balance = buyer.get('balance', 0) if buyer else 0
                if buyer_balance < price:
                    return mongo_json_response({"error": "Insufficient balance"}, status=400)
                    
                await user_collection.update_one({'id': buyer_id}, {'$inc': {'balance': -price}})
                await user_collection.update_one({'id': seller_id}, {'$inc': {'balance': price}})
                
                if buyer:
                    await user_collection.update_one({'id': buyer_id}, {'$push': {'characters': character}})
                else:
                    await user_collection.insert_one({
                        'id': buyer_id,
                        'username': user_info.get('username') or "",
                        'first_name': user_info.get('first_name') or "User",
                        'characters': [character],
                        'balance': 0
                    })
                    
                await black_market_collection.delete_one({"listing_id": listing_id})
                
                # Send notifications
                try:
                    buyer_name = user_info.get('first_name') or "User"
                    await app.send_message(
                        chat_id=seller_id,
                        text=f"💰 **Character Sold!**\n\nYour character **{character.get('name', 'Unknown')}** (ID: `{character.get('id')}`) was bought by [{buyer_name}](tg://user?id={buyer_id}) for **{price:,}** coins!",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                    
                return mongo_json_response({"success": True})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

async def api_cancel_listing(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
            
        user_id = user_info['id']
        try:
            body = await request.json()
            listing_id = body.get('listing_id')
            if not listing_id:
                return mongo_json_response({"error": "Invalid listing_id"}, status=400)
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)
            
        async with get_user_lock(user_id):
            listing = await black_market_collection.find_one({"listing_id": listing_id})
            if not listing:
                return mongo_json_response({"error": "Listing not found"}, status=400)
                
            if listing['seller_id'] != user_id:
                return mongo_json_response({"error": "Only the seller can cancel this listing"}, status=400)
                
            character = listing['character']
            await user_collection.update_one(
                {'id': user_id},
                {'$push': {'characters': character}}
            )
            await black_market_collection.delete_one({"listing_id": listing_id})
            return mongo_json_response({"success": True})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)



# ----------------- Bank System APIs & Background Tasks -----------------

# Rarity Pricing for bank collateral valuation (LTV = 60%)
RARITY_PRICE = {
    "⚪️ Common": 1000,
    "🟣 Rare": 5000,
    "🟡 Legendary": 15000,
    "🟢 Medium": 30000,
    "💮 Special Edition": 25000,
    "🔮 Limited Edition": 40000,
    "💸 Premium Edition": 30000,
    "🌤 Summer": 35000,
    "🎐 Celestial": 45000,
    "❄️ Winter": 20000,
    "💝 Valentine": 18000,
    "🎃 Halloween": 16000,
    "🎄 Christmas Special": 22000,
    "🪐 Omniversal": 80000,
    "🎭 Cosplay Master 🎭": 70000,
    "🧧 Events": 25000,
    "🍑 Echhi": 30000,
    "🎗️ AMV Edition": 27000,
    "🌟 Luminous": 50000,
}

async def api_get_loans(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
        
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
            
        user_id = user_info['id']
        loans = await db['bank_loans'].find({"user_id": user_id}).sort("created_at", -1).to_list(length=100)
        return mongo_json_response({"loans": loans})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

async def api_borrow_loan(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
            
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
            
        user_id = user_info['id']
        try:
            body = await request.json()
            character_ids = body.get('character_ids', [])
            if not character_ids:
                return mongo_json_response({"error": "No characters selected as collateral"}, status=400)
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)
            
        async with get_user_lock(user_id):
            active_loans_count = await db['bank_loans'].count_documents({"user_id": user_id, "status": "active"})
            if active_loans_count >= 3:
                return mongo_json_response({"error": "You already have 3 active loans. Please clear existing loans first."}, status=400)

            user = await user_collection.find_one({'id': user_id})
            if not user or 'characters' not in user:
                return mongo_json_response({"error": "No characters owned"}, status=400)
                
            harem = user['characters']
            collateral_chars = []
            
            for cid in character_ids:
                char_idx = next((i for i, c in enumerate(harem) if str(c.get('id')) == str(cid)), -1)
                if char_idx == -1:
                    return mongo_json_response({"error": f"Character with ID {cid} not found in your harem"}, status=400)
                collateral_chars.append(harem.pop(char_idx))
                
            total_val = 0
            for char in collateral_chars:
                rarity = char.get('rarity', '⚪️ Common')
                price = RARITY_PRICE.get(rarity, 1000)
                total_val += int(price * 0.60)
                
            if total_val <= 0:
                return mongo_json_response({"error": "Selected characters have zero collateral value"}, status=400)
                
            principal = total_val
            total_repayable = int(principal * 1.10)
            emi_amount = int(math.ceil(total_repayable / 5))
            
            while True:
                loan_id = str(random.randint(100000, 999999))
                existing = await db['bank_loans'].find_one({"loan_id": loan_id})
                if not existing:
                    break
                    
            loan = {
                "loan_id": loan_id,
                "user_id": user_id,
                "principal": principal,
                "total_repayable": total_repayable,
                "amount_paid": 0,
                "emis_total": 5,
                "emis_remaining": 5,
                "emi_amount": emi_amount,
                "next_emi_due": datetime.utcnow() + timedelta(days=1),
                "collateral_characters": collateral_chars,
                "bounced_count": 0,
                "status": "active",
                "created_at": datetime.utcnow()
            }
            
            await user_collection.update_one(
                {'id': user_id},
                {
                    '$inc': {'balance': principal},
                    '$set': {'characters': harem}
                }
            )
            
            await db['bank_loans'].insert_one(loan)
            
            char_names = ", ".join([c.get('name', 'Unknown') for c in collateral_chars])
            try:
                await app.send_message(
                    chat_id=user_id,
                    text=f"🏦 **Loan Approved!**\n\n"
                         f"You successfully borrowed **{principal:,} coins** from the bank by pledging:\n"
                         f"🌸 **{char_names}** as collateral.\n\n"
                         f"• **Loan ID:** `{loan_id}`\n"
                         f"• **Total Repayable:** 💰 `{total_repayable:,}` coins\n"
                         f"• **Daily EMI:** 💰 `{emi_amount:,}` coins\n"
                         f"• **Next Due Date:** {(datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                         f"⚠️ *Please ensure you have enough balance every day to avoid EMI bounces.*",
                    parse_mode=enums.ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"Failed to notify user: {e}")
                
            return mongo_json_response({"success": True, "loan_id": loan_id, "principal": principal})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

async def api_repay_loan(request):
    try:
        if request.method == "OPTIONS":
            return api_options_handler(request)
            
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
            
        user_id = user_info['id']
        try:
            body = await request.json()
            loan_id = body.get('loan_id')
            repay_type = body.get('repay_type', 'full')
            if not loan_id:
                return mongo_json_response({"error": "Invalid loan_id"}, status=400)
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)
            
        async with get_user_lock(user_id):
            loan = await db['bank_loans'].find_one({"loan_id": loan_id, "user_id": user_id, "status": "active"})
            if not loan:
                return mongo_json_response({"error": "Active loan not found"}, status=400)
                
            user = await user_collection.find_one({'id': user_id})
            balance = user.get('balance', 0) if user else 0
            
            debt_remaining = loan['total_repayable'] - loan['amount_paid']
            
            if repay_type == 'full':
                repay_amount = debt_remaining
            elif repay_type == 'emi':
                repay_amount = min(loan['emi_amount'], debt_remaining)
            else:
                return mongo_json_response({"error": "Invalid repay_type"}, status=400)
                
            if balance < repay_amount:
                return mongo_json_response({"error": f"Insufficient balance. You need {repay_amount:,} coins, but only have {balance:,}."}, status=400)
                
            new_balance = balance - repay_amount
            new_amount_paid = loan['amount_paid'] + repay_amount
            
            await user_collection.update_one({'id': user_id}, {'$set': {'balance': new_balance}})
            
            is_completed = (new_amount_paid >= loan['total_repayable']) or (repay_type == 'full')
            
            if is_completed:
                collateral_chars = loan.get('collateral_characters', [])
                await user_collection.update_one(
                    {'id': user_id},
                    {'$push': {'characters': {'$each': collateral_chars}}}
                )
                
                await db['bank_loans'].update_one(
                    {"loan_id": loan_id},
                    {
                        '$set': {
                            'amount_paid': loan['total_repayable'],
                            'emis_remaining': 0,
                            'status': 'repaid'
                        }
                    }
                )
                
                char_names = ", ".join([c.get('name', 'Unknown') for c in collateral_chars])
                try:
                    await app.send_message(
                        chat_id=user_id,
                        text=f"🎉 **Loan Fully Repaid!**\n\n"
                             f"Your loan `{loan_id}` of **{loan['principal']:,} coins** is fully paid off.\n"
                             f"The bank has returned your collateral characters to your harem:\n"
                             f"🌸 **{char_names}**",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                except Exception as e:
                    print(f"Failed to notify user: {e}")
                    
                return mongo_json_response({"success": True, "repaid_full": True})
            else:
                new_emis_remaining = max(0, loan['emis_remaining'] - 1)
                new_next_due = loan['next_emi_due'] + timedelta(days=1)
                
                await db['bank_loans'].update_one(
                    {"loan_id": loan_id},
                    {
                        '$set': {
                            'amount_paid': new_amount_paid,
                            'emis_remaining': new_emis_remaining,
                            'next_emi_due': new_next_due,
                            'bounced_count': 0
                        }
                    }
                )
                
                try:
                    await app.send_message(
                        chat_id=user_id,
                        text=f"💸 **EMI Payment Received!**\n\n"
                             f"You paid an EMI of **{repay_amount:,} coins** for loan `{loan_id}`.\n"
                             f"• **Remaining Debt:** 💰 `{loan['total_repayable'] - new_amount_paid:,}` coins\n"
                             f"• **EMIs Remaining:** `{new_emis_remaining}`\n"
                             f"• **Next Due:** {new_next_due.strftime('%Y-%m-%d %H:%M UTC')}",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                except Exception as e:
                    print(f"Failed to notify user: {e}")
                    
                return mongo_json_response({"success": True, "repaid_full": False, "amount_paid": repay_amount})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

async def run_bank_emi_loop():
    print("=== Bank EMI Background Task Started ===")
    while True:
        try:
            await process_bank_emis()
        except Exception as e:
            print(f"Error in process_bank_emis loop: {e}")
            traceback.print_exc()
        await asyncio.sleep(60)

async def process_bank_emis():
    now = datetime.utcnow()
    active_loans = await db['bank_loans'].find({"status": "active", "next_emi_due": {"$lte": now}}).to_list(length=100)
    
    for loan in active_loans:
        user_id = loan['user_id']
        loan_id = loan['loan_id']
        
        async with get_user_lock(user_id):
            current_loan = await db['bank_loans'].find_one({"loan_id": loan_id, "status": "active"})
            if not current_loan or current_loan['next_emi_due'] > now:
                continue
                
            user = await user_collection.find_one({'id': user_id})
            balance = user.get('balance', 0) if user else 0
            
            emi_amount = current_loan['emi_amount']
            debt_remaining = current_loan['total_repayable'] - current_loan['amount_paid']
            charge_amount = min(emi_amount, debt_remaining)
            
            if balance >= charge_amount:
                new_balance = balance - charge_amount
                new_amount_paid = current_loan['amount_paid'] + charge_amount
                new_emis_remaining = max(0, current_loan['emis_remaining'] - 1)
                
                await user_collection.update_one({'id': user_id}, {'$set': {'balance': new_balance}})
                
                is_completed = (new_amount_paid >= current_loan['total_repayable']) or (new_emis_remaining == 0)
                
                if is_completed:
                    collateral_chars = current_loan.get('collateral_characters', [])
                    await user_collection.update_one(
                        {'id': user_id},
                        {'$push': {'characters': {'$each': collateral_chars}}}
                    )
                    
                    await db['bank_loans'].update_one(
                        {"loan_id": loan_id},
                        {
                            '$set': {
                                'amount_paid': current_loan['total_repayable'],
                                'emis_remaining': 0,
                                'status': 'repaid'
                            }
                        }
                    )
                    
                    char_names = ", ".join([c.get('name', 'Unknown') for c in collateral_chars])
                    try:
                        await app.send_message(
                            chat_id=user_id,
                            text=f"🎉 **Loan Auto-Repaid!**\n\n"
                                 f"Your loan `{loan_id}` of **{current_loan['principal']:,} coins** is fully paid off through auto-debit.\n"
                                 f"The bank has returned your collateral characters to your harem:\n"
                                 f"🌸 **{char_names}**",
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        pass
                else:
                    new_next_due = current_loan['next_emi_due'] + timedelta(days=1)
                    await db['bank_loans'].update_one(
                        {"loan_id": loan_id},
                        {
                            '$set': {
                                'amount_paid': new_amount_paid,
                                'emis_remaining': new_emis_remaining,
                                'next_emi_due': new_next_due,
                                'bounced_count': 0
                            }
                        }
                    )
                    
                    try:
                        await app.send_message(
                            chat_id=user_id,
                            text=f"💸 **EMI Auto-Debited!**\n\n"
                                 f"An EMI of **{charge_amount:,} coins** has been successfully debited from your balance for loan `{loan_id}`.\n"
                                 f"• **Remaining Debt:** 💰 `{current_loan['total_repayable'] - new_amount_paid:,}` coins\n"
                                 f"• **EMIs Remaining:** `{new_emis_remaining}`\n"
                                 f"• **Next Due:** {new_next_due.strftime('%Y-%m-%d %H:%M UTC')}",
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        pass
            else:
                new_bounces = current_loan['bounced_count'] + 1
                penalty = 500
                new_balance = max(0, balance - penalty)
                
                await user_collection.update_one({'id': user_id}, {'$set': {'balance': new_balance}})
                
                if new_bounces >= 3:
                    collateral_chars = current_loan.get('collateral_characters', [])
                    await db['bank_loans'].update_one(
                        {"loan_id": loan_id},
                        {
                            '$set': {
                                'status': 'defaulted',
                                'bounced_count': new_bounces
                            }
                        }
                    )
                    
                    char_names = ", ".join([c.get('name', 'Unknown') for c in collateral_chars])
                    try:
                        await app.send_message(
                            chat_id=user_id,
                            text=f"🚨 **LOAN DEFAULT & SEIZURE!** 🚨\n\n"
                                 f"Your loan `{loan_id}` has defaulted after **3 consecutive EMI bounces**.\n\n"
                                 f"The bank has **permanently seized** your collateral characters:\n"
                                 f"🌸 **{char_names}**\n\n"
                                 f"These characters are no longer in the bank and cannot be retrieved.",
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        pass
                else:
                    new_next_due = current_loan['next_emi_due'] + timedelta(days=1)
                    await db['bank_loans'].update_one(
                        {"loan_id": loan_id},
                        {
                            '$set': {
                                'bounced_count': new_bounces,
                                'next_emi_due': new_next_due
                            }
                        }
                    )
                    
                    try:
                        await app.send_message(
                            chat_id=user_id,
                            text=f"⚠️ **EMI Auto-Debit BOUNCED!** ⚠️\n\n"
                                 f"Your daily EMI of **{charge_amount:,} coins** for loan `{loan_id}` bounced due to insufficient balance (Current: {balance:,} coins).\n\n"
                                 f"• **Bounce Penalty Charged:** 💰 `{penalty}` coins\n"
                                 f"• **Consecutive Bounces:** `{new_bounces}/3`\n"
                                 f"• **Next Retry:** {new_next_due.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                                 f"🚨 *WARNING: If this bounces 3 times, your collateral will be permanently seized!*",
                            parse_mode=enums.ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        pass

# ----------------- Auth Helpers -----------------

async def get_authed_user(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    init_data = auth_header.split(' ', 1)[1]
    return verify_telegram_webapp_data(init_data, TOKEN)

async def api_options_handler(request):
    return web.Response(
        status=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
        }
    )

async def serve_webapp_html(request):
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "blackmarket.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    else:
        return web.Response(text="<h1>Black Market - Web App Page Not Found</h1>", status=404, content_type='text/html')

# ----------------- Web App Server Startup Hook -----------------

async def start_webapp_server():
    port = int(os.getenv("PORT", 8080))
    app_web = web.Application()
    
    app_web.router.add_options('/api/listings', api_options_handler)
    app_web.router.add_options('/api/harem', api_options_handler)
    app_web.router.add_options('/api/balance', api_options_handler)
    app_web.router.add_options('/api/sell', api_options_handler)
    app_web.router.add_options('/api/buy', api_options_handler)
    app_web.router.add_options('/api/cancel', api_options_handler)
    app_web.router.add_options('/api/bank/loans', api_options_handler)
    app_web.router.add_options('/api/bank/borrow', api_options_handler)
    app_web.router.add_options('/api/bank/repay', api_options_handler)
    
    app_web.router.add_get('/', serve_webapp_html)
    app_web.router.add_get('/blackmarket', serve_webapp_html)
    app_web.router.add_get('/api/listings', api_get_listings)
    app_web.router.add_get('/api/harem', api_get_harem)
    app_web.router.add_get('/api/balance', api_get_balance)
    app_web.router.add_post('/api/sell', api_sell_character)
    app_web.router.add_post('/api/buy', api_buy_character)
    app_web.router.add_post('/api/cancel', api_cancel_listing)
    app_web.router.add_get('/api/bank/loans', api_get_loans)
    app_web.router.add_post('/api/bank/borrow', api_borrow_loan)
    app_web.router.add_post('/api/bank/repay', api_repay_loan)
    
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"=== Black Market Web Server started on port {port} ===")

# Hook into python-telegram-bot application post_init
original_post_init = getattr(application, 'post_init', None)

async def web_server_startup(app_ptb):
    if original_post_init:
        await original_post_init(app_ptb)
    await start_webapp_server()
    asyncio.create_task(run_bank_emi_loop())

application.post_init = web_server_startup
