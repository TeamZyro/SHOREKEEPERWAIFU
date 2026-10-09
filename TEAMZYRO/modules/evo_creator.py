import base64
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime
from io import BytesIO
from urllib.parse import parse_qsl

from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from bson import ObjectId
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from TEAMZYRO import app, db, user_collection, TOKEN, SUDO, OWNER_ID, ddw

LOG = logging.getLogger(__name__)
SLOT_COST = 5000
MIN_PRICE = 10000
MAX_PRICE = 1000000
RARITY = "customise"
MAX_IMAGE_BYTES = 5 * 1024 * 1024

requests_col = db["custom_art_requests"]
art_col = db["custom_characters"]
sales_col = db["custom_art_sales"]
evo_ledger = db["evo_transactions"]
coin_ledger = db["custom_art_coin_ledger"]
image_bucket = AsyncIOMotorGridFSBucket(db, bucket_name="custom_art_images")
ADMIN_IDS = set(SUDO) | {OWNER_ID}


def verify_init_data(init_data):
    """Validate Telegram Web App initData; never trust initDataUnsafe."""
    if not init_data or not TOKEN:
        return None
    try:
        values = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = values.pop("hash", None)
        if not received_hash:
            return None
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
        secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash):
            return None
        auth_date = int(values.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > 86400:
            return None
        return json.loads(values.get("user", "{}"))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


async def read_json(request):
    try:
        return await request.json()
    except Exception:
        raise web.HTTPBadRequest(text=json.dumps({"error": "Invalid JSON body"}), content_type="application/json")


async def authenticated_payload(request):
    body = await read_json(request)
    user = verify_init_data(body.get("initData") or request.headers.get("X-Telegram-Init-Data"))
    if not user or not user.get("id"):
        raise web.HTTPUnauthorized(text=json.dumps({"error": "Open this Mini App inside Telegram."}), content_type="application/json")
    return user, body


def json_error(message, status=400):
    return web.json_response({"error": message}, status=status)


async def serve_art_shop_html(request):
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "art_shop.html")
    if not os.path.isfile(path):
        return web.Response(text="<h1>Art Shop template not found</h1>", status=404, content_type="text/html")
    with open(path, "r", encoding="utf-8") as handle:
        return web.Response(text=handle.read(), content_type="text/html")


async def api_list_custom_art(request):
    items = []
    cursor = art_col.find({"status": "approved"}).sort("published_at", -1).limit(100)
    async for item in cursor:
        items.append({
            "id": str(item["_id"]), "name": item["name"], "anime": item.get("anime", "Unknown Anime"),
            "description": item.get("description", ""), "price": int(item["price"]),
            "creator_name": item.get("creator_name") or "Creator",
            "rarity": RARITY, "image_url": "/api/art/image/" + str(item["image_file_id"]),
            "sales": int(item.get("total_sales", 0)),
        })
    return web.json_response({"items": items})


