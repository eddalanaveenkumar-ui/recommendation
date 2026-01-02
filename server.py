from flask import Flask, request, jsonify
from app.recommendation import process_user_actions, get_recommendations
from app.db import db

app = Flask(__name__)

@app.route('/feed', methods=['POST'])
def feed():
    """
    Endpoint to handle user actions and return next batch of videos.
    Payload:
    {
        "user_id": "123",
        "actions": [
            {"video_id": "abc", "action_type": "like"},
            ...
        ],
        "is_first_request": false
    }
    """
    data = request.json
    user_id = data.get("user_id")
    actions = data.get("actions", [])
    is_first_request = data.get("is_first_request", False)
    
    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    # 1. Process Actions (Update User Profile)
    if actions:
        process_user_actions(user_id, actions)
    
    # 2. Determine Batch Size
    # First request (cold start or just started app) -> 5 videos
    # Subsequent requests -> 10 videos
    limit = 5 if is_first_request else 10
    
    # 3. Get Recommendations
    recs = get_recommendations(user_id, limit=limit)
    
    return jsonify({
        "videos": recs,
        "next_batch_size": 10 # Tell client to ask for 10 next time
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)