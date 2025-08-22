# TEAMZYRO/help.py

HELP_DATA = {
    "balance": {
        "HELP_NAME": "Bᴀʟ Aɴᴅ Pᴀʏ",
        "HELP": """
💰 **Balance Commands**:
- `/balance` → Check your balance.
- `/balance @username` → Check another user's balance.
- `/balance user_id` → Check balance using user ID.

💳 **Payment Commands**:
- `/pay amount @username` → Send coins to a user.
- `/pay amount user_id` → Send coins using user ID.
- `/pay amount` (reply to a user) → Send coins to the replied user.

⚠ **Note**:
- You must have enough balance to send coins.
- Payments are final and cannot be reversed.
"""
    },
    "check": {
        "HELP_NAME": "Cʜᴇᴄᴋ",
        "HELP": """
Use `/check <character_id>` to view details of a character.

- Displays character ID, name, anime, and rarity.
- Shows an image or video if available.
- Use the 'Who Have It' button to see the top 10 owners.
"""
    },
    "guess": {
        "HELP_NAME": "Gᴜᴇss",
        "HELP": """
Use `/guess <character_name>` to guess the mystery character.

- Earn 40 coins for a correct guess.
- The first correct guess captures the character.
- If incorrect, you can try again.
- A 'See Harem' button lets you view your collected characters.
"""
    },
    "harem": {
        "HELP_NAME": "Hᴀʀᴇᴍ",
        "HELP": """
Use `/harem` or `/collection` to view your collected characters.

- Navigate pages using the buttons.
- Filter by rarity using the filter button.
- Use "Collection" button for detailed inline view.
- "💌 AMV" button shows a video-only collection.

Characters are grouped by anime and show the count you own.
"""
    },
    "inline": {
        "HELP_NAME": "Iɴʟɪɴᴇ",
        "HELP": """
Use inline queries to search for characters or view collections.

- `@Gaming_X_World_Bot query` → Search for characters.
- `@Gaming_X_World_Bot collection.<user_id>` → View a user's character collection.
- `@Gaming_X_World_Bot collection.<user_id> <name>` → Search within a user's collection.
- `@Gaming_X_World_Bot <query>.AMV` → Show characters with video clips.

Results include character name, anime, rarity, and image/video.
"""
    },
    "favorites": {
        "HELP_NAME": "Fᴀᴠᴏʀɪᴛᴇs",
        "HELP": """
Add your favorite characters to your collection.

- `/fav <character_id>` → Add a character to your favorites.
- Click "✅ Yes" to confirm or "❎ No" to cancel.
- Your favorite characters will be saved for quick access.

Note: You can only favorite characters that are in your collection.
"""
    },
    "claim": {
        "HELP_NAME": "Cʟᴀɪᴍ",
        "HELP": """
Claim a free character every day! 🌟

- `/hclaim` or `/claim` → Claim your daily character.
- You must be in the required channel to claim.
- If you've already claimed today, you'll see the time remaining for the next claim.
- Characters are unique and not repeated from your collection.
- Return tomorrow for another claim! 🌸
"""
    },
    "requests": {
        "HELP_NAME": "Rᴇǫᴜᴇsᴛs",
        "HELP": """
Use the following command to request a character:

Request a Character  
`/reqchar <character_id>` - Request a specific character by ID.

Once requested, the owner will review and approve or deny your request.
"""
    },
    "gift": {
        "HELP_NAME": "Gɪғᴛ",
        "HELP": """
🎁 **Gift System**  
Send characters to other users using the `/gift` command.

**Commands:**
- `/gift <character_id>` (Reply to a user's message)  
  ┗ Gift a character to another user.

**How it works:**
1. Reply to a user's message.
2. Use `/gift <character_id>` to send a character.
3. The receiver gets a confirmation message.
4. The gift is auto-canceled if not confirmed within 1 hour.
"""
    },
    "jackpot": {
        "HELP_NAME": "Jᴀᴄᴋᴘᴏᴛ",
        "HELP": """
🎰 **Jackpot Game**  
Try your luck with the jackpot and win coins!

**Commands:**
- `/jackpot`  
  ┗ Roll the slot machine and earn coins.

**How it works:**
1. You can play twice per day.
2. The bot rolls a 🎰 dice.
3. Your winnings depend on the score:
   - 64 → 2000 coins 🎉
   - Other scores → 5 × score coins.
4. Your balance updates automatically.
"""
    },
    "rankings": {
        "HELP_NAME": "Rᴀɴᴋɪɴɢs",
        "HELP": """
🏆 **Rankings & Leaderboards**  
Check out the top users and groups in different categories!

**Commands:**
- `/rank`  
  ┗ View the Top 10 Users with the most characters.

**Categories:**
1. **Top Users** → Users with the highest number of characters.
2. **Top Groups** → Groups that have guessed the most characters.
3. **MTOP** → Users ranked by the highest coin balance.

**How it works:**
- `/rank` will display the top 10 users based on character count.
- You can switch between Top Users, Top Groups, and MTOP using the buttons.
- Rankings update dynamically as users collect characters or earn coins.
"""
    },
    "mines": {
        "HELP_NAME": "Mɪɴᴇs",
        "HELP": """
💣 **Minesweeper Game** 💣  

🎮 **How to Play:**
- Start the game using `/mines`.
- You need **1000 coins** to play.
- A 3×3 grid hides **3 mines**.
- You can survive **1 mine hit**, but the 2nd one ends the game.
- Open safe cells to earn rewards and claim anytime.

🏆 **Rewards:**
- 1 safe cell → 600 coins  
- 2 safe cells → 1200 coins  
- 3 safe cells → 1800 coins  
- 4–5 safe cells → 🎴 Character reward  
- 6 safe cells → 🎴 Character + 2000 coins  

📝 **Commands:**
- `/mines` → Start a new Minesweeper game.
"""
    },
    "sips": {
        "HELP_NAME": "Sɪᴘs",
        "HELP": """
Use this command to search for characters by name.

Commands:
- /sips <character_name> → Search for a character by name.
- Pagination buttons will appear if multiple results are found.

Each result includes:
- Character name
- Anime name
- Character ID
- Rarity indicator
"""
    },
    "shop": {
        "HELP_NAME": "Sʜᴏᴘ",
        "HELP": """
🛒 Shop Commands:
- /shop - Open the shop menu.
- /hshopmenu - Alternative command to open the shop.
- /hshop - Another way to access the shop.
- /addshop <id> <price> - Add a character to the shop (Admin only).

🛍 How It Works:
1. Use /shop to browse characters.
2. Click "Buy" to purchase a character.
3. Click "Next" to view more characters.
4. Make sure you have enough balance!

🔹 Enjoy shopping!
"""
    },
    "new_char": {
        "HELP_NAME": "Nᴇᴡ Cʜᴀʀ",
        "HELP": """
➤ /addchar character-name anime-name - Upload a character with an image.

Admins can approve or reject the request using the provided buttons.

➤ Rarity options:
- ⚪️ Common
- 🟣 Rare
- 🟡 Legendary
- 🟢 Medium
- 💮 Special Edition
- 🔮 Limited Edition
- 🎐 Celestial
- 💖 Valentine
- 🎃 Halloween
- ❄️ Winter
- 🌧 Rainy
- 💸 Expensive
- 👑 V. I. P.

➤ Admin Commands:
- Approve a pending character request.
- Cancel an upload request.

Make sure to reply with an image when using /addchar!
"""
    }
}