async def api_custom_art_image(request):
    try:
        file_id = ObjectId(request.match_info["file_id"])
        stream = await image_bucket.open_download_stream(file_id)
        raw = await stream.read()
    except Exception:
        raise web.HTTPNotFound(text="Image not found")
    content_type = (stream.metadata or {}).get("content_type", "image/jpeg")
    return web.Response(body=raw, content_type=content_type, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=3600"})


async def api_submit_custom_art(request):
    user, body = await authenticated_payload(request)
    user_id = int(user["id"])
    name = str(body.get("name", "")).strip()
    anime = str(body.get("anime", "")).strip()
    description = str(body.get("description", "")).strip()[:500]
    try:
        price = int(body.get("price"))
    except (ValueError, TypeError):
        return json_error("Enter a valid Coin price.")
    if not name or len(name) > 60:
        return json_error("Character name must be 1–60 characters.")
    if not anime or len(anime) > 100:
        return json_error("Anime name must be 1–100 characters.")
    if not MIN_PRICE <= price <= MAX_PRICE:
        return json_error("Price must be between 10,000 and 1,000,000 Coins.")
    encoded = body.get("image")
    if not isinstance(encoded, str) or "," not in encoded:
        return json_error("Upload a PNG, JPEG, or WebP image.")
    header, payload = encoded.split(",", 1)
    mime = {
        "data:image/png;base64": "image/png",
        "data:image/jpeg;base64": "image/jpeg",
        "data:image/webp;base64": "image/webp",
    }.get(header.lower())
    if not mime:
        return json_error("Only PNG, JPEG, and WebP are supported.")
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, base64.binascii.Error):
        return json_error("Image data is invalid.")
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        return json_error("Image must be under 5 MB.")
    if not await user_collection.find_one({"id": user_id}, {"_id": 1}):
        return json_error("Use the bot and capture a character first to register.")
    # Debit with a balance predicate so concurrent submissions cannot overspend.
    debit = await user_collection.update_one({"id": user_id, "evo_points": {"$gte": SLOT_COST}}, {"$inc": {"evo_points": -SLOT_COST}})
    if debit.modified_count != 1:
        return json_error("You need 5,000 Evo Points to submit art.")
    image_id = None
    try:
        image_id = await image_bucket.upload_from_stream(
            "custom-" + str(user_id), raw, metadata={"content_type": mime, "creator_id": user_id}
        )
        result = await requests_col.insert_one({
            "creator_id": user_id, "creator_name": user.get("username") or user.get("first_name") or "Creator",
            "name": name, "anime": anime, "description": description, "price": price, "rarity": RARITY,
            "image_file_id": str(image_id), "status": "pending", "created_at": datetime.utcnow(),
            "evo_cost": SLOT_COST,
        })
        await evo_ledger.insert_one({
            "user_id": user_id, "amount": -SLOT_COST, "reason": "custom_art_submission",
            "request_id": str(result.inserted_id), "created_at": datetime.utcnow(),
        })
    except Exception:
        await user_collection.update_one({"id": user_id}, {"$inc": {"evo_points": SLOT_COST}})
        if image_id:
            try:
                await image_bucket.delete(image_id)
            except Exception:
                pass
        LOG.exception("Custom art submission failed")
        return json_error("Submission failed. Your Evo Points have been returned.", 500)
    return web.json_response({"ok": True, "message": "Submitted for admin approval. 5,000 Evo Points are held until the decision."})


async def api_buy_custom_art(request):
    user, body = await authenticated_payload(request)
    buyer_id = int(user["id"])
    try:
        art_id = ObjectId(str(body.get("art_id", "")))
    except Exception:
        return json_error("Invalid art listing.")
    art = await art_col.find_one({"_id": art_id, "status": "approved"})
    if not art:
        return json_error("This art is no longer available.", 404)
    creator_id, price = int(art["creator_id"]), int(art["price"])
    if buyer_id == creator_id:
        return json_error("You cannot buy your own art.")
    session = None
    try:
        async with await ddw.start_session() as session:
            async with session.start_transaction():
                # Add buyer to the listing first inside the transaction; duplicate buys roll back.
                listing = await art_col.update_one(
                    {"_id": art_id, "status": "approved", "buyers": {"$ne": buyer_id}},
                    {"$inc": {"total_sales": 1, "total_earned": price}, "$addToSet": {"buyers": buyer_id}},
                    session=session,
                )
                if listing.modified_count != 1:
                    raise ValueError("ALREADY_BOUGHT")
                debit = await user_collection.update_one(
                    {"id": buyer_id, "balance": {"$gte": price}}, {"$inc": {"balance": -price}}, session=session
                )
                if debit.modified_count != 1:
                    raise ValueError("NOT_ENOUGH_COINS")
                credit = await user_collection.update_one(
                    {"id": creator_id}, {"$inc": {"balance": price}}, session=session
                )
                if credit.modified_count != 1:
                    raise ValueError("CREATOR_NOT_FOUND")
                await user_collection.update_one({"id": buyer_id}, {"$push": {"characters": {
                    "_id": ObjectId(), "id": "custom_" + str(art_id), "custom_id": str(art_id),
                    "img_url": request.scheme + "://" + request.host + "/api/art/image/" + str(art["image_file_id"]),
                    "name": art["name"], "anime": art.get("anime", "Unknown Anime"), "rarity": RARITY, "creator_id": creator_id,
                }}}, session=session)
                now = datetime.utcnow()
                await sales_col.insert_one({
                    "art_id": str(art_id), "buyer_id": buyer_id, "creator_id": creator_id,
                    "price": price, "created_at": now,
                }, session=session)
                await coin_ledger.insert_many([
                    {"user_id": buyer_id, "amount": -price, "reason": "custom_art_purchase", "art_id": str(art_id), "created_at": now},
                    {"user_id": creator_id, "amount": price, "reason": "custom_art_sale", "art_id": str(art_id), "created_at": now},
                ], session=session)
    except ValueError as exc:
        if str(exc) == "NOT_ENOUGH_COINS":
            return json_error("Not enough Coins.")
        if str(exc) == "ALREADY_BOUGHT":
            return json_error("You already own this custom art.", 409)
        LOG.exception("Creator purchase failed")
        return json_error("Purchase could not be completed.", 500)
    except Exception:
        LOG.exception("Creator purchase transaction failed")
        return json_error("Purchase could not be completed. Check again before retrying.", 503)
    return web.json_response({"ok": True, "message": "Purchase successful! The character was added to your collection."})


