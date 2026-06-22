import asyncio
import traceback
import os
import sys
import random
import json
import urllib.parse
from datetime import datetime, timedelta
from aiohttp import web
from bson import ObjectId

# Setup python-chess path
chess_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "python-chess"))
if chess_path not in sys.path:
    sys.path.insert(0, chess_path)

import chess

from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from TEAMZYRO import app, user_collection, db, TOKEN, ZYRO

# Collections
chess_rooms_collection = db['chess_rooms']

# In-memory connection manager for WebSocket connections
# room_id -> { "white": ws_conn, "black": ws_conn }
active_connections = {}

# User lock to prevent balance race conditions
user_locks = {}

def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]

# ----------------- Helper Functions -----------------

def verify_telegram_webapp_data(init_data: str, bot_token: str) -> dict:
    """
    Import/Re-implement verification of Telegram Mini App authorization.
    Imported at runtime to prevent dependency cycles.
    """
    try:
        from TEAMZYRO.modules.blackmarket import verify_telegram_webapp_data as verify_bm
        return verify_bm(init_data, bot_token)
    except Exception:
        # Fallback inline validation
        import hmac
        import hashlib
        if not init_data:
            return None
        if init_data.startswith("debug_"):
            try:
                debug_id = int(init_data.split("_")[2])
            except (ValueError, IndexError):
                debug_id = 7078181502
            return {"id": debug_id, "first_name": "DebugUser", "username": "debug_user"}
        try:
            parsed_data = dict(urllib.parse.parse_qsl(init_data))
            if 'hash' not in parsed_data:
                return None
            received_hash = parsed_data['hash']
            sorted_keys = sorted([k for k in parsed_data.keys() if k != 'hash'])
            data_check_string = '\n'.join([f"{k}={parsed_data[k]}" for k in sorted_keys])
            secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
            calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
            if calculated_hash == received_hash:
                return json.loads(parsed_data['user'])
        except Exception:
            pass
        return None

def get_webapp_url():
    url = os.getenv("CHESS_WEBAPP_URL") or os.getenv("WEBAPP_URL")
    if not url:
        port = int(os.getenv("PORT", 8080))
        url = f"http://localhost:{port}"
    return url.rstrip('/')

# ----------------- Bot Command Handler -----------------

@app.on_message(filters.command("chess"))
async def start_chess_challenge(client, message):
    user_id = message.from_user.id
    args = message.command
    
    if len(args) < 2:
        await message.reply_text(
            "♟️ <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧</b>\n\n"
            "Challenge someone to a real-time chess match!\n"
            "<blockquote>🎮 <b>How to Play:</b>\n"
            "Use <code>/chess &lt;bet_amount&gt;</code>\n"
            "Example: <code>/chess 500</code>\n\n"
            "⚠️ Min bet: 100 coins</blockquote>",
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        return

    try:
        bet = int(args[1])
        if bet < 100:
            await message.reply_text("❌ Bet amount must be at least 100 coins!", quote=True)
            return
    except ValueError:
        await message.reply_text("❌ Please enter a valid number for the bet amount!", quote=True)
        return

    # Check user balance
    user_data = await user_collection.find_one({"id": user_id})
    if not user_data or user_data.get("balance", 0) < bet:
        await message.reply_text("❌ You do not have enough coins to start this chess match!", quote=True)
        return

    # Generate unique 6-digit room code
    while True:
        room_id = "".join(random.choices("0123456789", k=6))
        existing = await chess_rooms_collection.find_one({"room_id": room_id})
        if not existing:
            break

    room_doc = {
        "room_id": room_id,
        "chat_id": message.chat.id,
        "message_id": None,
        "creator_id": user_id,
        "creator_name": message.from_user.first_name or "Challenger",
        "joiner_id": None,
        "joiner_name": None,
        "bet": bet,
        "board_state": chess.STARTING_FEN,
        "move_history": [],
        "white_player": None,
        "black_player": None,
        "white_name": "",
        "black_name": "",
        "white_time": 600.0, # 10 minutes default
        "black_time": 600.0,
        "active_turn": "white",
        "last_move_at": None,
        "status": "waiting",
        "created_at": datetime.utcnow()
    }
    
    await chess_rooms_collection.insert_one(room_doc)

    text = (
        f"♟️ <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 𝖢𝖧𝖠𝖫𝖫𝖤𝖭𝖦𝖤</b>\n\n"
        f"👤 <b>Challenger:</b> {message.from_user.mention}\n"
        f"💰 <b>Bet Amount:</b> <code>{bet:,}</code> coins\n\n"
        f"<i>Click the button below to join the match! Both players' bets will be escrowed.</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤝 Join Match", callback_data=f"chess_join:{room_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"chess_cancel:{room_id}")
        ]
    ])
    
    sent_msg = await message.reply_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)
    await chess_rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"message_id": sent_msg.id}}
    )

