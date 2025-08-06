import os
import re
import asyncio
from html import escape
from cachetools import TTLCache
from datetime import datetime

# Aiogram imports
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQueryResultPhoto, InlineQueryResultVideo
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Database
from motor.motor_asyncio import AsyncIOMotorClient

# Configuration
TOKEN = os.getenv("TOKEN", "8482718820:AAHm-xeEYJlVCH8-KChlKEaLS_WxvOHQ4i8")
mongo_url = "mongodb+srv://harshmanjhi1801:webapp@cluster0.xxwc4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# Bot and Dispatcher setup
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Database setup
try:
    client = AsyncIOMotorClient(mongo_url)
    db = client['shoreskeeper']
    user_collection = db["user_collection_lmaoooo"]
    collection = db['anime_characters_lol']
except Exception as e:
    raise

# Cache setup
all_characters_cache = TTLCache(maxsize=10000, ttl=300)  # 5 minutes
user_collection_cache = TTLCache(maxsize=10000, ttl=60)   # 1 minute

# Database functions
async def get_user_collection(user_id):
    """Get user collection"""
    user_id_str = str(user_id)
    
    # Check cache first
    if user_id_str in user_collection_cache:
        return user_collection_cache[user_id_str]
    
    try:
        user = await user_collection.find_one({'id': int(user_id)})
        
        if user:
            # Cache the result
            user_collection_cache[user_id_str] = user
        
        return user
        
    except Exception as e:
        return None

async def search_characters(query, force_refresh=False):
    """Search characters"""
    cache_key = f"search_{query.lower()}"
    
    # Check cache
    if not force_refresh and cache_key in all_characters_cache:
        return all_characters_cache[cache_key]
    
    try:
        # Create regex pattern
        regex = re.compile(query, re.IGNORECASE)
        
        # Database search
        search_filter = {
            "$or": [
                {"name": regex},
                {"anime": regex},
                {"aliases": regex}
            ]
        }
        
        characters = await collection.find(search_filter).to_list(length=None)
        
        # Cache results
        all_characters_cache[cache_key] = characters
        
        return characters
        
    except re.error as regex_error:
        return []
    except Exception as e:
        return []

async def get_all_characters(force_refresh=False):
    """Get all characters"""
    # Check cache
    if not force_refresh and 'all_characters' in all_characters_cache:
        return all_characters_cache['all_characters']
    
    try:
        # Database query
        characters = await collection.find({}).to_list(length=None)
        
        # Cache results
        all_characters_cache['all_characters'] = characters
        
        return characters
        
    except Exception as e:
        return []

