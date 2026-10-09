import base64, hashlib, hmac, json, logging, os, threading, time
from datetime import datetime
from io import BytesIO
from urllib.parse import parse_qsl

from flask import Flask, abort, jsonify, render_template, request, send_file
from gridfs import GridFS
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from TEAMZYRO import TOKEN, SUDO, OWNER_ID, app, mongo_url

LOG = logging.getLogger(__name__)
SLOT_COST, MIN_PRICE, MAX_PRICE, RARITY = 5000, 10000, 1000000, "customise"
ART_SHOP_URL = os.getenv("ART_SHOP_URL", "").rstrip("/")
MAX_IMAGE_BYTES = 5 * 1024 * 1024
web = Flask(__name__, template_folder="../../web/templates")
web.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 256 * 1024
mongo = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
database = mongo["shoreskeeper"]
users = database["user_collection_lmaoooo"]
requests_col = database["custom_art_requests"]
art_col = database["custom_characters"]
sales_col = database["custom_art_sales"]
evo_ledger = database["evo_transactions"]
coin_ledger = database["custom_art_coin_ledger"]
fs = GridFS(database, collection="custom_art_images")
ADMIN_IDS = set(SUDO) | {OWNER_ID}
_web_started = False

def verify_init_data(init_data):
    if not init_data or not TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", None)
        if not received_hash:
            return None
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received_hash):
            return None
        auth_date = int(pairs.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > 86400:
            return None
        user_data = json.loads(pairs.get("user", "{}"))
        return {"id": int(user_data["id"]), "username": user_data.get("username"), "first_name": user_data.get("first_name", "User")}
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None

def authenticated_user():
    body = request.get_json(silent=True) or {}
    user = verify_init_data(body.get("initData") or request.headers.get("X-Telegram-Init-Data"))
    if not user:
        abort(401, description="Open this page inside Telegram to authenticate.")
    return user, body

def image_url(file_id):
    return "/api/art/image/" + str(file_id)

@web.get("/")
@web.get("/art-shop")
def art_shop_page():
    return render_template("art_shop.html", mode="shop")

@web.get("/customise")
def customise_page():
    return render_template("art_shop.html", mode="create")

@web.get("/api/art/list")
def list_art():
    items = []
    for item in art_col.find({"status": "approved"}).sort("published_at", -1).limit(100):
        items.append({"id": str(item["_id"]), "name": item["name"], "description": item.get("description", ""),
            "price": int(item["price"]), "creator_id": int(item["creator_id"]),
            "creator_name": item.get("creator_name") or "Creator", "rarity": RARITY,
            "image_url": image_url(item["image_file_id"]), "sales": int(item.get("total_sales", 0))})
    return jsonify({"items": items})

@web.get("/api/art/image/<file_id>")
def serve_art_image(file_id):
    from bson import ObjectId
    try:
        image = fs.get(ObjectId(file_id))
    except Exception:
        abort(404)
    response = send_file(BytesIO(image.read()), mimetype=image.content_type or "image/jpeg", max_age=3600)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@web.post("/api/customise/submit")
def submit_custom_art():
    user, body = authenticated_user()
    name = str(body.get("name", "")).strip()
    description = str(body.get("description", "")).strip()[:500]
    try:
        price = int(body.get("price"))
    except (ValueError, TypeError):
        return jsonify({"error": "Enter a valid Coin price."}), 400
    encoded = body.get("image")
    if not name or len(name) > 60:
        return jsonify({"error": "Character name must be 1–60 characters."}), 400
    if price < MIN_PRICE or price > MAX_PRICE:
        return jsonify({"error": "Price must be between 10,000 and 1,000,000 Coins."}), 400
    if not isinstance(encoded, str) or "," not in encoded:
        return jsonify({"error": "Upload a PNG, JPEG, or WebP image."}), 400
    header, payload = encoded.split(",", 1)
    mime = {"data:image/png;base64": "image/png", "data:image/jpeg;base64": "image/jpeg",
            "data:image/webp;base64": "image/webp"}.get(header.lower())
    if not mime:
        return jsonify({"error": "Only PNG, JPEG, and WebP are supported."}), 400
    try:
        raw = base64.b64decode(payload, validate=True)
    except (ValueError, base64.binascii.Error):
        return jsonify({"error": "Image data is invalid."}), 400
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        return jsonify({"error": "Image must be under 5 MB."}), 400
    if not users.find_one({"id": user["id"]}, {"_id": 1}):
        return jsonify({"error": "Use the bot and capture a character first to register."}), 400
    image_id = fs.put(raw, content_type=mime, filename="custom-" + str(user["id"]))
    debit = users.update_one({"id": user["id"], "evo_points": {"$gte": SLOT_COST}}, {"$inc": {"evo_points": -SLOT_COST}})
    if debit.modified_count != 1:
        fs.delete(image_id)
        return jsonify({"error": "You need 5,000 Evo Points to submit art."}), 400
    doc = {"creator_id": user["id"], "creator_name": user.get("username") or user.get("first_name") or "Creator",
           "name": name, "description": description, "price": price, "rarity": RARITY,
           "image_file_id": str(image_id), "status": "pending", "created_at": datetime.utcnow(), "evo_cost": SLOT_COST}
    try:
        result = requests_col.insert_one(doc)
        evo_ledger.insert_one({"user_id": user["id"], "amount": -SLOT_COST, "reason": "custom_art_submission",
                               "request_id": str(result.inserted_id), "created_at": datetime.utcnow()})
    except Exception:
        users.update_one({"id": user["id"]}, {"$inc": {"evo_points": SLOT_COST}})
        fs.delete(image_id)
        raise
    return jsonify({"ok": True, "message": "Submitted for admin approval. 5,000 Evo Points are held until the decision."})

@web.post("/api/art/buy")
def buy_art():
    user, body = authenticated_user()
    from bson import ObjectId
    try:
        art_id = ObjectId(str(body.get("art_id", "")))
    except Exception:
        return jsonify({"error": "Invalid art listing."}), 400
    art = art_col.find_one({"_id": art_id, "status": "approved"})
    if not art:
        return jsonify({"error": "This art is no longer available."}), 404
    buyer_id, creator_id, price = user["id"], int(art["creator_id"]), int(art["price"])
    if buyer_id == creator_id:
        return jsonify({"error": "You cannot buy your own art."}), 400
    if not users.find_one({"id": creator_id}, {"_id": 1}):
        return jsonify({"error": "Creator account is unavailable."}), 409
    try:
        with mongo.start_session() as session:
            with session.start_transaction():
                debit = users.update_one({"id": buyer_id, "balance": {"$gte": price}}, {"$inc": {"balance": -price}}, session=session)
                if debit.modified_count != 1:
                    raise ValueError("NOT_ENOUGH_COINS")
                credit = users.update_one({"id": creator_id}, {"$inc": {"balance": price}}, session=session)
                if credit.modified_count != 1:
                    raise ValueError("CREATOR_CREDIT_FAILED")
                owned = {"_id": ObjectId(), "id": "custom_" + str(art_id), "custom_id": str(art_id),
                         "img_url": request.host_url.rstrip("/") + image_url(art["image_file_id"]), "name": art["name"],
                         "anime": "Custom Art", "rarity": RARITY, "creator_id": creator_id}
                users.update_one({"id": buyer_id}, {"$push": {"characters": owned}}, session=session)
                art_col.update_one({"_id": art_id}, {"$inc": {"total_sales": 1, "total_earned": price},
                    "$addToSet": {"buyers": buyer_id}}, session=session)
                sales_col.insert_one({"art_id": str(art_id), "buyer_id": buyer_id, "creator_id": creator_id,
                                      "price": price, "created_at": datetime.utcnow()}, session=session)
                now = datetime.utcnow()
                coin_ledger.insert_many([
                    {"user_id": buyer_id, "amount": -price, "reason": "custom_art_purchase", "art_id": str(art_id), "created_at": now},
                    {"user_id": creator_id, "amount": price, "reason": "custom_art_sale", "art_id": str(art_id), "created_at": now}], session=session)
    except ValueError as exc:
        if str(exc) == "NOT_ENOUGH_COINS":
            return jsonify({"error": "Not enough Coins."}), 400
        LOG.exception("Creator purchase failed")
        return jsonify({"error": "Purchase could not be completed. No Coins were charged."}), 500
    except PyMongoError:
        LOG.exception("Creator purchase transaction failed")
        return jsonify({"error": "Purchase could not be completed. Check again before retrying."}), 503
    return jsonify({"ok": True, "message": "Purchase successful! The character was added to your collection."})

@app.on_message(filters.command("customise"))
async def customise_command(client, message):
    if not ART_SHOP_URL:
        return await message.reply_text("Creator Studio is not configured. Set ART_SHOP_URL to your HTTPS web app URL.")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎨 Open Creator Studio", web_app=WebAppInfo(url=ART_SHOP_URL + "/customise"))]])
    await message.reply_text("🎨 **Evo Creator Studio**\n\nSubmit your character for admin approval.\n"
        "• Submission cost: 5,000 Evo Points\n• Rarity is locked to customise\n"
        "• Price: 10,000–1,000,000 Coins\n• Rejected submissions refund all 5,000 Evo Points.", reply_markup=keyboard)

@app.on_message(filters.command("shop"))
async def art_shop_command(client, message):
    if not ART_SHOP_URL:
        return await message.reply_text("Art Shop is not configured. Set ART_SHOP_URL to your HTTPS web app URL.")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🛍️ Open Art Shop", web_app=WebAppInfo(url=ART_SHOP_URL + "/art-shop"))]])
    await message.reply_text("🛍️ **Art Shop**\n\nBrowse and buy community-created custom characters only.", reply_markup=keyboard)

@app.on_message(filters.command("custompending"))
async def pending_custom_art(client, message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply_text("Admin only.")
    pending = list(requests_col.find({"status": "pending"}).sort("created_at", 1).limit(10))
    if not pending:
        return await message.reply_text("No pending custom art submissions.")
    from bson import ObjectId
    for item in pending:
        try:
            image = fs.get(ObjectId(item["image_file_id"]))
            photo = BytesIO(image.read())
            photo.name = "custom-art"
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Approve", callback_data="evoapprove:" + str(item["_id"])),
                InlineKeyboardButton("❌ Reject + Refund", callback_data="evoreject:" + str(item["_id"]))]])
            await message.reply_photo(photo, caption="Pending Custom Art\nName: " + item["name"] +
                "\nCreator ID: " + str(item["creator_id"]) + "\nPrice: " + format(item["price"], ",") +
                " Coins\nRarity: customise\nRequest: " + str(item["_id"]), reply_markup=keyboard)
        except Exception:
            LOG.exception("Could not display custom art request")