# ----------------- Inline Button Callback Handlers -----------------

@app.on_callback_query(filters.regex(r"^chess_cancel:"))
async def on_chess_cancel(client, callback_query):
    room_id = callback_query.data.split(":")[1]
    user_id = callback_query.from_user.id
    
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room:
        await callback_query.answer("Match not found!", show_alert=True)
        return
        
    if room["creator_id"] != user_id:
        await callback_query.answer("Only the creator can cancel this match!", show_alert=True)
        return
        
    if room["status"] != "waiting":
        await callback_query.answer("Match already started or finished!", show_alert=True)
        return
        
    await chess_rooms_collection.delete_one({"room_id": room_id})
    await callback_query.answer("Match cancelled successfully!", show_alert=True)
    await callback_query.message.edit_text(
        f"❌ <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 𝖢𝖠𝖭𝖢𝖤𝖫𝖫𝖤𝖣</b>\n\n"
        f"Match challenge cancelled by {callback_query.from_user.mention}.",
        parse_mode=enums.ParseMode.HTML
    )

@app.on_callback_query(filters.regex(r"^chess_join:"))
async def on_chess_join(client, callback_query):
    room_id = callback_query.data.split(":")[1]
    joiner_id = callback_query.from_user.id
    joiner_name = callback_query.from_user.first_name or "Opponent"
    
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room:
        await callback_query.answer("Match not found!", show_alert=True)
        return
        
    if room["status"] != "waiting":
        await callback_query.answer("Match has already been joined or cancelled!", show_alert=True)
        return
        
    creator_id = room["creator_id"]
    creator_name = room["creator_name"]
    bet = room["bet"]
    
    if joiner_id == creator_id:
        await callback_query.answer("You cannot join your own chess challenge!", show_alert=True)
        return

    # Lock both users to avoid double spending
    lock1, lock2 = min(creator_id, joiner_id), max(creator_id, joiner_id)
    
    async with get_user_lock(lock1):
        async with get_user_lock(lock2):
            # Fetch latest data
            creator = await user_collection.find_one({"id": creator_id})
            joiner = await user_collection.find_one({"id": joiner_id})
            
            if not creator or creator.get("balance", 0) < bet:
                await callback_query.answer("Challenger no longer has enough balance!", show_alert=True)
                return
                
            if not joiner or joiner.get("balance", 0) < bet:
                await callback_query.answer("Insufficient balance! You need enough coins to match the bet.", show_alert=True)
                return
                
            # Deduct balances
            await user_collection.update_one({"id": creator_id}, {"$inc": {"balance": -bet}})
            await user_collection.update_one({"id": joiner_id}, {"$inc": {"balance": -bet}})
            
            # Determine color assignment
            if random.choice([True, False]):
                white_player = creator_id
                white_name = creator_name
                black_player = joiner_id
                black_name = joiner_name
            else:
                white_player = joiner_id
                white_name = joiner_name
                black_player = creator_id
                black_name = creator_name
                
            now = datetime.utcnow()
            
            await chess_rooms_collection.update_one(
                {"room_id": room_id},
                {
                    "$set": {
                        "joiner_id": joiner_id,
                        "joiner_name": joiner_name,
                        "white_player": white_player,
                        "white_name": white_name,
                        "black_player": black_player,
                        "black_name": black_name,
                        "status": "active",
                        "last_move_at": now
                    }
                }
            )

    await callback_query.answer("Match joined successfully! Good luck!", show_alert=True)
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    webapp_url = f"https://t.me/{bot_username}?startapp=chess_{room_id}"
    
    text = (
        f"🎮 <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 𝖲𝖳𝖠𝖱𝖳𝖤𝖣!</b>\n\n"
        f"⚪ <b>White:</b> <a href=\"tg://user?id={white_player}\">{white_name}</a>\n"
        f"⚫ <b>Black:</b> <a href=\"tg://user?id={black_player}\">{black_name}</a>\n"
        f"💰 <b>Bet Pool:</b> <code>{bet * 2:,}</code> coins\n"
        f"⏳ <b>Time Control:</b> 10 Minutes per player\n\n"
        f"<i>Click the button below to open the board inside Telegram and play! If you close the app, you can reconnect.</i>"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("♟️ Play Chess", url=webapp_url)]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=enums.ParseMode.HTML)