def register_evo_creator_routes(app_web):
    """Attach routes to the existing AIOHTTP app used by Black Market and Chess."""
    app_web.router.add_get("/art-shop", serve_art_shop_html)
    app_web.router.add_get("/customise", serve_art_shop_html)
    app_web.router.add_get("/api/art/list", api_list_custom_art)
    app_web.router.add_get("/api/art/image/{file_id}", api_custom_art_image)
    app_web.router.add_post("/api/customise/submit", api_submit_custom_art)
    app_web.router.add_post("/api/art/buy", api_buy_custom_art)
    print("=== Evo Creator / Art Shop routes registered ===")


@app.on_message(filters.command("customise"))
async def customise_command(client, message):
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    # Reuse the bot's already-configured Main Mini App, exactly like Chess.
    webapp_url = f"https://t.me/{bot_username}?startapp=customise"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Open Creator Studio", url=webapp_url)]])
    await message.reply_text(
        "🎨 **Evo Creator Studio**\n\nSubmit your character for admin approval.\n"
        "• Submission cost: 5,000 Evo Points\n• Rarity is locked to customise\n"
        "• Price: 10,000–1,000,000 Coins\n• Rejected submissions refund all 5,000 Evo Points.",
        reply_markup=keyboard,
    )


@app.on_message(filters.command("shop"))
async def art_shop_command(client, message):
    bot_username = client.me.username if client.me else "shorekeeper_RoBot"
    # Reuse the bot's already-configured Main Mini App, exactly like Chess.
    webapp_url = f"https://t.me/{bot_username}?startapp=artshop"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ Open Art Shop", url=webapp_url)]])
    await message.reply_text("🛍️ **Art Shop**\n\nBrowse and buy community-created custom characters only.", reply_markup=keyboard)


