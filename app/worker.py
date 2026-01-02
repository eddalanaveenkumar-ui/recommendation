from googleapiclient.errors import HttpError
from app.youtube import search_videos, get_video_stats
from app.db import videos
from app.logger import logger
from app.config import MIN_VIEWS, MIN_LIKES, MIN_COMMENTS
from app.utils import extract_keywords, parse_duration
from app.masala import generate_masala

# Global counter for quota usage
# Search = 100 units, Video Details = 1 unit
quota_used = 0

def run_worker(api_key, tasks):
    global quota_used
    quota_used = 0  # Reset for new key
    
    for task in tasks:
        collected = 0

        for q in task["queries"]:
            try:
                # Search costs 100 units
                items = search_videos(api_key, q, task["language"], task["limit"])
                quota_used += 100
                
                ids = [i["id"]["videoId"] for i in items]

                if not ids:
                    continue

                # Video details costs 1 unit
                meta_map = get_video_stats(api_key, ids)
                quota_used += 1
                
                for vid, meta in meta_map.items():
                    stats = meta.get("statistics", {})
                    content_details = meta.get("contentDetails", {})
                    
                    views = int(stats.get("viewCount", 0))
                    likes = int(stats.get("likeCount", 0))
                    comments = int(stats.get("commentCount", 0))
                    
                    # Duration check (0 to 180 seconds)
                    duration_str = content_details.get("duration", "PT0S")
                    duration_seconds = parse_duration(duration_str)
                    
                    if not (0 < duration_seconds <= 180):
                        continue

                    if views < MIN_VIEWS or likes < MIN_LIKES or comments < MIN_COMMENTS:
                        continue

                    title = meta["snippet"]["title"]
                    desc = meta["snippet"]["description"]

                    keywords = extract_keywords(title, desc, task["language"])

                    data = {
                        "video_id": vid,
                        "title": title,
                        "description": desc,
                        "keywords": keywords,
                        "niche": task["niche"],
                        "sub_niche": task["sub_niche"],
                        "language": task["language"],
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "duration": duration_seconds,
                        "masala_keywords": generate_masala(
                            task["niche"], title, views, likes
                        ),
                        "source": "youtube"
                    }

                    videos.update_one(
                        {"video_id": vid},
                        {"$setOnInsert": data},
                        upsert=True
                    )
                    collected += 1
                    
                # Log quota usage periodically
                logger.info(f"Quota Used So Far: {quota_used} units")
                
            except HttpError as e:
                if e.resp.status == 403 and "quotaExceeded" in str(e):
                    logger.error(f"Quota exceeded for API key: {api_key[:10]}... (Used ~{quota_used} units). Stopping worker.")
                    return  # Stop this worker completely
                else:
                    logger.error(f"API Error: {e}")
                    continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                continue

        logger.info(
            f"Collected {collected} HIGH-ENGAGEMENT videos for "
            f"{task['niche']}/{task['sub_niche']} ({task['language']})"
        )