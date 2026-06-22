import os
import time
import random
import asyncio
import traceback
from aiohttp import web
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from TEAMZYRO import app, db, user_collection, application
from TEAMZYRO.modules.blackmarket import get_authed_user, mongo_json_response, get_user_lock
import chess

# Database collections
chess_games = db["chess_games"]
chess_stats = db["chess_stats"]

# Betting limits
MIN_BET = 100
MAX_BET = 100000
MOVE_TIMEOUT = 180  # 3 minutes in seconds

# Balance helpers
async def get_balance(user_id: int) -> int:
    user_data = await user_collection.find_one({'id': user_id}, {'balance': 1})
    if user_data:
        return user_data.get('balance', 0)
    return 0

async def update_balance(user_id: int, amount: int):
    await user_collection.update_one(
        {'id': user_id},
        {'$inc': {'balance': amount}},
        upsert=True
    )

# ── TELEGRAM COMMANDS ──────────────────────────────────────────────────

@app.on_message(filters.command("chess"))
async def host_chess_game(client, message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name

    args = message.command
    if len(args) < 2:
        await message.reply_text(
            "♟️ **Chess Betting Game**\n\n"
            "Host a game: `/chess <bet_amount>`\n"
            "Example: `/chess 1000`\n\n"
            f"⚠️ Min Bet: {MIN_BET:,} | Max Bet: {MAX_BET:,} coins"
        )
        return

    try:
        bet = int(args[1])
    except ValueError:
        await message.reply_text("❌ **Bet amount must be a positive number!**")
        return

    if bet < MIN_BET or bet > MAX_BET:
        await message.reply_text(f"❌ **Bet amount must be between {MIN_BET:,} and {MAX_BET:,} coins!**")
        return

    # Check if user already has an active chess lobby or game running
    existing = await chess_games.find_one({
        "status": {"$in": ["lobby", "playing"]},
        "$or": [{"player_white": user_id}, {"player_black": user_id}]
    })
    if existing:
        await message.reply_text("❌ **You already have an active chess match or lobby!**\nPlease finish it first.")
        return

    # Check balance
    balance = await get_balance(user_id)
    if balance < bet:
        await message.reply_text(f"❌ **You do not have enough coins!**\nYour balance: `{balance:,}` coins.")
        return

    # Deduct bet upfront
    await update_balance(user_id, -bet)

    # Insert game state
    game_id = str(int(time.time() * 1000))
    game_data = {
        "game_id": game_id,
        "player_white": user_id,
        "player_white_name": first_name,
        "player_black": None,
        "player_black_name": None,
        "bet": bet,
        "prize_pool": bet * 2,
        "board_fen": chess.Board().fen(),
        "turn": user_id,  # White plays first
        "status": "lobby",
        "created_at": time.time(),
        "last_move_at": time.time(),
        "chat_id": message.chat.id,
        "message_id": None,
        "player_white_last_seen": time.time(),
        "player_black_last_seen": 0.0,
        "move_history": []
    }
    await chess_games.insert_one(game_data)

    lobby_text = (
        "♟️ **Chess Match Lobby**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Host (White):** {first_name}\n"
        f"💰 **Bet:** <code>{bet:,}</code> Coins\n\n"
        "⏳ *Waiting for an opponent to join...*"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Join Game", callback_data=f"join_chess_{game_id}"),
            InlineKeyboardButton("❌ Cancel Match", callback_data=f"cancel_chess_{game_id}")
        ]
    ])

    sent_message = await message.reply_text(
        text=lobby_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard
    )

    await chess_games.update_one(
        {"game_id": game_id},
        {"$set": {"message_id": sent_message.id}}
    )


# ── CALLBACK HANDLERS ──────────────────────────────────────────────────

