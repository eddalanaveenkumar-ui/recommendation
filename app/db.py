from pymongo import MongoClient, ASCENDING
from app.config import MONGO_URI

client = MongoClient(
    MONGO_URI,
    maxPoolSize=20,
    serverSelectionTimeoutMS=5000
)

db = client["youtube_collector"]

videos = db["videos"]
videos.create_index([("video_id", ASCENDING)], unique=True)

user_keywords = db["user_keywords"]
user_profiles = db["user_profiles"]
user_profiles.create_index([("user_id", ASCENDING)], unique=True)