@app.on_callback_query(filters.regex(r"^evoapprove:"))
async def approve_custom_art(client, query):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Admin only.", show_alert=True)
    from bson import ObjectId
    try:
        request_id = ObjectId(query.data.split(":", 1)[1])
        item = requests_col.find_one_and_update({"_id": request_id, "status": "pending"},
            {"$set": {"status": "approved", "reviewed_at": datetime.utcnow(), "reviewed_by": query.from_user.id}},
            return_document=ReturnDocument.BEFORE)
        if not item:
            return await query.answer("Request already reviewed.", show_alert=True)
        result = art_col.insert_one({"creator_id": item["creator_id"], "creator_name": item.get("creator_name", "Creator"),
            "name": item["name"], "description": item.get("description", ""), "price": item["price"], "rarity": RARITY,
            "image_file_id": item["image_file_id"], "status": "approved", "published_at": datetime.utcnow(),
            "total_sales": 0, "total_earned": 0, "buyers": []})
        requests_col.update_one({"_id": request_id}, {"$set": {"published_art_id": str(result.inserted_id)}})
        try:
            await client.send_message(item["creator_id"], "Your custom character " + item["name"] + " was approved and listed in Art Shop!")
        except Exception:
            pass
        await query.message.edit_caption((query.message.caption or "") + "\n\nAPPROVED and published")
        await query.answer("Published to Art Shop.")
    except Exception:
        LOG.exception("Custom art approval failed")
        await query.answer("Approval failed. Check logs.", show_alert=True)

