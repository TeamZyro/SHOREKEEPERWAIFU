import asyncio
import base64
import os
import subprocess
import json
import time
import tempfile

import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from TEAMZYRO import app

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.getenv("NVIDIA_AI_MODEL", "z-ai/glm-5.3")
NVIDIA_NSFW_MODEL = os.getenv(
    "NVIDIA_NSFW_MODEL",
    "nvidia/nemotron-3.5-content-safety",
)
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
AI_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=8, sock_read=25)
NSFW_TIMEOUT = aiohttp.ClientTimeout(total=45, connect=8, sock_read=35)

@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    parts = message.text.split(maxsplit=1) if message.text else []
    prompt = parts[1].strip() if len(parts) > 1 else ""

    if not prompt:
        await message.reply_text(
            "🤖 <b>AI Assistant</b>\n\n"
            "Use: <code>/ai your question</code>",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    if not NVIDIA_API_KEY:
        await message.reply_text(
            "⚠️ AI is not configured. Please set the NVIDIA_API_KEY environment variable.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    try:
        payload = {
            "model": NVIDIA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Shorekeeper AI. Answer clearly, helpfully and concisely. "
                        "Match the user's language when practical."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
            "top_p": 0.9,
            "max_tokens": 1024,
            "stream": False,
        }

        async with aiohttp.ClientSession(timeout=AI_TIMEOUT) as session:
            async with session.post(
                NVIDIA_API_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                data = await response.json(content_type=None)

        if response.status != 200:
            error_detail = data.get(
                "detail", data.get("message", "Unknown NVIDIA API error")
            )
            print(f"NVIDIA AI API error {response.status}: {error_detail}")
            await message.reply_text(
                "❌ AI request failed. Please try again later.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        choices = data.get("choices") or []
        answer = (
            choices[0].get("message", {}).get("content", "").strip()
            if choices else ""
        )

        if not answer:
            await message.reply_text("❌ AI returned an empty response.")
            return

        for start in range(0, len(answer), 4000):
            await message.reply_text(answer[start:start + 4000])

    except asyncio.TimeoutError:
        await message.reply_text("⏳ AI took too long to respond. Please try again.")
    except aiohttp.ClientError as exc:
        print(f"NVIDIA AI connection error: {exc}")
        await message.reply_text("🌐 AI service connection failed. Please try again.")
    except Exception as exc:
        print(f"NVIDIA AI command error: {exc}")
        await message.reply_text("❌ An error occurred while contacting the AI.")


# -------------------------
# NVIDIA NSFW media moderation
# -------------------------

NSFW_PROMPT = (
    "Inspect the attached image itself and classify ONLY sexual content. "
    "Mark unsafe if the image contains pornography, explicit sexual activity, "
    "or clearly sexual nudity. Normal clothing, swimwear, non-sexual medical "
    "or educational images, and ordinary anime/art are safe. "
    "Do not classify the text prompt; classify the image."
)

NSFW_POLICY = """
Classify the attached image for sexual content only.
Unsafe: pornography, explicit sexual acts, or clearly sexual nudity.
Safe: normal clothing, swimwear, non-sexual medical/educational content,
ordinary anime/art, and non-sexual skin exposure.
Return exactly: User Safety: safe OR User Safety: unsafe.
"""

def _image_data_uri(path: str, mime: str = "image/jpeg") -> str:
    with open(path, "rb") as file:
        encoded = base64.b64encode(file.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


async def _check_nsfw_image(path: str, mime: str = "image/jpeg") -> bool:
    if not NVIDIA_API_KEY:
        print("NSFW moderation skipped: NVIDIA_API_KEY is not configured.")
        return False

    payload = {
        "model": NVIDIA_NSFW_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": NSFW_PROMPT},
                {"type": "image_url", "image_url": {"url": _image_data_uri(path, mime)}},
            ],
        }],
        "max_tokens": 50,
        "temperature": 0.01,
        "top_p": 0.95,
        "stream": False,
        "chat_template_kwargs": {
            "custom_policy": NSFW_POLICY,
            "request_categories": "/no_categories",
            "enable_thinking": False,
        },
    }

    try:
        file_size = os.path.getsize(path)
        started = time.monotonic()
        print(f"[NSFW] API request start: file={file_size} bytes mime={mime} model={NVIDIA_NSFW_MODEL}")
        async with aiohttp.ClientSession(timeout=NSFW_TIMEOUT) as session:
            async with session.post(
                NVIDIA_API_URL,
                headers={
                    "Authorization": f"Bearer {NVIDIA_API_KEY}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                data = await response.json(content_type=None)

        if response.status != 200:
            print(
                f"NVIDIA NSFW API error {response.status}: "
                f"{data.get('detail', data.get('message', data))}"
            )
            return False

        choices = data.get("choices") or []
        if not choices:
            print(f"[NSFW] NVIDIA returned no choices: {json.dumps(data)[:1500]}")
            return False

        result = (choices[0].get("message") or {}).get("content") or ""
        lowered = " ".join(result.lower().split())
        is_unsafe = "user safety: unsafe" in lowered
        is_sexual = (
            "s2: sexual" in lowered
            or "s7: sexual (minor)" in lowered
            or "sexual (minor)" in lowered
            or "safety categories: sexual" in lowered
        )
        is_nsfw = is_unsafe or is_sexual
        print(f"[NSFW] NVIDIA result: {result[:800]!r} | unsafe={is_unsafe} sexual_category={is_sexual} final={is_nsfw}")
        return is_nsfw

    except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
        print(f"NVIDIA NSFW connection error: {exc}")
        return False
    except Exception as exc:
        print(f"NVIDIA NSFW check error: {type(exc).__name__}: {exc}")
        return False


async def _is_admin(client: Client, message: Message) -> bool:
    if not message.from_user or not message.chat:
        return False
    try:
        member = await client.get_chat_member(
            message.chat.id,
            message.from_user.id,
        )
        is_admin = member.status in (
            enums.ChatMemberStatus.OWNER,
            enums.ChatMemberStatus.ADMINISTRATOR,
        )
        print(f"[NSFW] sender={message.from_user.id} member_status={member.status} admin_bypass={is_admin}")
        return is_admin
    except Exception as exc:
        print(f"NSFW admin check error: {exc}")
        return False


async def _delete_if_nsfw(client: Client, message: Message) -> None:
    if not message.chat or message.chat.type not in (
        enums.ChatType.GROUP,
        enums.ChatType.SUPERGROUP,
    ):
        return

    if await _is_admin(client, message):
        return

    temp_path = None
    try:
        if message.photo:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                temp_path = tmp.name
            print(f"[NSFW] downloading photo: message={message.id}")
            await message.download(file_name=temp_path)
            print(f"[NSFW] photo downloaded: {os.path.getsize(temp_path)} bytes")
            is_nsfw = await _check_nsfw_image(temp_path)

        elif message.sticker and not message.sticker.is_animated and not message.sticker.is_video:
            with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                temp_path = tmp.name
            print(f"[NSFW] downloading sticker: message={message.id}")
            await message.download(file_name=temp_path)
            print(f"[NSFW] sticker downloaded: {os.path.getsize(temp_path)} bytes")
            is_nsfw = await _check_nsfw_image(temp_path, "image/webp")

        elif message.video or (message.sticker and message.sticker.is_video):
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                temp_path = tmp.name
            await message.download(file_name=temp_path)

            with tempfile.TemporaryDirectory() as frame_dir:
                pattern = os.path.join(frame_dir, "frame-%02d.jpg")
                process = await asyncio.create_subprocess_exec(
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-i", temp_path,
                    "-vf", "fps=1/3,scale=896:896:force_original_aspect_ratio=decrease",
                    "-frames:v", "6", "-q:v", "5", pattern,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()
                if process.returncode != 0:
                    print(f"FFmpeg frame extraction failed: {stderr.decode(errors='ignore')[:500]}")
                    return

                frames = sorted(
                    os.path.join(frame_dir, name)
                    for name in os.listdir(frame_dir)
                    if name.endswith(".jpg")
                )
                is_nsfw = False
                for frame in frames:
                    if await _check_nsfw_image(frame):
                        is_nsfw = True
                        break
        else:
            return

        print(f"[NSFW] final decision: chat={message.chat.id} message={message.id} nsfw={is_nsfw}")
        if is_nsfw:
            try:
                await message.delete()
                print(f"NSFW media deleted: chat={message.chat.id}, message={message.id}")
            except Exception as exc:
                print(f"[NSFW] DELETE FAILED: {type(exc).__name__}: {exc}. Check bot admin/Delete Messages permission.")

    except Exception as exc:
        print(f"NSFW media handler error: {type(exc).__name__}: {exc}")
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


# Do not depend on filters.group to receive the update. We verify the
# chat type inside the handler, which is safer across Pyrogram/Kurigram.
@app.on_message(
    filters.photo | filters.video | filters.sticker,
    group=97,
)
async def nsfw_media_handler(client: Client, message: Message):
    print(
        f"[NSFW] handler received media: chat={getattr(message.chat, 'id', None)} "
        f"type={getattr(message.chat, 'type', None)} message={message.id}"
    )
    await _delete_if_nsfw(client, message)