@app.on_message(filters.command("custompending"))
async def pending_custom_art(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("Admin only.")
    cursor = requests_col.find({"status": "pending"}).sort("created_at", 1).limit(10)
    found = False
    async for item in cursor:
        found = True
        try:
            stream = await image_bucket.open_download_stream(ObjectId(item["image_file_id"]))
            photo = BytesIO(await stream.read())
            content_type = (stream.metadata or {}).get("content_type", "image/jpeg")
            extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type, ".jpg")
            photo.name = "custom-art" + extension
            caption = (
                "Pending Custom Art\nName: " + item["name"] +
                "\nCreator ID: " + str(item["creator_id"]) + "\nPrice: " + format(item["price"], ",") +
                " Coins\nAnime: " + item.get("anime", "Unknown Anime") + "\nRarity: customise\nRequest: " + str(item["_id"])
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data="evoapprove:" + str(item["_id"])),
                InlineKeyboardButton("❌ Reject + Refund", callback_data="evoreject:" + str(item["_id"])),
            ]])
            # Telegram photo uploads require a supported filename extension; non-JPEG
            # formats are sent as documents so PNG/WebP submissions remain reviewable.
            if content_type == "image/jpeg":
                await message.reply_photo(photo, caption=caption, reply_markup=keyboard)
            else:
                await message.reply_document(photo, caption=caption, reply_markup=keyboard)
        except Exception:
            LOG.exception("Could not display custom art request")
    if not found:
        await message.reply_text("No pending custom art submissions.")


@app.on_callback_query(filters.regex(r"^evoapprove:"))
async def approve_custom_art(client, query):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Admin only.", show_alert=True)
    request_id = ObjectId(query.data.split(":", 1)[1])
    item = await requests_col.find_one_and_update(
        {"_id": request_id, "status": "pending"},
        {"$set": {"status": "approved", "reviewed_at": datetime.utcnow(), "reviewed_by": query.from_user.id}},
        return_document=True,
    )
    if not item:
        return await query.answer("Request already reviewed.", show_alert=True)
    try:
        listing = await art_col.insert_one({
            "creator_id": item["creator_id"], "creator_name": item.get("creator_name", "Creator"),
            "name": item["name"], "anime": item.get("anime", "Unknown Anime"), "description": item.get("description", ""), "price": item["price"],
            "rarity": RARITY, "image_file_id": item["image_file_id"], "status": "approved",
            "published_at": datetime.utcnow(), "total_sales": 0, "total_earned": 0, "buyers": [],
        })
        await requests_col.update_one({"_id": request_id}, {"$set": {"published_art_id": str(listing.inserted_id)}})
    except Exception:
        # Keep a retryable status if publishing failed; no Evo refund on approval.
        await requests_col.update_one({"_id": request_id, "status": "approved"}, {"$set": {"status": "pending"}})
        LOG.exception("Custom art publication failed")
        return await query.answer("Publishing failed; request returned to pending.", show_alert=True)
    try:
        await app.send_message(item["creator_id"], "✅ Your custom character " + item["name"] + " (" + item.get("anime", "Unknown Anime") + ") was approved and listed in Art Shop!")
    except Exception:
        pass
    await query.message.edit_caption((query.message.caption or "") + "\n\n✅ APPROVED and published")
    await query.answer("Published to Art Shop.")


@app.on_callback_query(filters.regex(r"^evoreject:"))
async def reject_custom_art(client, query):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Admin only.", show_alert=True)
    request_id = ObjectId(query.data.split(":", 1)[1])
    item = await requests_col.find_one_and_update(
        {"_id": request_id, "status": "pending"},
        {"$set": {"status": "rejected", "reviewed_at": datetime.utcnow(), "reviewed_by": query.from_user.id}},
        return_document=True,
    )
    if not item:
        return await query.answer("Request already reviewed.", show_alert=True)
    refund_amount = int(item.get("evo_cost", SLOT_COST))
    refund = await user_collection.update_one({"id": item["creator_id"]}, {"$inc": {"evo_points": refund_amount}})
    if refund.modified_count == 1:
        await evo_ledger.insert_one({
            "user_id": item["creator_id"], "amount": refund_amount,
            "reason": "custom_art_rejection_refund", "request_id": str(request_id), "created_at": datetime.utcnow(),
        })
        try:
            await app.send_message(item["creator_id"], "❌ Your custom character " + item["name"] +
                " was rejected. Your " + format(refund_amount, ",") + " Evo Points have been refunded.")
        except Exception:
            pass
    else:
        LOG.error("Could not refund Evo Points for rejected request %s", request_id)
    await query.message.edit_caption((query.message.caption or "") + "\n\n❌ REJECTED — refund processed")
    await query.answer("Rejected.")
