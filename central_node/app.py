# File: central_node/app.py
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Config
CLUSTERS = {
    "1": "http://cluster_1:5000",
    "2": "http://cluster_2:5000",
    "3": "http://cluster_3:5000"
}

# Topology (Distance)
LATENCY_MATRIX = {
    "1": {"2": 10, "3": 50},
    "2": {"1": 10, "3": 15},
    "3": {"1": 50, "2": 15}
}
VICINITY_THRESHOLD = 20

@app.route('/')
def health_check():
    return jsonify({"status": "online", "role": "Central Cloud"})

@app.route('/initialize_network', methods=['POST'])
def initialize_network():
    results = {}
    for source_id, source_url in CLUSTERS.items():
        neighbors = []
        if source_id in LATENCY_MATRIX:
            for target_id, latency in LATENCY_MATRIX[source_id].items():
                if latency <= VICINITY_THRESHOLD:
                    neighbors.append(CLUSTERS[target_id])
        
        try:
            requests.post(f"{source_url}/update_vicinity", json={"neighbors": neighbors})
            results[f"cluster_{source_id}"] = "Success"
        except:
            results[f"cluster_{source_id}"] = "Failed"

    return jsonify({"status": "Network Initialized", "results": results})

@app.route('/cluster_resources')
def get_all_resources():
    # Helper to see status of all clusters
    report = {}
    for cid, url in CLUSTERS.items():
        try:
            resp = requests.get(f"{url}/cluster_resources", timeout=1)
            if resp.status_code == 200:
                report[f"cluster_{cid}"] = resp.json()
        except:
            report[f"cluster_{cid}"] = "Offline"
    return jsonify(report)

# --- NEW: Global Scaling Logic ---
@app.route('/global_scale_request', methods=['POST'])
def global_scale_request():
    """
    Called when a Cluster + its Vicinity are full.
    The Central Node looks for ANY cluster in the system with space.
    """
    data = request.json
    requester_id = data.get('requester_id', 'unknown')
    
    print(f"[Central] Global Scale Request from Cluster {requester_id}")

    # Iterate through ALL known clusters
    for cid, url in CLUSTERS.items():
        
        # Skip the cluster that asked for help (it's already full)
        if cid == requester_id:
            continue
            
        # Optimization: We could check latency here to find the "next closest" 
        # that wasn't in the strict vicinity, but for now we find "First Available".
        
        try:
            print(f"[Central] Checking candidate: Cluster {cid}...")
            # We send the request with 'is_offloaded=True' so the target 
            # only checks its local resources and doesn't forward it again.
            resp = requests.post(f"{url}/run_container", json=data, timeout=2)
            
            if resp.status_code == 200:
                print(f"[Central] Found space in Cluster {cid}!")
                return jsonify({
                    "status": "success",
                    "assigned_cluster": cid,
                    "cluster_url": url,
                    "target_response": resp.json()
                })
        except Exception as e:
            print(f"Failed to contact Cluster {cid}: {e}")

    return jsonify({"status": "failed", "reason": "No global resources available"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