@app.on_callback_query(filters.regex(r"^evoreject:"))
async def reject_custom_art(client, query):
    if query.from_user.id not in ADMIN_IDS:
        return await query.answer("Admin only.", show_alert=True)
    from bson import ObjectId
    try:
        request_id = ObjectId(query.data.split(":", 1)[1])
        item = requests_col.find_one_and_update({"_id": request_id, "status": "pending"},
            {"$set": {"status": "rejected", "reviewed_at": datetime.utcnow(), "reviewed_by": query.from_user.id}},
            return_document=ReturnDocument.BEFORE)
        if not item:
            return await query.answer("Request already reviewed.", show_alert=True)
        refund_amount = int(item.get("evo_cost", SLOT_COST))
        refund = users.update_one({"id": item["creator_id"]}, {"$inc": {"evo_points": refund_amount}})
        if refund.modified_count == 1:
            evo_ledger.insert_one({"user_id": item["creator_id"], "amount": refund_amount, "reason": "custom_art_rejection_refund",
                                   "request_id": str(request_id), "created_at": datetime.utcnow()})
        try:
            await client.send_message(item["creator_id"], "Your custom character " + item["name"] +
                " was rejected. Your " + format(refund_amount, ",") + " Evo Points have been refunded.")
        except Exception:
            pass
        await query.message.edit_caption((query.message.caption or "") + "\n\nREJECTED — Evo refund issued")
        await query.answer("Rejected; refund issued.")
    except Exception:
        LOG.exception("Custom art rejection failed")
        await query.answer("Rejection failed. Check logs.", show_alert=True)

def start_web_server():
    global _web_started
    if _web_started or not os.getenv("PORT"):
        return
    _web_started = True
    port = int(os.getenv("PORT", "8080"))
    threading.Thread(target=lambda: web.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
                     daemon=True, name="evo-art-web").start()
    LOG.info("Evo Creator web server starting on port %s", port)

start_web_server()
