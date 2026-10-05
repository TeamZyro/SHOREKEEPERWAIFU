import asyncio
import os
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from TEAMZYRO import app

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.getenv("NVIDIA_AI_MODEL", "z-ai/glm-5.3")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
AI_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=8, sock_read=25)


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

    # IMPORTANT: Never use synchronous requests.post() inside the Telegram event loop.
    # A slow NVIDIA response would otherwise block the entire bot.
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
            error_detail = data.get("detail", data.get("message", "Unknown NVIDIA API error"))
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
