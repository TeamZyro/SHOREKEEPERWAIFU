import os
import requests
from pyrogram import filters
from TEAMZYRO import ZYRO, collection, require_power, GLOG

# ─────────────────────────────────────────────────
#  /reupload <id1> <id2> <id3> ...
#
#  Flow for each ID:
#   1. Fetch existing (broken) img_url from DB
#   2. Bot calls send_photo() with that URL →
#      Telegram downloads it from its cache
#   3. Bot downloads the photo via Telegram file_id
#   4. Re-uploads to Catbox → gets fresh URL
#   5. Updates img_url + status="working" in DB
#   6. Deletes the temp Telegram message
# ─────────────────────────────────────────────────


def upload_to_catbox(file_path: str) -> str:
    """Upload a local file to catbox.moe and return the public URL."""
    api_url = "https://catbox.moe/user/api.php"
    with open(file_path, "rb") as f:
        response = requests.post(
            api_url,
            data={"reqtype": "fileupload"},
            files={"fileToUpload": f},
            timeout=60,
        )
    if response.status_code == 200 and response.text.strip().startswith("https"):
        return response.text.strip()
    raise Exception(f"Catbox upload failed: {response.text.strip()}")


@ZYRO.on_message(filters.command(["reupload"]))
@require_power("add_character")
async def reupload_handler(client, message):
    """
    Usage:
      /reupload 30
      /reupload 30 60 61 100
    """
    args = message.text.split()[1:]   # skip command

    if not args:
        return await message.reply_text(
            "❌ **Wrong format!**\n\n"
            "Usage:\n"
            "`/reupload 30`\n"
            "`/reupload 30 60 61 100`\n\n"
            "Bot will fetch the image from Telegram using the broken URL,\n"
            "re-upload to Catbox and update the database."
        )

    status_msg = await message.reply_text(
        f"⏳ Processing **{len(args)}** character(s)…"
    )

    results = []
    success = 0
    fail    = 0

    for char_id in args:
        char_id  = char_id.strip()
        path     = None
        sent_msg = None

        try:
            # ── Find character in DB ───────────────
            char = await collection.find_one({"id": char_id})
            if not char:
                try:
                    char = await collection.find_one({"id": int(char_id)})
                except Exception:
                    pass

            if not char:
                results.append(f"❌ `{char_id}` — not found in DB")
                fail += 1
                continue

            name    = char.get("name", "?")
            old_url = char.get("img_url", "")

            if not old_url:
                results.append(f"❌ `{char_id}` ({name}) — no img_url in DB")
                fail += 1
                continue

            # ── Step 1: Send photo via broken URL ──
            # Telegram will pull the image from its cache / servers
            sent_msg = await client.send_photo(
                chat_id=GLOG,
                photo=old_url,
                caption=f"#reupload id:{char_id}"
            )

            # ── Step 2: Download from Telegram ─────
            path = await client.download_media(
                sent_msg.photo.file_id,
                file_name=f"/tmp/reupload_{char_id}.jpg"
            )

            # ── Step 3: Upload to Catbox ───────────
            new_url = upload_to_catbox(path)

            # ── Step 4: Update MongoDB ─────────────
            await collection.update_one(
                {"id": char.get("id")},
                {"$set": {"img_url": new_url, "status": "working"}}
            )

            results.append(f"✅ `{char_id}` **{name}**\n   └ `{new_url}`")
            success += 1

        except Exception as e:
            results.append(f"❌ `{char_id}` — `{str(e)[:100]}`")
            fail += 1

        finally:
            # Clean up temp Telegram message
            if sent_msg:
                try:
                    await sent_msg.delete()
                except Exception:
                    pass
            # Clean up local file
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    # ── Final summary ─────────────────────────────
    summary = "\n".join(results)
    await status_msg.edit(
        f"**📦 Reupload Complete**\n"
        f"✅ Success: **{success}**  |  ❌ Failed: **{fail}**\n\n"
        f"{summary}"
    )
