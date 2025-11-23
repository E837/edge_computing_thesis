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

# --- NEW: Algorithm 1 Implementation ---
@app.route('/deploy_application', methods=['POST'])
def deploy_application():
    """
    Algorithm 1: Deploy_Application_To_Cluster
    Input: JSON { "req_cpu": 1.5, "req_ram": 500 }
    Output: Assigned Cluster ID
    """
    data = request.json
    req_cpu = data.get('req_cpu', 0)
    req_ram = data.get('req_ram', 0)
    
    print(f"Received Request: Need CPU={req_cpu}, RAM={req_ram}")

    best_cluster = None
    max_available_cpu = -1 # Using "Most Free CPU" as a simple heuristic for "Lowest Workload"

    # Iterate through all known clusters (c1, c2, c3)
    for c_id, c_url in CLUSTERS.items():
        try:
            # 1. Query Cluster Manager (Line 6-7 of Algorithm 1)
            resp = requests.get(f"{c_url}/cluster_resources", timeout=2)
            if resp.status_code == 200:
                info = resp.json()
                avail = info['available_resources']
                
                print(f"Cluster {c_id} has CPU={avail['cpu']}, RAM={avail['ram']}")
                
                # 2. Check Feasibility (Line 9 of Algorithm 1)
                if avail['cpu'] >= req_cpu and avail['ram'] >= req_ram:
                    
                    # 3. Selection Strategy (Line 10-13: Select Best)
                    # Here we select the one with the MOST available CPU (Load Balancing)
                    if avail['cpu'] > max_available_cpu:
                        max_available_cpu = avail['cpu']
                        best_cluster = c_id
                        
        except Exception as e:
            print(f"Failed to contact Cluster {c_id}: {e}")

    # 4. Final Decision (Line 17)
    if best_cluster:
        # Notify the chosen cluster to actually run the app (Line 20)
        target_url = CLUSTERS[best_cluster]
        deploy_resp = requests.post(f"{target_url}/run_container", json=data)
        
        return jsonify({
            "status": "Deployment Successful",
            "assigned_cluster": best_cluster,
            "cluster_response": deploy_resp.json() if deploy_resp.status_code == 200 else "Error"
        })
    else:
        return jsonify({"status": "Deployment Failed", "reason": "No cluster has enough resources"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
