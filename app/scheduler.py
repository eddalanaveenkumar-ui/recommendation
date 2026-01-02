from app.keywords import KEYWORDS
from app.config import MAX_RESULTS_PER_TASK
import random

def build_tasks():
    tasks = []

    for niche, subs in KEYWORDS.items():
        for sub, langs in subs.items():
            for lang, queries in langs.items():
                tasks.append({
                    "niche": niche,
                    "sub_niche": sub,
                    "language": lang,
                    "queries": queries,
                    "limit": MAX_RESULTS_PER_TASK
                })
    
    # Shuffle tasks to ensure equal distribution across niches over time
    random.shuffle(tasks)
    return tasks