# ----------------- WebApp Server Route Handlers -----------------

async def serve_chess_html(request):
    html_path = os.path.join(os.path.dirname(__file__), "..", "templates", "chess.html")
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return web.Response(text=content, content_type='text/html')
    else:
        return web.Response(text="<h1>Chess Webapp Template Not Found</h1>", status=404, content_type='text/html')

async def chess_ws_handler(request):
    room_id = request.match_info['room_id']
    
    # Verify room exists and is active
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room:
        return web.Response(text="Room not found", status=404)
        
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    player_role = None
    user_id = None
    
    try:
        # Loop for socket authorization and events
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                    
                msg_type = data.get("type")
                
                if msg_type == "auth":
                    # Authenticate user
                    init_data = data.get("initData")
                    # Fallback user_id for non-Telegram debugging
                    fallback_id = data.get("user_id")
                    
                    auth_user = verify_telegram_webapp_data(init_data, TOKEN)
                    if auth_user:
                        user_id = auth_user.get("id")
                    elif fallback_id:
                        user_id = int(fallback_id)
                        
                    if not user_id:
                        await ws.send_json({"type": "error", "message": "Authentication failed"})
                        await ws.close()
                        return ws
                        
                    # Check if user belongs in this game
                    if user_id == room["white_player"]:
                        player_role = "white"
                    elif user_id == room["black_player"]:
                        player_role = "black"
                    else:
                        await ws.send_json({"type": "error", "message": "You are not a player in this room"})
                        await ws.close()
                        return ws
                        
                    # Register connection
                    if room_id not in active_connections:
                        active_connections[room_id] = {"white": None, "black": None}
                    active_connections[room_id][player_role] = ws
                    
                    # Notify opponent of connection
                    opponent_role = "black" if player_role == "white" else "white"
                    opponent_ws = active_connections[room_id].get(opponent_role)
                    if opponent_ws:
                        await opponent_ws.send_json({"type": "opponent_status", "connected": True})
                        
                    # Calculate real remaining times dynamically
                    now = datetime.utcnow()
                    white_time = room["white_time"]
                    black_time = room["black_time"]
                    if room["status"] == "active" and room["last_move_at"]:
                        elapsed = (now - room["last_move_at"]).total_seconds()
                        if room["active_turn"] == "white":
                            white_time = max(0.0, white_time - elapsed)
                        else:
                            black_time = max(0.0, black_time - elapsed)
                            
                    # Send initial room state
                    await ws.send_json({
                        "type": "init",
                        "role": player_role,
                        "board_state": room["board_state"],
                        "move_history": room["move_history"],
                        "white_name": room["white_name"],
                        "black_name": room["black_name"],
                        "white_id": room["white_player"],
                        "black_id": room["black_player"],
                        "white_time": int(white_time),
                        "black_time": int(black_time),
                        "active_turn": room["active_turn"],
                        "bet": room["bet"],
                        "status": room["status"],
                        "opponent_connected": opponent_ws is not None
                    })
                    
                elif msg_type == "move":
                    if not player_role:
                        continue
                    # Handle move submission
                    move_uci = data.get("move")
                    await handle_player_move(room_id, player_role, move_uci)
                    
                elif msg_type == "resign":
                    if not player_role:
                        continue
                    await handle_resignation(room_id, player_role)
                    
                elif msg_type == "abort":
                    if not player_role:
                        continue
                    await handle_abort(room_id, player_role)
                    
    except Exception as e:
        print(f"Error in websocket loop for room {room_id}: {e}")
        traceback.print_exc()
    finally:
        # Cleanup connection
        if room_id in active_connections and player_role:
            active_connections[room_id][player_role] = None
            # Notify opponent of disconnect
            opponent_role = "black" if player_role == "white" else "white"
            opponent_ws = active_connections[room_id].get(opponent_role)
            if opponent_ws:
                await opponent_ws.send_json({"type": "opponent_status", "connected": False})
                
            # If both are gone, clean the key
            if not active_connections[room_id]["white"] and not active_connections[room_id]["black"]:
                active_connections.pop(room_id, None)
                
    return ws

