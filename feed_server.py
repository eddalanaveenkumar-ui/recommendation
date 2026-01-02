from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import os
from dotenv import load_dotenv
from flask_cors import CORS
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = app.logger

# --- Database Connection ---
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["youtube_collector"]
videos_collection = db["videos"]
user_profiles_collection = db["user_profiles"]

# --- Configuration ---
ACTION_WEIGHTS = {
    "watch_till_end": 5,
    "rewatch": 6,
    "like": 3,
    "save": 4,
    "share": 5,
    "open_comments": 2,
    "skip_early": -3,
    "watch": 1
}

# --- Core Logic ---

def update_user_profile(user_id, actions):
    """
    Updates the user's profile based on their interactions.
    """
    if not actions:
        return

    user_profile = user_profiles_collection.find_one({"user_id": user_id})
    
    if not user_profile:
        logger.info(f"Creating new profile for user_id: {user_id} during update")
        user_profile = {
            "user_id": user_id,
            "keyword_scores": {},
            "masala_scores": {},
            "history": [],
            "watch_history": [],
            "liked_videos": [],
            "saved_videos": [],
            "daily_stats": {},
            "last_updated": datetime.utcnow()
        }

    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = set(user_profile.get("history", []))
    
    watch_history = user_profile.get("watch_history", [])
    liked_videos = user_profile.get("liked_videos", [])
    saved_videos = user_profile.get("saved_videos", [])
    daily_stats = user_profile.get("daily_stats", {})
    
    current_date_str = datetime.utcnow().strftime("%Y-%m-%d")

    for action in actions:
        vid = action.get("video_id")
        act_type = action.get("action_type")
        duration = action.get("duration", 0)
        
        if not vid:
            continue
            
        # Update Daily Watch Time
        if act_type == "watch" and duration > 0:
            stats = daily_stats.get(current_date_str, {"watch_time": 0})
            stats["watch_time"] += duration
            daily_stats[current_date_str] = stats
            
        timestamp = datetime.utcnow()

        # Update Lists
        if act_type == "like":
            liked_videos = [v for v in liked_videos if v["video_id"] != vid]
            liked_videos.append({"video_id": vid, "timestamp": timestamp})
        elif act_type == "save":
            saved_videos = [v for v in saved_videos if v["video_id"] != vid]
            saved_videos.append({"video_id": vid, "timestamp": timestamp})
            
        # Update Watch History
        if act_type in ["watch", "like", "save", "share", "watch_till_end", "rewatch"]:
             watch_history = [v for v in watch_history if v["video_id"] != vid]
             watch_history.append({"video_id": vid, "timestamp": timestamp})

        # Recommendation Logic
        if act_type not in ACTION_WEIGHTS:
            continue
            
        # Add to history to avoid repeating immediately
        history.add(vid)
        
        # Fetch video metadata
        video_data = videos_collection.find_one({"video_id": vid})
        if not video_data:
            continue
            
        weight = ACTION_WEIGHTS[act_type]
        
        # Update Scores
        for kw in video_data.get("keywords", []):
            keyword_scores[kw] = keyword_scores.get(kw, 0) + weight
        for mk in video_data.get("masala_keywords", []):
            masala_scores[mk] = masala_scores.get(mk, 0) + weight

    # Save changes
    user_profiles_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "keyword_scores": keyword_scores,
                "masala_scores": masala_scores,
                "history": list(history)[-1000:], 
                "watch_history": watch_history[-200:],
                "liked_videos": liked_videos,
                "saved_videos": saved_videos,
                "daily_stats": daily_stats,
                "last_updated": datetime.utcnow()
            }
        },
        upsert=True
    )

