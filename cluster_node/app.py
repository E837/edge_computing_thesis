# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
MY_VICINITY = []

# Dictionary to store registered workers
# Format: { "worker_id": { "url": "...", "capacity": {...} } }
WORKERS = {}

@app.route('/')
def health_check():
    return jsonify({
        "status": "online",
        "id": NODE_ID,
        "worker_count": len(WORKERS),
        "vicinity": MY_VICINITY
    })

# --- Vicinity Logic (From Step 2) ---
@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    global MY_VICINITY
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY = data['neighbors']
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "missing data"}), 400

# --- NEW: Monitoring Logic (Step 3) ---

@app.route('/register_worker', methods=['POST'])
def register_worker():
    """ Called by Edge Nodes when they start up """
    data = request.json
    w_id = data['worker_id']
    w_url = data['worker_url']
    w_cap = data['capacity']
    
    WORKERS[w_id] = {
        "url": w_url,
        "capacity": w_cap
    }
    print(f"Worker {w_id} registered. Total workers: {len(WORKERS)}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    """
    Aggregates resources from ALL registered edge workers.
    Used by Central Node (Algorithm 1) to decide deployment.
    """
    total_cpu = 0
    total_ram = 0
    avail_cpu = 0
    avail_ram = 0
    
    active_workers = 0

    # Query every worker for real-time stats
    for w_id, info in WORKERS.items():
        try:
            # Poll the worker
            resp = requests.get(f"{info['url']}/stats", timeout=2)
            if resp.status_code == 200:
                stats = resp.json()
                
                # Add to totals
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                active_workers += 1
        except:
            print(f"Worker {w_id} is unresponsive.")

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_workers,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

# --- NEW: Deploy Trigger ---
@app.route('/run_container', methods=['POST'])
def run_container():
    """
    Simulates running a container.
    In a real system, this would call Docker API.
    Here, we just log it. 
    (Note: To strictly follow the logic, we should deduct resources from a specific worker,
    but for this high-level simulation, we assume the Cluster Manager handles scheduling).
    """
    data = request.json
    req_cpu = data.get('req_cpu')
    
    # Find a worker to take this load (Simple Round Robin or First Fit)
    # For simplicity, we just pick the first capable worker
    target_worker = None
    for w_id, info in WORKERS.items():
        # In a real implementation, we would check worker specifics here again
        target_worker = w_id
        break
        
    if target_worker:
        print(f"Deploying app (CPU={req_cpu}) on Worker {target_worker}")
        # Ideally, we send a request to the Edge Node to increase its usage.
        # Let's simulate that notification:
        try:
            worker_url = WORKERS[target_worker]['url']
            requests.post(f"{worker_url}/allocate_resources", json=data)
        except:
            pass
            
        return jsonify({"status": "deployed", "target_worker": target_worker})
    
    return jsonify({"status": "error", "message": "No workers available"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
