from app.db import db, videos
from datetime import datetime
import random

# Weights for user actions
ACTION_WEIGHTS = {
    "watch_till_end": 5,
    "rewatch": 6,
    "like": 3,
    "save": 4,
    "share": 5,
    "open_comments": 2,
    "skip_early": -3
}

def process_user_actions(user_id, actions):
    """
    Process a batch of user actions to update user preferences.
    actions: list of dicts {video_id, action_type, ...}
    """
    user_profile = db.user_profiles.find_one({"user_id": user_id})
    
    if not user_profile:
        user_profile = {
            "user_id": user_id,
            "keyword_scores": {},
            "masala_scores": {},
            "history": [],
            "last_updated": datetime.utcnow()
        }

    keyword_scores = user_profile.get("keyword_scores", {})
    masala_scores = user_profile.get("masala_scores", {})
    history = set(user_profile.get("history", []))

    for action in actions:
        vid = action.get("video_id")
        act_type = action.get("action_type")
        
        if not vid or act_type not in ACTION_WEIGHTS:
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
                "history": list(history)[-500:], # Keep last 500 watched
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