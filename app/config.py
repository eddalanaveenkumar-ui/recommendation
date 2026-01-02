import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_KEYS = [
    os.getenv("YT_KEY_1"),
    os.getenv("YT_KEY_2"),
    os.getenv("YT_KEY_3"),
    os.getenv("YT_KEY_4"),
]

MONGO_URI = os.getenv("MONGO_URI")

LANGUAGES = ["en", "te", "ta", "hi"]

MAX_RESULTS_PER_TASK = 25

# HIGH ENGAGEMENT FILTERS
MIN_VIEWS = 10_000
MIN_LIKES = 500
MIN_COMMENTS = 50