# Inline query handler
@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery):
    """Main inline query handler"""
    query_id = inline_query.id
    user_id = inline_query.from_user.id
    username = inline_query.from_user.username or "Unknown"
    
    try:
        query = inline_query.query
        offset = int(inline_query.offset) if inline_query.offset else 0
        
        # Determine query type
        is_collection_query = query.startswith('collection.')
        is_amv_query = '.AMV' in query
        
        all_characters = []
        user = None
        
        if is_collection_query:
            try:
                # Parse collection query
                parts = query.split(' ')
                collection_part = parts[0]  # collection.user_id
                search_terms = ' '.join(parts[1:]) if len(parts) > 1 else ''
                
                extracted_user_id = collection_part.split('.')[1]
                
            except Exception as parse_error:
                await inline_query.answer([], cache_time=5)
                return
            
            if extracted_user_id.isdigit():
                # Get user collection
                user = await get_user_collection(extracted_user_id)
                
                if user:
                    # Process user characters
                    raw_characters = user.get('characters', [])
                    
                    # Remove duplicates based on character ID
                    unique_chars = {}
                    for char in raw_characters:
                        if 'id' in char:
                            char_id = char['id']
                            if char_id not in unique_chars:
                                unique_chars[char_id] = char
                                unique_chars[char_id]['count'] = 1
                            else:
                                unique_chars[char_id]['count'] += 1
                    
                    all_characters = list(unique_chars.values())
                    
                    # Apply search filter if provided
                    if search_terms:
                        try:
                            regex = re.compile(search_terms, re.IGNORECASE)
                            filtered_chars = []
                            
                            for char in all_characters:
                                name_match = regex.search(char.get('name', ''))
                                anime_match = regex.search(char.get('anime', ''))
                                
                                if name_match or anime_match:
                                    filtered_chars.append(char)
                            
                            all_characters = filtered_chars
                            
                        except re.error as regex_error:
                            all_characters = []
                else:
                    all_characters = []
            else:
                all_characters = []
        
        else:
            if query.strip():
                all_characters = await search_characters(query)
            else:
                all_characters = await get_all_characters()
        
        # Apply media filter
        original_count = len(all_characters)
        
        if is_amv_query:
            all_characters = [char for char in all_characters if 'vid_url' in char and char.get('vid_url')]
        else:
            all_characters = [char for char in all_characters if 'img_url' in char and char.get('img_url')]
        
        # Pagination
        total_available = len(all_characters)
        characters = all_characters[offset:offset + 50]
        next_offset = str(offset + len(characters)) if len(characters) == 50 and offset + 50 < total_available else None
        
        # Build results
        results = []
        
        for idx, character in enumerate(characters, start=offset + 1):
            try:
                char_id = character.get('id', 'unknown')
                char_name = character.get('name', 'Unknown')
                char_anime = character.get('anime', 'Unknown')
                char_rarity = character.get('rarity', 'Unknown')
                
                # Build caption
                if is_collection_query and user:
                    user_character_count = character.get('count', 1)
                    user_name = escape(user.get('first_name', 'User'))
                    caption = (
                        f"<b>👤 Check out <a href='tg://user?id={user['id']}'>{user_name}</a>'s character:</b>\n\n"
                        f"🌸 <b>{escape(char_name)} (x{user_character_count})</b>\n"
                        f"🏖️ From: <b>{escape(char_anime)}</b>\n"
                        f"🔮 Rarity: <b>{escape(char_rarity)}</b>\n\n"
                        f"🆔️ <b>{char_id}</b>\n\n"
                    )
                else:
                    caption = (
                        f"<b>Discover this amazing character:</b>\n\n"
                        f"🌸 <b>{escape(char_name)}</b>\n"
                        f"🏖️ From: <b>{escape(char_anime)}</b>\n"
                        f"🔮 Rarity: <b>{escape(char_rarity)}</b>\n"
                        f"🆔️ <b>{char_id}</b>\n\n"
                    )
                
                # Create result based on media type
                result_id = f"{char_id}_{int(datetime.now().timestamp() * 1000)}_{idx}"
                
                if is_amv_query and 'vid_url' in character:
                    vid_url = character['vid_url']
                    thumbnail_url = character.get('thum_url', 'https://envs.sh/6Y3.jpg')
                    
                    result = InlineQueryResultVideo(
                        id=result_id,
                        video_url=vid_url,
                        mime_type="video/mp4",
                        thumbnail_url=thumbnail_url,
                        title=char_name,
                        description=f"From: {char_anime} | Rarity: {char_rarity}",
                        caption=caption,
                        parse_mode='HTML'
                    )
                    
                elif 'img_url' in character:
                    img_url = character['img_url']
                    
                    result = InlineQueryResultPhoto(
                        id=result_id,
                        thumbnail_url=img_url,
                        photo_url=img_url,
                        caption=caption,
                        parse_mode='HTML'
                    )
                else:
                    continue
                
                results.append(result)
                
            except Exception as char_error:
                continue
        
        # Send response
        await inline_query.answer(results, next_offset=next_offset, cache_time=5)
        
    except Exception as e:
        # Send empty response on error
        try:
            await inline_query.answer([], cache_time=5)
        except Exception as response_error:
            pass

# Main function
async def main():
    """Main function"""
    try:
        # Start polling
        await dp.start_polling(bot, drop_pending_updates=True)
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        raise

if __name__ == "__main__":
    asyncio.run(main())
