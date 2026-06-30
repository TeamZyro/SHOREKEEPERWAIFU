import os
import time
import asyncio
import aiohttp
from PIL import Image
from pyrogram import filters
from TEAMZYRO import app

# Netlify function used by Cloudinary upscale tool for signed parameter signature
SIGN_URL = "https://cloudinary-tools.netlify.app/.netlify/functions/sign-upload-params"
CLOUD_NAME = "dtz0urit6"
API_KEY = "985946268373735"
UPLOAD_PRESET = "cloudinary-tools"

async def get_cloudinary_signature(params):
    async with aiohttp.ClientSession() as session:
        async with session.post(SIGN_URL, json={"paramsToSign": params}) as r:
            if r.status == 200:
                data = await r.json()
                return data["signature"]
            else:
                raise Exception(f"Failed to get signature: {await r.text()}")

async def upload_to_cloudinary(file_path):
    timestamp = int(time.time())
    params = {
        "timestamp": timestamp,
        "source": "uw",
        "upload_preset": UPLOAD_PRESET
    }
    
    # 1. Sign parameters
    signature = await get_cloudinary_signature(params)
    
    # 2. Upload file
    upload_url = f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload"
    data = aiohttp.FormData()
    data.add_field("api_key", API_KEY)
    data.add_field("timestamp", str(timestamp))
    data.add_field("source", "uw")
    data.add_field("upload_preset", UPLOAD_PRESET)
    data.add_field("signature", signature)
    
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    data.add_field("file", file_bytes, filename=os.path.basename(file_path))
    
    async with aiohttp.ClientSession() as session:
        async with session.post(upload_url, data=data) as r:
            if r.status == 200:
                return await r.json()
            else:
                raise Exception(f"Upload failed: {await r.text()}")

async def download_upscaled_image(url, retries=15, delay=2.0):
    async with aiohttp.ClientSession() as session:
        for i in range(retries):
            async with session.get(url) as r:
                if r.status == 200:
                    return await r.read()
                elif r.status in (423, 404, 500):
                    # AI model processing lock/busy or generating, wait and retry
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(delay)
    raise Exception("Image processing timed out on Cloudinary.")

@app.on_message(filters.command(["upscale", "enhance"]))
async def upscale_handler(client, message):
    reply = message.reply_to_message
    
    # Check if replied message exists and has photo/document image
    is_image = False
    if reply:
        if reply.photo:
            is_image = True
        elif reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image/"):
            is_image = True
            
    if not is_image:
        await message.reply_text("Please reply to a photo or image document with /upscale to enhance it!")
        return
        
    status_message = await message.reply("⚡ Downloading photo from Telegram...")
    
    # Download file locally
    temp_path = await reply.download()
    if not temp_path:
        await status_message.edit("❌ Failed to download photo from Telegram.")
        return
        
    try:
        # Determine dimensions of original image to make sure it is within Cloudinary's limits
        try:
            with Image.open(temp_path) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0
            
        await status_message.edit("📤 Uploading image to Cloudinary...")
        upload_res = await upload_to_cloudinary(temp_path)
        
        public_id = upload_res["public_id"]
        original_format = upload_res.get("format", "png")
        
        await status_message.edit("🧠 AI is upscaling your image (Cloudinary AI super-resolution)...")
        
        # Cloudinary's e_upscale requires image < 4.2 megapixels.
        # If it's larger, we limit it to 2048x2048 first before upscaling.
        if width * height > 4194304:
            transformation = f"w_2048,h_2048,c_limit/e_upscale,q_auto"
        else:
            transformation = "e_upscale,q_auto"
            
        # Build upscaled transformation URL
        upscaled_url = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{transformation}/{public_id}.{original_format}"
        
        # Download and wait for upscaled result
        img_bytes = await download_upscaled_image(upscaled_url)
        
        await status_message.edit("📥 Downloading upscaled image...")
        
        # Save upscaled image locally
        output_filename = f"upscaled_{os.path.basename(temp_path)}"
        output_path = os.path.join(os.path.dirname(temp_path), output_filename)
        
        with open(output_path, "wb") as f:
            f.write(img_bytes)
            
        await status_message.edit("📤 Sending upscaled image back...")
        # Send as document to preserve full quality
        await client.send_document(
            chat_id=message.chat.id,
            document=output_path,
            caption="✨ Image upscaled successfully using Cloudinary AI!",
            reply_to_message_id=message.id
        )
        await status_message.delete()
        
    except Exception as e:
        await status_message.edit(f"❌ Error occurred: {str(e)}")
    finally:
        # Cleanup temporary files
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        if 'output_path' in locals() and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
