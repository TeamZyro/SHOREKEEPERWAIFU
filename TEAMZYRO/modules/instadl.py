import os
import re
import time
import asyncio
import aiohttp
from pyrogram import filters
from playwright.async_api import async_playwright
from TEAMZYRO import app

INSTA_URL_PATTERN = re.compile(
    r'(https?://(?:www\.)?instagram\.com/(?:p|reel|tv|stories)/[^/?#\s]+)',
    re.IGNORECASE
)

async def extract_download_link(ig_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto("https://fastdl.app/en3", wait_until="networkidle", timeout=30000)
            await page.fill("#search-form-input", ig_url)
            await page.click("#searchFormButton")
            await page.wait_for_selector(".output-list, .download-box, a[href*='fastdl.app/download'], a[href*='cdninstagram'], a[href*='fastdl.app/get']", timeout=20000)
            
            links = await page.query_selector_all("a")
            for link in links:
                href = await link.get_attribute("href")
                if href and ("download" in href or "cdninstagram" in href or "fastdl.app/get" in href):
                    return href
            return None
        finally:
            await browser.close()

async def download_file(url, output_path):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://fastdl.app/"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            if r.status == 200:
                with open(output_path, "wb") as f:
                    f.write(await r.read())
                return True
    return False

@app.on_message(filters.command(["insta", "ig", "instadl"]))
async def insta_downloader_handler(client, message):
    args = message.text.split()
    ig_url = None
    
    if len(args) > 1:
        ig_url = args[1]
    elif message.reply_to_message and message.reply_to_message.text:
        match = INSTA_URL_PATTERN.search(message.reply_to_message.text)
        if match:
            ig_url = match.group(1)
            
    if not ig_url:
        match = INSTA_URL_PATTERN.search(message.text)
        if match:
            ig_url = match.group(1)
            
    if not ig_url:
        await message.reply_text("Please provide an Instagram link! Example: `/insta https://instagram.com/reel/...`")
        return
        
    status_message = await message.reply("🔄 Processing Instagram link via FastDL...")
    
    try:
        download_url = await extract_download_link(ig_url)
        if not download_url:
            await status_message.edit("❌ Failed to retrieve download link from FastDL.")
            return
            
        await status_message.edit("📥 Downloading media from Instagram CDN...")
        
        filename = f"insta_{int(time.time())}.mp4"
        temp_path = os.path.join("downloads", filename) if os.path.exists("downloads") else filename
        
        success = await download_file(download_url, temp_path)
        if not success:
            await status_message.edit("❌ Failed to download media from FastDL CDN.")
            return
            
        await status_message.edit("📤 Uploading media to Telegram...")
        
        try:
            await client.send_video(
                chat_id=message.chat.id,
                video=temp_path,
                caption="✨ Downloaded using FastDL!",
                reply_to_message_id=message.id
            )
        except Exception:
            await client.send_document(
                chat_id=message.chat.id,
                document=temp_path,
                caption="✨ Downloaded using FastDL!",
                reply_to_message_id=message.id
            )
            
        await status_message.delete()
        
    except Exception as e:
        await status_message.edit(f"❌ Error: {str(e)}")
    finally:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
