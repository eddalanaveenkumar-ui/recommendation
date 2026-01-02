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