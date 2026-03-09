# ------------------------------ IMPORTS ---------------------------------
import logging
import os
from telegram.ext import Application
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters as f
#from pyrogram.types import x
from aiogram import Bot, Dispatcher, types

# --------------------------- LOGGING SETUP ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        logging.FileHandler("log.txt"),
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)

# ---------------------------- CONSTANTS ---------------------------------
api_id = os.getenv("API_ID", "24965086")
api_hash = os.getenv("API_HASH", "b9c764ce47c010e1a887f19fea54f648")
TOKEN = os.getenv("TOKEN", "8308024939:AAHv49KD7nbKG2HVVCm-9MbBxSSEOXdhSJ0")
GLOG = os.getenv("GLOG", "babhboy")
CHARA_CHANNEL_ID = os.getenv("CHARA_CHANNEL_ID", "Zlog12")
SUPPORT_CHAT_ID = os.getenv("SUPPORT_CHAT_ID", "-1002562168076")
mongo_url = "mongodb+srv://harshmanjhi1801:webapp@cluster0.xxwc4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
backup_mongo_url = "mongodb+srv://harshmanjhi1801:webapp@cluster0.xxwc4.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

MUSJ_JOIN = os.getenv("MUSJ_JOIN", "LoverCodesChat")

# Modified to support both image and video URLs
# 🔹 START_MEDIA (Fixed: Direct URLs inside code)
START_MEDIA = [
    "https://files.catbox.moe/zufhkk.mp4",
    "https://files.catbox.moe/zufhkk.mp4"
]

PHOTO_URL = [
    os.getenv("PHOTO_URL_1", "https://files.catbox.moe/7ccoub.jpg"),
    os.getenv("PHOTO_URL_2", "https://files.catbox.moe/7ccoub.jpg")
]

STATS_IMG = ["https://files.catbox.moe/gknnju.jpg"] 

DB_NAME = "shoreskeeper"

SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/zyrosupport")
UPDATE_CHAT = os.getenv("UPDATE_CHAT", "https://t.me/Zyro_Network")
SUDO = list(map(int, os.getenv("SUDO", "7073835511,7073835511").split(',')))
OWNER_ID = int(os.getenv("OWNER_ID", "7018103039"))

# --------------------- TELEGRAM BOT CONFIGURATION -----------------------
command_filter = f.create(lambda _, __, message: message.text and message.text.startswith("/"))
application = Application.builder().token(TOKEN).build()
ZYRO = Client("Shivu", api_id=api_id, api_hash=api_hash, bot_token=TOKEN)
bot = Bot(token=TOKEN)
dp = Dispatcher()
# -------------------------- DATABASE SETUP ------------------------------
ddw = AsyncIOMotorClient(mongo_url)
db = ddw[DB_NAME]
collection = db['anime_characters_lol']
user_totals_collection = db['user_totals_lmaoooo']
user_collection = db["user_collection_lmaoooo"]
group_user_totals_collection = db['group_user_totalsssssss']
top_global_groups_collection = db['top_global_groups']
pm_users = db['total_pm_users']
discounts_collection = db['discounts']
# -------------------------- GLOBAL VARIABLES ----------------------------
app = ZYRO
sudo_users = SUDO

x = 0000000
# --------------------------- STRIN ---------------------------------------
locks = {}
message_counters = {}
spam_counters = {}
last_characters = {}
sent_characters = {}
first_correct_guesses = {}
message_counts = {}
last_user = {}
warned_users = {}
user_cooldowns = {}
user_nguess_progress = {}
user_guess_progress = {}
normal_message_counts = {}  

# -------------------------- POWER SETUP --------------------------------
from TEAMZYRO.unit.zyro_ban import *
from TEAMZYRO.unit.zyro_sudo import *
from TEAMZYRO.unit.zyro_react import *
from TEAMZYRO.unit.zyro_log import *
from TEAMZYRO.unit.zyro_send_img import *
from TEAMZYRO.unit.zyro_rarity import *
# ------------------------------------------------------------------------

async def PLOG(text: str):
    await app.send_message(
       chat_id=GLOG,
       text=text
   )

# ---------------------------- END OF CODE ------------------------------


backup_ddw = AsyncIOMotorClient(backup_mongo_url)