# ----------------- Game Event Logic Helpers -----------------

async def handle_player_move(room_id: str, role: str, move_uci: str):
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room or room["status"] != "active":
        return
        
    if room["active_turn"] != role:
        # Not player's turn
        return
        
    try:
        board = chess.Board(room["board_state"])
        move = chess.Move.from_uci(move_uci)
    except Exception:
        # Invalid UCI format
        return
        
    if move not in board.legal_moves:
        # Move is illegal
        ws = active_connections.get(room_id, {}).get(role)
        if ws:
            await ws.send_json({"type": "illegal_move", "message": "Move is illegal in this position"})
        return
        
    # Apply move
    board.push(move)
    
    # Calculate elapsed time
    now = datetime.utcnow()
    last_move_at = room["last_move_at"] or room["created_at"]
    elapsed = (now - last_move_at).total_seconds()
    
    white_time = room["white_time"]
    black_time = room["black_time"]
    
    if role == "white":
        white_time = max(0.0, white_time - elapsed)
    else:
        black_time = max(0.0, black_time - elapsed)
        
    # Check game over states
    is_game_over = False
    game_status = "active"
    winner = None
    reason = ""
    
    if board.is_checkmate():
        is_game_over = True
        winner = role # Current player delivered checkmate
        game_status = "white_won" if winner == "white" else "black_won"
        reason = "checkmate"
    elif board.is_stalemate():
        is_game_over = True
        game_status = "draw"
        reason = "stalemate"
    elif board.is_insufficient_material():
        is_game_over = True
        game_status = "draw"
        reason = "insufficient_material"
    elif board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
        is_game_over = True
        game_status = "draw"
        reason = "repetition"
    elif board.is_fifty_moves() or board.can_claim_fifty_moves():
        is_game_over = True
        game_status = "draw"
        reason = "fifty_moves"
        
    next_turn = "black" if role == "white" else "white"
    move_history = room["move_history"] + [move_uci]
    
    update_data = {
        "board_state": board.fen(),
        "move_history": move_history,
        "white_time": white_time,
        "black_time": black_time,
        "active_turn": next_turn,
        "last_move_at": now
    }
    
    if is_game_over:
        update_data["status"] = game_status
        await settle_escrow(room, game_status, reason)
        
    await chess_rooms_collection.update_one({"room_id": room_id}, {"$set": update_data})
    
    # Broadcast move to both players
    room_sockets = active_connections.get(room_id, {})
    for r in ["white", "black"]:
        ws = room_sockets.get(r)
        if ws:
            await ws.send_json({
                "type": "update",
                "board_state": board.fen(),
                "move_history": move_history,
                "white_time": int(white_time),
                "black_time": int(black_time),
                "active_turn": next_turn,
                "status": game_status,
                "reason": reason
            })
            if is_game_over:
                await ws.send_json({
                    "type": "game_over",
                    "status": game_status,
                    "reason": reason,
                    "winner": winner
                })

async def handle_resignation(room_id: str, role: str):
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room or room["status"] != "active":
        return
        
    winner = "black" if role == "white" else "white"
    game_status = "black_won" if winner == "black" else "white_won"
    reason = "resignation"
    
    now = datetime.utcnow()
    last_move_at = room["last_move_at"] or room["created_at"]
    elapsed = (now - last_move_at).total_seconds()
    
    white_time = room["white_time"]
    black_time = room["black_time"]
    if role == "white":
        white_time = max(0.0, white_time - elapsed)
    else:
        black_time = max(0.0, black_time - elapsed)
        
    await settle_escrow(room, game_status, reason)
    
    await chess_rooms_collection.update_one(
        {"room_id": room_id},
        {
            "$set": {
                "status": game_status,
                "white_time": white_time,
                "black_time": black_time,
                "last_move_at": now
            }
        }
    )
    
    # Broadcast resignation
    room_sockets = active_connections.get(room_id, {})
    for r in ["white", "black"]:
        ws = room_sockets.get(r)
        if ws:
            await ws.send_json({
                "type": "game_over",
                "status": game_status,
                "reason": reason,
                "winner": winner
            })

