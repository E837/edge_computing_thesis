# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
NODE_TYPE = os.getenv('NODE_TYPE', 'cluster_manager')

# Storage for my neighbors (Vicinity)
# This list will be populated by the Central Node
MY_VICINITY = [] 

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "node_type": NODE_TYPE,
        "node_id": NODE_ID,
        "vicinity": MY_VICINITY
    })

# --- NEW: Endpoint to receive Vicinity list from Central Node ---
@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    global MY_VICINITY
    data = request.json
    
    # Expecting input like: {"neighbors": ["http://cluster_2:5000"]}
    if 'neighbors' in data:
        MY_VICINITY = data['neighbors']
        print(f"Cluster {NODE_ID} Vicinity Updated: {MY_VICINITY}")
        return jsonify({"status": "success", "message": "Vicinity updated"}), 200
    else:
        return jsonify({"status": "error", "message": "No neighbors provided"}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