@app.on_callback_query(filters.regex(r"^join_chess_(\w+)"))
async def join_chess_callback(client, callback_query):
    user_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name
    game_id = callback_query.data.split("_")[2]

    game = await chess_games.find_one({"game_id": game_id})
    if not game:
        await callback_query.answer("Game not found!", show_alert=True)
        return

    if game["status"] != "lobby":
        await callback_query.answer("This game has already started or been cancelled!", show_alert=True)
        return

    if game["player_white"] == user_id:
        await callback_query.answer("You cannot join your own game!", show_alert=True)
        return

    # Check active limits
    existing = await chess_games.find_one({
        "status": {"$in": ["lobby", "playing"]},
        "$or": [{"player_white": user_id}, {"player_black": user_id}]
    })
    if existing:
        await callback_query.answer("You are already in an active game or lobby!", show_alert=True)
        return

    # Check balance
    bet = game["bet"]
    balance = await get_balance(user_id)
    if balance < bet:
        await callback_query.answer(f"Insufficient coins! You need {bet:,} coins.", show_alert=True)
        return

    # Deduct bet
    await update_balance(user_id, -bet)

    # Start game
    await chess_games.update_one(
        {"game_id": game_id},
        {
            "$set": {
                "player_black": user_id,
                "player_black_name": first_name,
                "status": "playing",
                "last_move_at": time.time(),
                "player_black_last_seen": time.time()
            }
        }
    )

    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    # startapp URL
    play_url = f"https://t.me/{bot_username}?startapp=chess_{game_id}"

    started_text = (
        "⚔️ **Chess Match Started!**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚪️ **White:** {game['player_white_name']}\n"
        f"⚫️ **Black:** {first_name}\n"
        f"💰 **Prize Pool:** <code>{game['prize_pool']:,}</code> Coins\n\n"
        "Click the button below to join the room and play in the Mini Web App!"
    )

    play_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Join Chess Room", url=play_url)]
    ])

    await callback_query.message.edit_text(
        text=started_text,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=play_keyboard
    )
    await callback_query.answer("Match joined! Let's play chess!")


@app.on_callback_query(filters.regex(r"^cancel_chess_(\w+)"))
async def cancel_chess_callback(client, callback_query):
    user_id = callback_query.from_user.id
    game_id = callback_query.data.split("_")[2]

    game = await chess_games.find_one({"game_id": game_id})
    if not game:
        await callback_query.answer("Game not found!", show_alert=True)
        return

    if game["status"] != "lobby":
        await callback_query.answer("This game cannot be cancelled anymore!", show_alert=True)
        return

    if game["player_white"] != user_id:
        await callback_query.answer("Only the host can cancel this game!", show_alert=True)
        return

    # Refund host
    await chess_games.update_one(
        {"game_id": game_id},
        {"$set": {"status": "cancelled"}}
    )
    await update_balance(user_id, game["bet"])

    await callback_query.message.edit_text(
        f"❌ **Chess Match Cancelled**\nNo opponent joined. Host {game['player_white_name']} refunded."
    )
    await callback_query.answer("Lobby cancelled. Bet refunded.")


# ── WEB APP ENDPOINTS ──────────────────────────────────────────────────

async def api_get_chess_game(request):
    try:
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
        
        user_id = user_info['id']
        game_id = request.query.get('game_id')
        if not game_id:
            return mongo_json_response({"error": "Missing game_id"}, status=400)

        game = await chess_games.find_one({"game_id": game_id})
        if not game:
            return mongo_json_response({"error": "Game not found"}, status=404)

        # Enforce room access: only white and black players allowed
        if user_id != game['player_white'] and user_id != game['player_black']:
            return mongo_json_response({"error": "You are not a player in this room!"}, status=403)

        current_time = time.time()
        
        # Update last seen timestamps for connection tracking
        update_field = {}
        if user_id == game['player_white']:
            update_field["player_white_last_seen"] = current_time
            game["player_white_last_seen"] = current_time
        elif user_id == game['player_black']:
            update_field["player_black_last_seen"] = current_time
            game["player_black_last_seen"] = current_time

        if update_field:
            await chess_games.update_one({"game_id": game_id}, {"$set": update_field})

        # Calculate connection statuses
        white_connected = (current_time - game.get("player_white_last_seen", 0)) < 12
        black_connected = (current_time - game.get("player_black_last_seen", 0)) < 12

        # Format FEN and details
        response_data = {
            "game_id": game["game_id"],
            "player_white": game["player_white"],
            "player_white_name": game["player_white_name"],
            "player_black": game["player_black"],
            "player_black_name": game["player_black_name"],
            "bet": game["bet"],
            "prize_pool": game["prize_pool"],
            "board_fen": game["board_fen"],
            "turn": game["turn"],
            "status": game["status"],
            "winner": game.get("winner"),
            "winner_name": game.get("winner_name"),
            "last_move_at": game["last_move_at"],
            "move_history": game.get("move_history", []),
            "white_connected": white_connected,
            "black_connected": black_connected,
            "server_time": current_time,
            "time_remaining": max(0, MOVE_TIMEOUT - (current_time - game["last_move_at"]))
        }
        return mongo_json_response(response_data)

    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server error: {str(e)}"}, status=500)


