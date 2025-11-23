# File: central_node/app.py
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# List of known clusters in our Docker network
CLUSTERS = {
    "1": "http://cluster_1:5000",
    "2": "http://cluster_2:5000",
    "3": "http://cluster_3:5000"
}

# SIMULATED LATENCY MATRIX (in milliseconds)
# Represents the physical distance between clusters
# If latency < 20ms, they are considered "Vicinity"
LATENCY_MATRIX = {
    "1": {"2": 10, "3": 50},  # Cluster 1 is close to 2 (10ms), far from 3 (50ms)
    "2": {"1": 10, "3": 15},  # Cluster 2 is close to both
    "3": {"1": 50, "2": 15}   # Cluster 3 is close to 2, far from 1
}

VICINITY_THRESHOLD = 20 # ms

@app.route('/')
def health_check():
    return jsonify({"status": "online", "role": "Central Cloud"})

# --- Trigger to Calculate and Push Vicinity ---
@app.route('/initialize_network', methods=['POST'])
def initialize_network():
    results = {}
    
    for source_id, source_url in CLUSTERS.items():
        neighbors = []
        
        # 1. Calculate neighbors based on Matrix
        if source_id in LATENCY_MATRIX:
            for target_id, latency in LATENCY_MATRIX[source_id].items():
                if latency <= VICINITY_THRESHOLD:
                    # Add the URL of the neighbor
                    neighbors.append(CLUSTERS[target_id])
        
        # 2. Push this list to the specific Cluster Manager
        try:
            payload = {"neighbors": neighbors}
            # Send POST request to the Cluster Manager
            resp = requests.post(f"{source_url}/update_vicinity", json=payload)
            results[f"cluster_{source_id}"] = "Success" if resp.status_code == 200 else "Failed"
        except Exception as e:
            results[f"cluster_{source_id}"] = f"Error: {str(e)}"
            
    return jsonify({
        "status": "Network Initialized", 
        "topology_results": results,
        "matrix_used": LATENCY_MATRIX
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
