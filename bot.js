const TelegramBot = require('node-telegram-bot-api');
const { MongoClient } = require('mongodb');
const NodeCache = require('node-cache');

// Configuration
const TOKEN = process.env.TOKEN || "8482718820:AAHm-xeEYJlVCH8-KChlKEaLS_WxvOHQ4i8";
const MONGO_URL = "mongodb+srv://I-LOVE-PDF-BOT:I-LOVE-PDF-BOT@cluster0.c51o3a9.mongodb.net/?retryWrites=true&w=majority";

// Bot setup
const bot = new TelegramBot(TOKEN, { polling: true });

// Database setup
let db, userCollection, charactersCollection;

// Cache setup
const allCharactersCache = new NodeCache({ stdTTL: 300 }); // 5 minutes
const userCollectionCache = new NodeCache({ stdTTL: 60 });  // 1 minute

const http = require('http');

const PORT = process.env.PORT || 3000;
http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/plain' });
  res.end('Bot is running!\n');
}).listen(PORT, () => {
  console.log(`Web server listening on port ${PORT}`);
});


// Initialize MongoDB connection
async function initDatabase() {
    try {
        const client = new MongoClient(MONGO_URL);
        await client.connect();
        console.log('Connected to MongoDB');
        
        db = client.db('waifu_collector_bot');
        userCollection = db.collection('user_collection_lmaoooo');
        charactersCollection = db.collection('anime_characters_lol');
    } catch (error) {
        console.error('Database connection error:', error);
        throw error;
    }
}

// Database functions
async function getUserCollection(userId) {
    const userIdStr = userId.toString();
    
    // Check cache first
    const cached = userCollectionCache.get(userIdStr);
    if (cached) {
        return cached;
    }
    
    try {
        const user = await userCollection.findOne({ id: parseInt(userId) });
        
        if (user) {
            // Cache the result
            userCollectionCache.set(userIdStr, user);
        }
        
        return user;
    } catch (error) {
        console.error('Error getting user collection:', error);
        return null;
    }
}

async function searchCharacters(query, forceRefresh = false) {
    const cacheKey = `search_${query.toLowerCase()}`;
    
    // Check cache
    if (!forceRefresh) {
        const cached = allCharactersCache.get(cacheKey);
        if (cached) {
            return cached;
        }
    }
    
    try {
        // Create regex pattern
        const regex = new RegExp(query, 'i');
        
        // Database search
        const searchFilter = {
            $or: [
                { name: regex },
                { anime: regex },
                { aliases: regex }
            ]
        };
        
        const characters = await charactersCollection.find(searchFilter).toArray();
        
        // Cache results
        allCharactersCache.set(cacheKey, characters);
        
        return characters;
    } catch (error) {
        console.error('Error searching characters:', error);
        return [];
    }
}

async function getAllCharacters(forceRefresh = false) {
    // Check cache
    if (!forceRefresh) {
        const cached = allCharactersCache.get('all_characters');
        if (cached) {
            return cached;
        }
    }
    
    try {
        // Database query
        const characters = await charactersCollection.find({}).toArray();
        
        // Cache results
        allCharactersCache.set('all_characters', characters);
        
        return characters;
    } catch (error) {
        console.error('Error getting all characters:', error);
        return [];
    }
}