async def api_make_chess_move(request):
    try:
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
        
        user_id = user_info['id']
        try:
            body = await request.json()
            game_id = body.get('game_id')
            move_uci = body.get('move_uci')
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)

        if not game_id or not move_uci:
            return mongo_json_response({"error": "Missing game_id or move_uci"}, status=400)

        async with get_user_lock(user_id):
            game = await chess_games.find_one({"game_id": game_id, "status": "playing"})
            if not game:
                return mongo_json_response({"error": "Game not found or has already ended"}, status=404)

            # Check if it is the user's turn
            if game["turn"] != user_id:
                return mongo_json_response({"error": "It is not your turn!"}, status=400)

            # Validate chess move using python-chess library
            board = chess.Board(game["board_fen"])
            try:
                move = chess.Move.from_uci(move_uci)
            except Exception:
                return mongo_json_response({"error": "Invalid move format"}, status=400)

            if move not in board.legal_moves:
                # Try parsing SAN or check promotion
                return mongo_json_response({"error": "Illegal chess move!"}, status=400)

            # Execute move
            board.push(move)
            
            # Check game end criteria
            status = "playing"
            winner_id = None
            winner_name = None
            ended_reason = ""

            if board.is_checkmate():
                status = "ended"
                winner_id = user_id
                winner_name = user_info['first_name']
                ended_reason = "checkmate"
            elif board.is_stalemate():
                status = "ended"
                winner_id = "draw"
                ended_reason = "stalemate"
            elif board.is_insufficient_material():
                status = "ended"
                winner_id = "draw"
                ended_reason = "insufficient material"
            elif board.is_seventyfive_moves() or board.is_fivefold_repetition():
                status = "ended"
                winner_id = "draw"
                ended_reason = "repetition / 75-moves rule"

            next_turn = game["player_black"] if user_id == game["player_white"] else game["player_white"]
            history = game.get("move_history", [])
            history.append(move_uci)

            # Update DB
            update_data = {
                "board_fen": board.fen(),
                "turn": next_turn,
                "last_move_at": time.time(),
                "move_history": history
            }

            if status == "ended":
                update_data["status"] = "ended"
                update_data["winner"] = winner_id
                update_data["winner_name"] = winner_name
                
                # Perform payouts
                if winner_id == "draw":
                    # Refund both players
                    await update_balance(game["player_white"], game["bet"])
                    await update_balance(game["player_black"], game["bet"])
                    await record_stats(game["player_white"], game["player_white_name"], "draw")
                    await record_stats(game["player_black"], game["player_black_name"], "draw")
                else:
                    # Payout winner
                    await update_balance(winner_id, game["prize_pool"])
                    loser_id = game["player_black"] if winner_id == game["player_white"] else game["player_white"]
                    loser_name = game["player_black_name"] if winner_id == game["player_white"] else game["player_white_name"]
                    await record_stats(winner_id, winner_name, "win")
                    await record_stats(loser_id, loser_name, "loss")

            await chess_games.update_one({"game_id": game_id}, {"$set": update_data})

            # Telegram notification
            if status == "ended":
                try:
                    if winner_id == "draw":
                        msg_text = (
                            "🤝 **Chess Draw!**\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            f"The chess match between **{game['player_white_name']}** and **{game['player_black_name']}** ended in a **Draw** ({ended_reason}).\n"
                            f"💰 {game['bet']:,} coins have been refunded to both players."
                        )
                    else:
                        msg_text = (
                            "🏆 **Chess Match Winner!**\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            f"🎉 Congratulations to **{winner_name}** for winning the chess match by checkmate!\n"
                            f"💰 **Prize Pool Awarded:** `{game['prize_pool']:,}` coins."
                        )
                    await app.send_message(chat_id=game["chat_id"], text=msg_text)
                except Exception:
                    pass

            return mongo_json_response({"success": True})

    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server error: {str(e)}"}, status=500)


