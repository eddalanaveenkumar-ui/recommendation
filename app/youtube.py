from googleapiclient.discovery import build

def search_videos(api_key, query, language, max_results):
    yt = build("youtube", "v3", developerKey=api_key)

    res = yt.search().list(
        q=query,
        part="snippet",
        type="video",
        order="viewCount",
        relevanceLanguage=language,
        maxResults=max_results
    ).execute()

    return res.get("items", [])

def get_video_stats(api_key, video_ids):
    yt = build("youtube", "v3", developerKey=api_key)

    res = yt.videos().list(
        part="statistics,contentDetails,snippet",
        id=",".join(video_ids)
    ).execute()

    return {v["id"]: v for v in res.get("items", [])}

def get_video_details(api_key, video_id):
    """
    Fetches details for a single video, including dimensions.
    """
    yt = build("youtube", "v3", developerKey=api_key)

    res = yt.videos().list(
        part="statistics,contentDetails,snippet",
        id=video_id
    ).execute()

    item = res.get("items", [None])[0]
    if not item:
        return None

    # Extract dimensions from the highest resolution thumbnail
    thumbnail_details = item.get("snippet", {}).get("thumbnails", {})
    width, height = 0, 0
    if "maxres" in thumbnail_details:
        width = thumbnail_details["maxres"].get("width")
        height = thumbnail_details["maxres"].get("height")
    elif "high" in thumbnail_details:
        width = thumbnail_details["high"].get("width")
        height = thumbnail_details["high"].get("height")
    elif "medium" in thumbnail_details:
        width = thumbnail_details["medium"].get("width")
        height = thumbnail_details["medium"].get("height")
    
    details = {
        "id": item["id"],
        "snippet": item.get("snippet"),
        "statistics": item.get("statistics"),
        "contentDetails": item.get("contentDetails"),
        "width": width,
        "height": height
    }
    return details