def get_personalized_feed(user_id, limit):
    logger.info(f"Getting feed for user_id: {user_id}, limit: {limit}")
    user_profile = user_profiles_collection.find_one({"user_id": user_id})
    
    # Cold Start
    if not user_profile:
        logger.info(f"User profile not found for {user_id}, returning random feed")
        pipeline = [{"$sample": {"size": limit}}, {"$project": {"_id": 0}}]
        return list(videos_collection.aggregate(pipeline))

    # Personalized
    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = user_profile.get("history", [])

    top_keywords = sorted(keyword_scores, key=keyword_scores.get, reverse=True)[:10]
    top_masala = sorted(masala_scores, key=masala_scores.get, reverse=True)[:5]
    
    logger.info(f"Top keywords: {top_keywords}, Top masala: {top_masala}")
    
    if not top_keywords and not top_masala:
         logger.info("No preferences found, returning random feed excluding history")
         pipeline = [{"$match": {"video_id": {"$nin": history}}}, {"$sample": {"size": limit}}, {"$project": {"_id": 0}}]
         return list(videos_collection.aggregate(pipeline))

    query = {
        "video_id": {"$nin": history},
        "$or": [
            {"keywords": {"$in": top_keywords}},
            {"masala_keywords": {"$in": top_masala}}
        ]
    }
    
    candidates = list(videos_collection.find(query, {"_id": 0}).limit(limit * 3))
    logger.info(f"Found {len(candidates)} candidates based on preferences")
    
    if len(candidates) < limit:
        needed = limit - len(candidates)
        logger.info(f"Not enough candidates, filling with {needed} random videos")
        random_fill = list(videos_collection.aggregate([
            {"$match": {"video_id": {"$nin": history}}},
            {"$sample": {"size": needed}},
            {"$project": {"_id": 0}}
        ]))
        candidates.extend(random_fill)

    random.shuffle(candidates)
    return candidates[:limit]

def get_user_list_data(user_id, list_type="history", limit=20):
    user_profile = user_profiles_collection.find_one({"user_id": user_id})
    if not user_profile:
        return []
        
    if list_type == "liked":
        items = user_profile.get("liked_videos", [])
    elif list_type == "saved":
        items = user_profile.get("saved_videos", [])
    else:
        items = user_profile.get("watch_history", [])
        
    # Sort by timestamp desc
    items.sort(key=lambda x: x["timestamp"], reverse=True)
    items = items[:limit]
    
    # Enrich with video details
    results = []
    for item in items:
        vid = item["video_id"]
        video_data = videos_collection.find_one({"video_id": vid}, {"_id": 0})
        if video_data:
            video_data["interaction_timestamp"] = item["timestamp"]
            results.append(video_data)
            
    return results

def get_user_stats_data(user_id):
    user_profile = user_profiles_collection.find_one({"user_id": user_id})
    if not user_profile:
        return {}
        
    daily_stats = user_profile.get("daily_stats", {})
    
    # Filter last 7 days
    today = datetime.utcnow().date()
    stats_response = {}
    
    for i in range(7):
        date_key = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        data = daily_stats.get(date_key, {"watch_time": 0})
        stats_response[date_key] = data
        
    return stats_response

# --- API Endpoints ---

@app.route('/', methods=['GET'])
def health_check():
    # CRITICAL FIX: This route must return a 200 OK for Render's health check.
    return jsonify({"status": "ok", "service": "feed-server"}), 200

@app.route('/api/login', methods=['POST'])
def login():
    """
    Endpoint to register/login user and store email.
    Payload:
    {
        "user_id": "123",
        "email": "user@example.com"
    }
    """
    data = request.json
    user_id = data.get("user_id")
    email = data.get("email")
    
    logger.info(f"Login request for user_id: {user_id}, email: {email}")
    
    if not user_id or not email:
        return jsonify({"error": "user_id and email required"}), 400
        
    user_profiles_collection.update_one(
        {"user_id": user_id},
        {"$set": {"email": email, "last_updated": datetime.utcnow()}},
        upsert=True
    )
    return jsonify({"status": "success"})

@app.route('/api/feed', methods=['POST'])
def feed():
    try:
        data = request.json
        user_id = data.get("user_id")
        actions = data.get("actions", [])
        is_first_request = data.get("is_first_request", False)
        
        logger.info(f"Feed request for user_id: {user_id}, actions: {len(actions)}")
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if actions:
            update_user_profile(user_id, actions)
        
        batch_size = 5 if is_first_request else 10
        videos = get_personalized_feed(user_id, batch_size)
        
        logger.info(f"Returning {len(videos)} videos for user_id: {user_id}")
        
        return jsonify({
            "user_id": user_id,
            "batch_size": len(videos),
            "videos": videos
        }), 200
    except Exception as e:
        logger.error(f"Error in feed endpoint: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/api/history/<user_id>', methods=['GET'])
def get_history(user_id):
    videos = get_user_list_data(user_id, list_type="history")
    return jsonify(videos)

@app.route('/api/liked/<user_id>', methods=['GET'])
def get_liked(user_id):
    videos = get_user_list_data(user_id, list_type="liked")
    return jsonify(videos)

@app.route('/api/saved/<user_id>', methods=['GET'])
def get_saved(user_id):
    videos = get_user_list_data(user_id, list_type="saved")
    return jsonify(videos)

@app.route('/api/watchtime/<user_id>', methods=['GET'])
def get_watchtime(user_id):
    stats = get_user_stats_data(user_id)
    return jsonify(stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)