import os
import sys
from app.scheduler import build_tasks
from app.worker import run_worker
from app.config import YOUTUBE_KEYS

# Get worker index from env or argument
WORKER_INDEX = int(os.getenv("WORKER_INDEX", 0))

# If the current key is exhausted, try the next one automatically
current_index = WORKER_INDEX

while current_index < len(YOUTUBE_KEYS):
    api_key = YOUTUBE_KEYS[current_index]
    if not api_key:
        print(f"No API key found at index {current_index}. Skipping.")
        current_index += 1
        continue
        
    print(f"Starting worker with Key Index: {current_index}")
    
    tasks = build_tasks()
    run_worker(api_key, tasks)
    
    # If run_worker returns, it means it finished OR hit a quota limit.
    # We can check if we should try the next key.
    # For simplicity in this script, we'll just move to the next key if the previous one failed/finished.
    # In a more complex setup, run_worker could return a status code.
    
    print(f"Worker with Key Index {current_index} finished or stopped.")
    current_index += 1

print("All API keys exhausted or tasks completed.")