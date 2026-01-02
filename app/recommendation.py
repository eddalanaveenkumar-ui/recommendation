from app.db import db, videos
from datetime import datetime, timedelta
import random

# Weights for user actions
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

def update_user_profile(user_id, email=None):
    """
    Creates or updates a user profile.
    """
    update_data = {
        "last_updated": datetime.utcnow()
    }
    if email:
        update_data["email"] = email

    db.user_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True
    )

def process_user_actions(user_id, actions):
    """
    Process a batch of user actions to update user preferences.
    actions: list of dicts {video_id, action_type, duration, ...}
    """
    user_profile = db.user_profiles.find_one({"user_id": user_id})
    
    if not user_profile:
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
        if duration > 0:
            stats = daily_stats.get(current_date_str, {"watch_time": 0})
            stats["watch_time"] += duration
            daily_stats[current_date_str] = stats
            
        timestamp = datetime.utcnow()
        
        # Update Lists
        if act_type == "like":
            # Remove if exists to update timestamp/avoid duplicates
            liked_videos = [v for v in liked_videos if v["video_id"] != vid]
            liked_videos.append({"video_id": vid, "timestamp": timestamp})
        elif act_type == "save":
            saved_videos = [v for v in saved_videos if v["video_id"] != vid]
            saved_videos.append({"video_id": vid, "timestamp": timestamp})
            
        # Update Watch History
        if act_type not in ["skip_early"]:
             watch_history = [v for v in watch_history if v["video_id"] != vid]
             watch_history.append({"video_id": vid, "timestamp": timestamp})

        # Recommendation Logic
        if act_type not in ACTION_WEIGHTS:
            continue
            
        # Add to history to avoid repeating immediately
        history.add(vid)
        
        # Get video metadata
        video_data = videos.find_one({"video_id": vid})
        if not video_data:
            continue
            
        weight = ACTION_WEIGHTS[act_type]
        
        # Update Keyword Scores
        for kw in video_data.get("keywords", []):
            current = keyword_scores.get(kw, 0)
            keyword_scores[kw] = current + weight
            
        # Update Masala Scores
        for mk in video_data.get("masala_keywords", []):
            current = masala_scores.get(mk, 0)
            masala_scores[mk] = current + weight

    # Save updated profile
    db.user_profiles.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "keyword_scores": keyword_scores,
                "masala_scores": masala_scores,
                "history": list(history)[-500:], 
                "watch_history": watch_history[-200:],
                "liked_videos": liked_videos,
                "saved_videos": saved_videos,
                "daily_stats": daily_stats,
                "last_updated": datetime.utcnow()
            }
        },
        upsert=True
    )

def get_recommendations(user_id, limit=10):
    """
    Get personalized video recommendations based on user profile.
    """
    user_profile = db.user_profiles.find_one({"user_id": user_id})
    
    if not user_profile:
        # Cold start: Return random high-engagement videos
        return list(videos.aggregate([
            {"$sample": {"size": limit}},
            {"$project": {"_id": 0}}
        ]))

    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = user_profile.get("history", [])

    # Get top 5 keywords and masala tags
    top_keywords = sorted(keyword_scores, key=keyword_scores.get, reverse=True)[:5]
    top_masala = sorted(masala_scores, key=masala_scores.get, reverse=True)[:3]
    
    # If profile is weak (not enough data), mix with random
    if not top_keywords:
        return list(videos.aggregate([
            {"$sample": {"size": limit}},
            {"$project": {"_id": 0}}
        ]))

    # Query for videos matching preferences but not in history
    query = {
        "video_id": {"$nin": history},
        "$or": [
            {"keywords": {"$in": top_keywords}},
            {"masala_keywords": {"$in": top_masala}}
        ]
    }
    
    # Fetch candidates
    candidates = list(videos.find(query).limit(limit * 2))
    
    # If not enough candidates, fill with random
    if len(candidates) < limit:
        needed = limit - len(candidates)
        random_fill = list(videos.aggregate([
            {"$match": {"video_id": {"$nin": history}}},
            {"$sample": {"size": needed}}
        ]))
        candidates.extend(random_fill)

    # Shuffle and return
    random.shuffle(candidates)
    return candidates[:limit]

def get_user_list(user_id, list_type="history", limit=20):
    user_profile = db.user_profiles.find_one({"user_id": user_id})
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
        video_data = videos.find_one({"video_id": vid}, {"_id": 0})
        if video_data:
            video_data["interaction_timestamp"] = item["timestamp"]
            results.append(video_data)
            
    return results

def get_user_stats(user_id):
    user_profile = db.user_profiles.find_one({"user_id": user_id})
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
