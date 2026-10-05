import os
import requests
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from TEAMZYRO import app

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.getenv("NVIDIA_AI_MODEL", "meta/llama-3.3-70b-instruct")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")


@app.on_message(filters.command("ai"))
async def ai_command(client: Client, message: Message):
    prompt = message.text.split(maxsplit=1)[1].strip() if message.text and len(message.text.split(maxsplit=1)) > 1 else ""

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
        response = requests.post(
            NVIDIA_API_URL,
            headers={
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "model": NVIDIA_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Shorekeeper AI. Answer clearly, helpfully, and concisely. Match the user's language when practical.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.6,
                "top_p": 0.9,
                "max_tokens": 2048,
                "stream": False,
            },
            timeout=60,
        )

        if response.status_code != 200:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text
            print(f"NVIDIA AI API error {response.status_code}: {error_detail}")
            await message.reply_text(
                "❌ AI request failed. Please try again later.",
                parse_mode=enums.ParseMode.HTML,
            )
            return

        data = response.json()
        answer = data["choices"][0]["message"]["content"].strip()

        if not answer:
            await message.reply_text("❌ AI returned an empty response.")
            return

        # Telegram messages have a practical text-size limit; split long AI answers.
        for start in range(0, len(answer), 4000):
            await message.reply_text(answer[start:start + 4000])

    except requests.Timeout:
        await message.reply_text("⏳ AI request timed out. Please try again.")
    except Exception as exc:
        print(f"NVIDIA AI command error: {exc}")
        await message.reply_text("❌ An error occurred while contacting the AI.")
