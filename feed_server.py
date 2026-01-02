from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import random
import os
import json
from dotenv import load_dotenv
from flask_cors import CORS

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

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
    "skip_early": -3
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
        user_profile = {
            "user_id": user_id,
            "keyword_scores": {},
            "masala_scores": {},
            "history": [],
            "liked_videos": [],
            "saved_videos": [],
            "total_watch_time": 0,
            "last_updated": datetime.utcnow()
        }

    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = user_profile.get("history", [])
    liked_videos = user_profile.get("liked_videos", [])
    saved_videos = user_profile.get("saved_videos", [])
    total_watch_time = user_profile.get("total_watch_time", 0)

    for action in actions:
        vid = action.get("video_id")
        act_type = action.get("action_type")
        
        if not vid or act_type not in ACTION_WEIGHTS:
            continue
            
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

        # Update Lists based on action
        if vid not in history:
            history.append(vid)
            
        if act_type == "like" and vid not in liked_videos:
            liked_videos.append(vid)
        elif act_type == "save" and vid not in saved_videos:
            saved_videos.append(vid)
            
        # Update Watch Time
        duration = video_data.get("duration", 0)
        if act_type in ["watch_till_end", "rewatch"]:
            total_watch_time += duration
        elif act_type == "skip_early":
            total_watch_time += min(duration, 3) # Assume 3 seconds watched

    # Save changes
    user_profiles_collection.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "keyword_scores": keyword_scores,
                "masala_scores": masala_scores,
                "history": history[-1000:], 
                "liked_videos": liked_videos[-500:],
                "saved_videos": saved_videos[-500:],
                "total_watch_time": total_watch_time,
                "last_updated": datetime.utcnow()
            }
        },
        upsert=True
    )

def get_personalized_feed(user_id, limit):
    user_profile = user_profiles_collection.find_one({"user_id": user_id})
    
    # Cold Start
    if not user_profile:
        pipeline = [{"$sample": {"size": limit}}, {"$project": {"_id": 0}}]
        return list(videos_collection.aggregate(pipeline))

    # Personalized
    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = user_profile.get("history", [])

    top_keywords = sorted(keyword_scores, key=keyword_scores.get, reverse=True)[:10]
    top_masala = sorted(masala_scores, key=masala_scores.get, reverse=True)[:5]
    
    if not top_keywords and not top_masala:
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
    
    if len(candidates) < limit:
        needed = limit - len(candidates)
        random_fill = list(videos_collection.aggregate([
            {"$match": {"video_id": {"$nin": history}}},
            {"$sample": {"size": needed}},
            {"$project": {"_id": 0}}
        ]))
        candidates.extend(random_fill)

    random.shuffle(candidates)
    return candidates[:limit]

def get_videos_by_ids(video_ids):
    """Helper to fetch video details for a list of IDs"""
    if not video_ids:
        return []
    return list(videos_collection.find({"video_id": {"$in": video_ids}}, {"_id": 0}))

# --- API Endpoints ---

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "active", "service": "feed-server"}), 200

@app.route('/api/feed', methods=['POST'])
def feed():
    try:
        data = request.json
        user_id = data.get("user_id")
        actions = data.get("actions", [])
        is_first_request = data.get("is_first_request", False)
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        if actions:
            update_user_profile(user_id, actions)
        
        batch_size = 5 if is_first_request else 10
        videos = get_personalized_feed(user_id, batch_size)
        
        return jsonify({
            "user_id": user_id,
            "batch_size": len(videos),
            "videos": videos
        }), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/api/history/<user_id>', methods=['GET'])
def get_history(user_id):
    profile = user_profiles_collection.find_one({"user_id": user_id})
    if not profile:
        return jsonify([])
    # Return most recent first
    ids = profile.get("history", [])[::-1]
    videos = get_videos_by_ids(ids)
    # Sort videos to match history order
    videos_map = {v['video_id']: v for v in videos}
    ordered_videos = [videos_map[vid] for vid in ids if vid in videos_map]
    return jsonify(ordered_videos)

@app.route('/api/liked/<user_id>', methods=['GET'])
def get_liked(user_id):
    profile = user_profiles_collection.find_one({"user_id": user_id})
    if not profile:
        return jsonify([])
    ids = profile.get("liked_videos", [])[::-1]
    videos = get_videos_by_ids(ids)
    videos_map = {v['video_id']: v for v in videos}
    ordered_videos = [videos_map[vid] for vid in ids if vid in videos_map]
    return jsonify(ordered_videos)

@app.route('/api/saved/<user_id>', methods=['GET'])
def get_saved(user_id):
    profile = user_profiles_collection.find_one({"user_id": user_id})
    if not profile:
        return jsonify([])
    ids = profile.get("saved_videos", [])[::-1]
    videos = get_videos_by_ids(ids)
    videos_map = {v['video_id']: v for v in videos}
    ordered_videos = [videos_map[vid] for vid in ids if vid in videos_map]
    return jsonify(ordered_videos)

@app.route('/api/watchtime/<user_id>', methods=['GET'])
def get_watchtime(user_id):
    profile = user_profiles_collection.find_one({"user_id": user_id})
    total_seconds = profile.get("total_watch_time", 0) if profile else 0
    return jsonify({"total_seconds": total_seconds})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)