async def handle_abort(room_id: str, role: str):
    room = await chess_rooms_collection.find_one({"room_id": room_id})
    if not room or room["status"] != "active":
        return
        
    # Aborting is only allowed if no moves have been played yet
    if len(room["move_history"]) > 0:
        ws = active_connections.get(room_id, {}).get(role)
        if ws:
            await ws.send_json({"type": "error", "message": "Cannot abort. Move has already been made. Resign instead."})
        return
        
    game_status = "aborted"
    reason = "aborted"
    
    await settle_escrow(room, game_status, reason)
    
    await chess_rooms_collection.update_one(
        {"room_id": room_id},
        {"$set": {"status": game_status}}
    )
    
    # Broadcast abort
    room_sockets = active_connections.get(room_id, {})
    for r in ["white", "black"]:
        ws = room_sockets.get(r)
        if ws:
            await ws.send_json({
                "type": "game_over",
                "status": game_status,
                "reason": reason,
                "winner": None
            })

# ----------------- Escrow Settlement Logic -----------------

async def notify_group_chat(room: dict, text: str):
    chat_id = room.get("chat_id")
    message_id = room.get("message_id")
    if chat_id:
        try:
            await ZYRO.send_message(
                chat_id=chat_id,
                text=text,
                reply_to_message_id=message_id,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            print(f"Error notifying group chat: {e}")

async def settle_escrow(room: dict, status: str, reason: str):
    white_player = room["white_player"]
    black_player = room["black_player"]
    bet = room["bet"]
    
    white_name = room["white_name"]
    black_name = room["black_name"]
    
    white_user_lock = get_user_lock(white_player)
    black_user_lock = get_user_lock(black_player)
    
    async with white_user_lock:
        async with black_user_lock:
            if status == "white_won":
                # White wins, receives full pool (bet * 2)
                winnings = bet * 2
                await user_collection.update_one({"id": white_player}, {"$inc": {"balance": winnings}})
                
                # Notify on Telegram
                text_notif = (
                    f"🏆 <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 𝖮𝖵𝖤𝖱!</b>\n\n"
                    f"⚪ <b>White:</b> {white_name} (Winner)\n"
                    f"⚫ <b>Black:</b> {black_name}\n"
                    f"💰 <b>Winnings:</b> <code>{winnings:,}</code> coins (by {reason})"
                )
                await notify_players(white_player, black_player, text_notif)
                await notify_group_chat(room, text_notif)
                
            elif status == "black_won":
                # Black wins, receives full pool (bet * 2)
                winnings = bet * 2
                await user_collection.update_one({"id": black_player}, {"$inc": {"balance": winnings}})
                
                # Notify on Telegram
                text_notif = (
                    f"🏆 <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 𝖮𝖵𝖤𝖱!</b>\n\n"
                    f"⚪ <b>White:</b> {white_name}\n"
                    f"⚫ <b>Black:</b> {black_name} (Winner)\n"
                    f"💰 <b>Winnings:</b> <code>{winnings:,}</code> coins (by {reason})"
                )
                await notify_players(white_player, black_player, text_notif)
                await notify_group_chat(room, text_notif)
                
            elif status in ["draw", "aborted"]:
                # Draw or Aborted, refund both players their bet
                await user_collection.update_one({"id": white_player}, {"$inc": {"balance": bet}})
                await user_collection.update_one({"id": black_player}, {"$inc": {"balance": bet}})
                
                # Notify on Telegram
                verb = "drawn" if status == "draw" else "aborted"
                text_notif = (
                    f"🤝 <b>𝖢𝖧𝖤𝖲𝖲 𝖬𝖠𝖳𝖢𝖧 {verb.upper()}</b>\n\n"
                    f"⚪ <b>White:</b> {white_name}\n"
                    f"⚫ <b>Black:</b> {black_name}\n"
                    f"⚖️ <b>Outcome:</b> Refunded {bet:,} coins to both players (by {reason})."
                )
                await notify_players(white_player, black_player, text_notif)
                await notify_group_chat(room, text_notif)

async def notify_players(p1: int, p2: int, text: str):
    for player_id in [p1, p2]:
        try:
            await ZYRO.send_message(
                chat_id=player_id,
                text=text,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass # Suppress DM block exceptions

# ----------------- Real-time Timer Background Task -----------------

async def run_chess_timer_loop():
    print("=== Chess Match Timer Background Task Started ===")
    while True:
        try:
            await process_chess_timers()
        except Exception as e:
            print(f"Error in process_chess_timers: {e}")
            traceback.print_exc()
        await asyncio.sleep(1)

async def process_chess_timers():
    now = datetime.utcnow()
    # Fetch active chess matches
    active_rooms = await chess_rooms_collection.find({"status": "active"}).to_list(length=100)
    
    for room in active_rooms:
        room_id = room["room_id"]
        last_move_at = room["last_move_at"] or room["created_at"]
        elapsed = (now - last_move_at).total_seconds()
        
        turn = room["active_turn"]
        white_time = room["white_time"]
        black_time = room["black_time"]
        
        # Calculate countdowns
        if turn == "white":
            white_time_now = max(0.0, white_time - elapsed)
            black_time_now = black_time
        else:
            black_time_now = max(0.0, black_time - elapsed)
            white_time_now = white_time
            
        # Check if turn timer expired
        if (turn == "white" and white_time_now <= 0.0) or (turn == "black" and black_time_now <= 0.0):
            # Time has run out! Opponent wins
            winner = "black" if turn == "white" else "white"
            game_status = "black_won" if winner == "black" else "white_won"
            reason = "timeout"
            
            # Settle balances
            await settle_escrow(room, game_status, reason)
            
            # Update DB
            await chess_rooms_collection.update_one(
                {"room_id": room_id},
                {
                    "$set": {
                        "status": game_status,
                        "white_time": white_time_now,
                        "black_time": black_time_now
                    }
                }
            )
            
            # Broadcast timeout over websockets
            room_sockets = active_connections.get(room_id, {})
            for r in ["white", "black"]:
                ws = room_sockets.get(r)
                if ws:
                    try:
                        await ws.send_json({
                            "type": "game_over",
                            "status": game_status,
                            "reason": reason,
                            "winner": winner
                        })
                    except Exception:
                        pass
        else:
            # Sync ticking timers to players
            room_sockets = active_connections.get(room_id, {})
            for r in ["white", "black"]:
                ws = room_sockets.get(r)
                if ws:
                    try:
                        await ws.send_json({
                            "type": "timer_sync",
                            "white_time": int(white_time_now),
                            "black_time": int(black_time_now)
                        })
                    except Exception:
                        pass

# ----------------- Router Registration Helper -----------------

async def serve_avatar(request):
    user_id_str = request.match_info['user_id']
    try:
        user_id = int(user_id_str)
    except ValueError:
        return web.Response(text="Invalid user ID", status=400)
        
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cache"))
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    cached_file = os.path.join(cache_dir, f"avatar_{user_id}.jpg")
    
    if os.path.exists(cached_file):
        return web.FileResponse(cached_file)
        
    try:
        user = await ZYRO.get_users(user_id)
        if user and user.photo:
            file_path = await ZYRO.download_media(
                user.photo.small_file_id,
                file_name=cached_file
            )
            if file_path and os.path.exists(file_path):
                return web.FileResponse(file_path)
    except Exception as e:
        print(f"Error downloading profile photo for user {user_id}: {e}")
        
    return web.Response(text="Avatar not found", status=404)

def register_chess_routes(app_web: web.Application):
    app_web.router.add_get('/room/{room_id}', serve_chess_html)
    app_web.router.add_get('/chess/ws/{room_id}', chess_ws_handler)
    app_web.router.add_get('/avatar/{user_id}', serve_avatar)
    print("=== Chess webapp endpoints registered ===")