async def api_surrender_chess_game(request):
    try:
        user_info = await get_authed_user(request)
        if not user_info:
            return mongo_json_response({"error": "Unauthorized"}, status=401)
        
        user_id = user_info['id']
        try:
            body = await request.json()
            game_id = body.get('game_id')
        except Exception:
            return mongo_json_response({"error": "Invalid request body"}, status=400)

        if not game_id:
            return mongo_json_response({"error": "Missing game_id"}, status=400)

        async with get_user_lock(user_id):
            game = await chess_games.find_one({"game_id": game_id, "status": "playing"})
            if not game:
                return mongo_json_response({"error": "Game not found or has already ended"}, status=404)

            # Check if user is player
            if user_id != game["player_white"] and user_id != game["player_black"]:
                return mongo_json_response({"error": "You are not a player in this match"}, status=400)

            # Surrender logic
            winner_id = game["player_black"] if user_id == game["player_white"] else game["player_white"]
            winner_name = game["player_black_name"] if user_id == game["player_white"] else game["player_white_name"]
            loser_name = game["player_white_name"] if user_id == game["player_white"] else game["player_black_name"]

            await chess_games.update_one(
                {"game_id": game_id},
                {
                    "$set": {
                        "status": "ended",
                        "winner": winner_id,
                        "winner_name": winner_name
                    }
                }
            )

            # Payout
            await update_balance(winner_id, game["prize_pool"])
            await record_stats(winner_id, winner_name, "win")
            await record_stats(user_id, loser_name, "loss")

            try:
                msg_text = (
                    "🏳️ **Chess Surrender!**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"**{loser_name}** has surrendered the match.\n"
                    f"🏆 **Winner:** {winner_name}\n"
                    f"💰 **Prize Pool Awarded:** `{game['prize_pool']:,}` coins."
                )
                await app.send_message(chat_id=game["chat_id"], text=msg_text)
            except Exception:
                pass

            return mongo_json_response({"success": True})

    except Exception as e:
        traceback.print_exc()
        return mongo_json_response({"error": f"Server error: {str(e)}"}, status=500)


# Record stats helper
async def record_stats(user_id, first_name, result):
    inc_dict = {}
    if result == "win":
        inc_dict["wins"] = 1
    elif result == "loss":
        inc_dict["losses"] = 1
    elif result == "draw":
        inc_dict["draws"] = 1

    await chess_stats.update_one(
        {"_id": user_id},
        {"$set": {"first_name": first_name}, "$inc": inc_dict},
        upsert=True
    )


# ── TIMEOUT MONITORING LOOP ──────────────────────────────────────────

async def chess_timeout_loop():
    print("=== Chess Timeout Monitoring Loop Started ===")
    while True:
        try:
            await asyncio.sleep(10)
            current_time = time.time()

            # 1. Cancel empty lobbies after 5 minutes (300 seconds)
            expired_lobbies = chess_games.find({
                "status": "lobby",
                "created_at": {"$lt": current_time - 300}
            })
            async for lobby in expired_lobbies:
                await chess_games.update_one(
                    {"game_id": lobby["game_id"]},
                    {"$set": {"status": "cancelled"}}
                )
                await update_balance(lobby["player_white"], lobby["bet"])
                
                try:
                    await app.edit_message_text(
                        chat_id=lobby["chat_id"],
                        message_id=lobby["message_id"],
                        text=f"❌ **Chess Match Cancelled**\nNo opponent joined. Host {lobby['player_white_name']} refunded."
                    )
                except Exception:
                    pass

            # 2. Timeout active games if turn exceeds MOVE_TIMEOUT
            afk_games = chess_games.find({
                "status": "playing",
                "last_move_at": {"$lt": current_time - MOVE_TIMEOUT}
            })
            async for active_game in afk_games:
                afk_player_id = active_game["turn"]
                winner_id = active_game["player_black"] if afk_player_id == active_game["player_white"] else active_game["player_white"]
                winner_name = active_game["player_black_name"] if afk_player_id == active_game["player_white"] else active_game["player_white_name"]
                afk_player_name = active_game["player_white_name"] if afk_player_id == active_game["player_white"] else active_game["player_black_name"]

                # Declare win due to timeout
                await chess_games.update_one(
                    {"game_id": active_game["game_id"]},
                    {
                        "$set": {
                            "status": "ended",
                            "winner": winner_id,
                            "winner_name": winner_name
                        }
                    }
                )

                # Winnings payout
                await update_balance(winner_id, active_game["prize_pool"])
                await record_stats(winner_id, winner_name, "win")
                await record_stats(afk_player_id, afk_player_name, "loss")

                try:
                    timeout_text = (
                        "⏰ **Chess Move Timeout!**\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"**{afk_player_name}** exceeded the move time limit of {MOVE_TIMEOUT // 60} minutes.\n\n"
                        f"🏆 **Winner:** {winner_name}\n"
                        f"💰 **Prize Pool Awarded:** `{active_game['prize_pool']:,}` coins."
                    )
                    
                    # Edit the started message inline if possible, or send a new message
                    await app.send_message(chat_id=active_game["chat_id"], text=timeout_text)
                except Exception:
                    pass

        except Exception as e:
            print(f"Error in chess_timeout_loop: {e}")


# Hook into python-telegram-bot application post_init to schedule task safely inside the event loop
original_post_init = getattr(application, 'post_init', None)

async def chess_post_init(app_ptb):
    if original_post_init:
        await original_post_init(app_ptb)
    asyncio.create_task(chess_timeout_loop())

application.post_init = chess_post_init
