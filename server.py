from flask import Flask, request, jsonify
from app.recommendation import process_user_actions, get_recommendations, get_user_list, get_user_stats, update_user_profile
from app.db import db

app = Flask(__name__)

@app.route('/user/login', methods=['POST'])
def login():
    """
    Endpoint to register/login user and store email.
    Payload:
    {
        "user_id": "123",
        "email": "user@example.com"
    }
    """
    data = request.json
    user_id = data.get("user_id")
    email = data.get("email")
    
    if not user_id or not email:
        return jsonify({"error": "user_id and email required"}), 400
        
    update_user_profile(user_id, email=email)
    return jsonify({"status": "success"})

@app.route('/feed', methods=['POST'])
def feed():
    """
    Endpoint to handle user actions and return next batch of videos.
    Payload:
    {
        "user_id": "123",
        "actions": [
            {"video_id": "abc", "action_type": "like", "duration": 10},
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

@app.route('/user/history', methods=['GET'])
def get_history():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    videos = get_user_list(user_id, list_type="history")
    return jsonify({"videos": videos})

@app.route('/user/liked', methods=['GET'])
def get_liked():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    videos = get_user_list(user_id, list_type="liked")
    return jsonify({"videos": videos})

@app.route('/user/saved', methods=['GET'])
def get_saved():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    videos = get_user_list(user_id, list_type="saved")
    return jsonify({"videos": videos})

@app.route('/user/stats', methods=['GET'])
def get_stats():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    stats = get_user_stats(user_id)
    return jsonify({"stats": stats})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)