// Utility functions
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Inline query handler
bot.on('inline_query', async (query) => {
    const queryId = query.id;
    const userId = query.from.id;
    const username = query.from.username || 'Unknown';
    
    try {
        const queryText = query.query;
        const offset = parseInt(query.offset) || 0;
        
        // Determine query type
        const isCollectionQuery = queryText.startsWith('collection.');
        const isAmvQuery = queryText.includes('.AMV');
        
        let allCharacters = [];
        let user = null;
        
        if (isCollectionQuery) {
            try {
                // Parse collection query
                const parts = queryText.split(' ');
                const collectionPart = parts[0]; // collection.user_id
                const searchTerms = parts.slice(1).join(' ');
                
                const extractedUserId = collectionPart.split('.')[1];
                
                if (/^\d+$/.test(extractedUserId)) {
                    // Get user collection
                    user = await getUserCollection(extractedUserId);
                    
                    if (user) {
                        // Process user characters
                        const rawCharacters = user.characters || [];
                        
                        // Remove duplicates based on character ID
                        const uniqueChars = {};
                        for (const char of rawCharacters) {
                            if (char.id) {
                                const charId = char.id;
                                if (!uniqueChars[charId]) {
                                    uniqueChars[charId] = { ...char, count: 1 };
                                } else {
                                    uniqueChars[charId].count += 1;
                                }
                            }
                        }
                        
                        allCharacters = Object.values(uniqueChars);
                        
                        // Apply search filter if provided
                        if (searchTerms) {
                            try {
                                const regex = new RegExp(searchTerms, 'i');
                                allCharacters = allCharacters.filter(char => {
                                    const nameMatch = regex.test(char.name || '');
                                    const animeMatch = regex.test(char.anime || '');
                                    return nameMatch || animeMatch;
                                });
                            } catch (regexError) {
                                allCharacters = [];
                            }
                        }
                    } else {
                        allCharacters = [];
                    }
                } else {
                    allCharacters = [];
                }
            } catch (parseError) {
                await bot.answerInlineQuery(queryId, [], { cache_time: 5 });
                return;
            }
        } else {
            if (queryText.trim()) {
                allCharacters = await searchCharacters(queryText);
            } else {
                allCharacters = await getAllCharacters();
            }
        }
        
        // Apply media filter
        if (isAmvQuery) {
            allCharacters = allCharacters.filter(char => char.vid_url);
        } else {
            allCharacters = allCharacters.filter(char => char.img_url);
        }
        
        // Pagination
        const totalAvailable = allCharacters.length;
        const characters = allCharacters.slice(offset, offset + 50);
        const nextOffset = (characters.length === 50 && offset + 50 < totalAvailable) 
            ? (offset + characters.length).toString() 
            : null;
        
        // Build results
        const results = [];
        
        for (let idx = 0; idx < characters.length; idx++) {
            try {
                const character = characters[idx];
                const charId = character.id || 'unknown';
                const charName = character.name || 'Unknown';
                const charAnime = character.anime || 'Unknown';
                const charRarity = character.rarity || 'Unknown';
                
                // Build caption
                let caption;
                if (isCollectionQuery && user) {
                    const userCharacterCount = character.count || 1;
                    const userName = escapeHtml(user.first_name || 'User');
                    caption = `<b>👤 Check out <a href='tg://user?id=${user.id}'>${userName}</a>'s character:</b>\n\n` +
                             `🌸 <b>${escapeHtml(charName)} (x${userCharacterCount})</b>\n` +
                             `🏖️ From: <b>${escapeHtml(charAnime)}</b>\n` +
                             `🔮 Rarity: <b>${escapeHtml(charRarity)}</b>\n\n` +
                             `🆔️ <b>${charId}</b>\n\n`;
                } else {
                    caption = `<b>Discover this amazing character:</b>\n\n` +
                             `🌸 <b>${escapeHtml(charName)}</b>\n` +
                             `🏖️ From: <b>${escapeHtml(charAnime)}</b>\n` +
                             `🔮 Rarity: <b>${escapeHtml(charRarity)}</b>\n` +
                             `🆔️ <b>${charId}</b>\n\n`;
                }
                
                // Create result based on media type
                const resultId = `${charId}_${Date.now()}_${offset + idx + 1}`;
                
                let result;
                if (isAmvQuery && character.vid_url) {
                    const vidUrl = character.vid_url;
                    const thumbnailUrl = character.thum_url || 'https://envs.sh/6Y3.jpg';
                    
                    result = {
                        type: 'video',
                        id: resultId,
                        video_url: vidUrl,
                        mime_type: 'video/mp4',
                        thumb_url: thumbnailUrl,
                        title: charName,
                        description: `From: ${charAnime} | Rarity: ${charRarity}`,
                        caption: caption,
                        parse_mode: 'HTML'
                    };
                } else if (character.img_url) {
                    const imgUrl = character.img_url;
                    
                    result = {
                        type: 'photo',
                        id: resultId,
                        photo_url: imgUrl,
                        thumb_url: imgUrl,
                        caption: caption,
                        parse_mode: 'HTML'
                    };
                } else {
                    continue;
                }
                
                results.push(result);
            } catch (charError) {
                console.error('Error processing character:', charError);
                continue;
            }
        }
        
        // Send response
        await bot.answerInlineQuery(queryId, results, {
            next_offset: nextOffset,
            cache_time: 5
        });
        
    } catch (error) {
        console.error('Inline query error:', error);
        // Send empty response on error
        try {
            await bot.answerInlineQuery(queryId, [], { cache_time: 5 });
        } catch (responseError) {
            console.error('Error sending empty response:', responseError);
        }
    }
});

// Error handling
bot.on('error', (error) => {
    console.error('Bot error:', error);
});

bot.on('polling_error', (error) => {
    console.error('Polling error:', error);
});

// Main function
async function main() {
    try {
        console.log('Initializing database...');
        await initDatabase();
        
        console.log('Starting bot...');
        console.log('Bot is running...');
        
        // Keep the process alive
        process.on('SIGINT', () => {
            console.log('Shutting down bot...');
            bot.stopPolling();
            process.exit(0);
        });
        
    } catch (error) {
        console.error('Failed to start bot:', error);
        process.exit(1);
    }
}

// Start the bot
if (require.main === module) {
    main();
}

module.exports = { bot, main };
