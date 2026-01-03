from pymongo import MongoClient
from config import Config

client = MongoClient(Config.MONGO_URI)
db = client[Config.DB_NAME]

sessions_col = db.sessions
added_col = db.added_users
settings_col = db.settings

# ---------- SESSIONS ----------
async def save_session(phone, string):
    sessions_col.update_one(
        {"phone": phone},
        {"$set": {"session": string}},
        upsert=True
    )

async def get_sessions():
    return {x["phone"]: x["session"] for x in sessions_col.find()}

# ---------- ADDED USERS ----------
async def mark_added(user_id):
    added_col.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id}},
        upsert=True
    )

async def is_added(user_id):
    return added_col.find_one({"user_id": user_id}) is not None

# ---------- SETTINGS ----------
async def set_val(key, value):
    settings_col.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )

async def get_val(key):
    data = settings_col.find_one({"key": key})
    return data["value"] if data else None
