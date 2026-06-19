import asyncio
import traceback
import os
import random
import urllib.parse
import json
import hmac
import hashlib
from datetime import datetime
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
            f"🌸 **{character.get('name', 'Unknown')}** ({character.get('rarity', 'Unknown')})\n"
            f"⛩️ Anime: **{character.get('anime', 'Unknown')}**\n"
            f"💰 Price: **{price:,}** coins\n"
            f"🆔 Listing ID: `{listing_id}`\n\n"
            f"This character has been moved to escrow and won't show in your harem. "
            f"Use `/unsell {listing_id}` to cancel the sale."
        )
        
        if character.get('vid_url'):
            await message.reply_video(video=character['vid_url'], caption=caption, parse_mode=enums.ParseMode.MARKDOWN)
        elif character.get('img_url'):
            await message.reply_photo(photo=character['img_url'], caption=caption, parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await message.reply_text(caption, parse_mode=enums.ParseMode.MARKDOWN)

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
        
        await message.reply_text(
            f"❌ **Listing Cancelled!**\n"
            f"**{character.get('name', 'Unknown')}** has been returned to your harem.",
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
            
            await message.reply_text(
                f"🎉 **Purchase Successful!**\n\n"
                f"You bought **{character.get('name', 'Unknown')}** for **{price:,}** coins from [{seller_name}](tg://user?id={seller_id}).",
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

@app.on_message(filters.command(["bm", "blackmarket"]))
async def black_market_catalog(client, message):
    page = 0
    await display_black_market(client, message, page, is_initial=True)

@app.on_message(filters.command("my_listings"))
async def my_listings_command(client, message):
    user_id = message.from_user.id
    listings = await black_market_collection.find({"seller_id": user_id}).to_list(length=100)
    
    if not listings:
        await message.reply_text("You don't have any active listings in the black market.")
        return
        
    text = "📋 **YOUR BLACK MARKET LISTINGS**\n\n"
    keyboard = []
    for i, listing in enumerate(listings, 1):
        char = listing['character']
        price = listing['price']
        rarity_emoji = rarity_map2.get(char.get('rarity'), '')
        text += (
            f"**{i}.** {rarity_emoji} **{char.get('name', 'Unknown')}**\n"
            f"  Price: 💰 `{price:,}` coins\n"
            f"  Listing ID: `{listing['listing_id']}`\n\n"
        )
        keyboard.append([InlineKeyboardButton(f"❌ Cancel {char.get('name', 'Char')[:12]}...", callback_data=f"bm_cancel_conf:{listing['listing_id']}:0")])
        
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    await message.reply_text(text, reply_markup=reply_markup, parse_mode=enums.ParseMode.MARKDOWN)

# ----------------- Interactive Telegram Interface -----------------

async def display_black_market(client, message_or_query, page, is_initial=False):
    is_callback = not is_initial
    message = message_or_query.message if is_callback else message_or_query
    
    listings = await black_market_collection.find({}).sort("listed_at", -1).to_list(length=100)
    
    if not listings:
        text = "🛒 **SHOREKEEPER BLACK MARKET**\n\nThere are no active listings at the moment."
        webapp_url = os.getenv("WEBAPP_URL")
        keyboard = []
        if webapp_url:
            keyboard.append([InlineKeyboardButton("🛒 Open Web App", web_app=WebAppInfo(url=f"{webapp_url}/blackmarket"))])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
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
            f"**{idx}.** {rarity_emoji} **{char.get('name', 'Unknown')}**\n"
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
        
    webapp_url = os.getenv("WEBAPP_URL")
    if webapp_url:
        keyboard.append([InlineKeyboardButton("🛒 Open Web App", web_app=WebAppInfo(url=f"{webapp_url}/blackmarket"))])
        
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
        f"🌸 **{char.get('name', 'Unknown')}**\n"
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
                f"You have bought **{character.get('name', 'Unknown')}** for **{price:,}** coins from [{seller_name}](tg://user?id={seller_id})!",
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
            return mongo_json_response({"success": true, "listing_id": listing_id})
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
                        text=f"💰 **Character Sold!**\n\nYour character **{character.get('name', 'Unknown')}** was bought by [{buyer_name}](tg://user?id={buyer_id}) for **{price:,}** coins!",
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                except Exception:
                    pass
                    
                return mongo_json_response({"success": true})
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
            return mongo_json_response({"success": true})
    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server Error: {str(e)}"}, status=500)

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
    
    app_web.router.add_get('/', serve_webapp_html)
    app_web.router.add_get('/blackmarket', serve_webapp_html)
    app_web.router.add_get('/api/listings', api_get_listings)
    app_web.router.add_get('/api/harem', api_get_harem)
    app_web.router.add_get('/api/balance', api_get_balance)
    app_web.router.add_post('/api/sell', api_sell_character)
    app_web.router.add_post('/api/buy', api_buy_character)
    app_web.router.add_post('/api/cancel', api_cancel_listing)
    
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

application.post_init = web_server_startup
