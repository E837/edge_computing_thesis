# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
MY_VICINITY = []
WORKERS = {}

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "workers": len(WORKERS)})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY = data['neighbors']
        return jsonify({"status": "success", "vicinity_count": len(MY_VICINITY)}), 200
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = {
        "url": data['worker_url'],
        "capacity": data['capacity']
    }
    print(f"Worker {w_id} registered.")
    return jsonify({"status": "registered"}), 200

def calculate_local_resources():
    """Helper function to get current local stats"""
    total_cpu = 0
    avail_cpu = 0
    
    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                avail_cpu += stats['available']['cpu']
        except:
            pass
    return total_cpu, avail_cpu

@app.route('/cluster_resources')
def get_cluster_resources():
    # Aggregates resources for Central Node
    total_cpu = 0
    total_ram = 0
    avail_cpu = 0
    avail_ram = 0
    active_workers = 0

    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                active_workers += 1
        except:
            pass

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_workers,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

@app.route('/run_container', methods=['POST'])
def run_container():
    """
    Algorithm 4 Implementation:
    1. Try Local Allocation.
    2. If Local Fails -> Try Vicinity Offloading.
    """
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    
    # --- STEP 1: Check Local Resources ---
    _, local_avail = calculate_local_resources()
    print(f"Request: {req_cpu} CPU. Local Available: {local_avail}")

    # Simple heuristic: Do we have enough space locally?
    if local_avail >= req_cpu:
        # Logic to deploy locally
        target_worker = list(WORKERS.keys())[0] # Simplification: Pick first
        worker_url = WORKERS[target_worker]['url']
        
        try:
            resp = requests.post(f"{worker_url}/allocate_resources", json=data, timeout=5)
            if resp.status_code == 200:
                return jsonify({
                    "status": "deployed_locally", 
                    "target_worker": target_worker
                })
        except Exception as e:
            print(f"Local deployment error: {e}")

    # --- STEP 2: Vicinity Offloading (Algorithm 4) ---
    print(f"Local Cluster {NODE_ID} Overloaded! Attempting Vicinity Offload...")
    
    # Check 'is_offloaded' to prevent infinite loops (Ping-Pong effect)
    if data.get('is_offloaded'):
        return jsonify({"status": "failed", "reason": "Already offloaded once, stopping chain"}), 503

    # Mark request as offloaded
    offload_data = data.copy()
    offload_data['is_offloaded'] = True

    for neighbor_url in MY_VICINITY:
        try:
            print(f"Checking Neighbor: {neighbor_url}")
            # 1. Ask Neighbor if they have space (Query their /cluster_resources)
            res_check = requests.get(f"{neighbor_url}/cluster_resources", timeout=2)
            if res_check.status_code == 200:
                neighbor_stats = res_check.json()
                neighbor_avail = neighbor_stats['available_resources']['cpu']
                
                if neighbor_avail >= req_cpu:
                    # 2. Neighbor has space! Offload the task.
                    print(f"Offloading to {neighbor_url}...")
                    deploy_resp = requests.post(f"{neighbor_url}/run_container", json=offload_data, timeout=5)
                    
                    if deploy_resp.status_code == 200:
                        return jsonify({
                            "status": "offloaded_vicinity",
                            "original_cluster": NODE_ID,
                            "assigned_neighbor": neighbor_url,
                            "neighbor_response": deploy_resp.json()
                        })
        except Exception as e:
            print(f"Failed to contact neighbor {neighbor_url}: {e}")

    return jsonify({"status": "failed", "reason": "Cluster Full & Vicinity Full"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
