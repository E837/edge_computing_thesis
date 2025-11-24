# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')

# State
MY_VICINITY = [] # List of neighbor URLs
WORKERS = {}     # Dict of registered workers: { "worker_id": { "url": "...", "capacity": {...} } }

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "workers": len(WORKERS)})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    """Central node pushes the list of neighbors here."""
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY[:] = data['neighbors'] # Update list in place
        print(f"[{NODE_ID}] Updated Vicinity: {MY_VICINITY}")
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    """Workers register themselves here on startup."""
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = {
        "url": data['worker_url'],
        "capacity": data['capacity'] # Store max capacity
    }
    print(f"[{NODE_ID}] Worker registered: {w_id}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    """
    Aggregates stats from all workers to send to Central Node.
    Fixes the missing RAM bug.
    """
    total_cpu = 0.0
    avail_cpu = 0.0
    total_ram = 0
    avail_ram = 0
    active_count = 0

    for w_id, info in WORKERS.items():
        try:
            # Query the worker for real-time stats
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                
                # Aggregate Totals
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                
                # Aggregate Available
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                
                active_count += 1
        except Exception:
            # If a worker is down, we just skip it
            continue

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_count,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram} 
    })

@app.route('/run_container', methods=['POST'])
def run_container():
    """
    Algorithm 4: Logic to run task locally OR offload to vicinity.
    Input: { "req_cpu": 4, "req_ram": 100 }
    """
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))

    print(f"[{NODE_ID}] Received Task Request: CPU={req_cpu}, RAM={req_ram}")

    # --- STEP 1: Try Local Deployment (Smart Fit) ---
    # We must iterate through workers and find one that has enough SPECIFIC capacity.
    
    for w_id, info in WORKERS.items():
        try:
            # Check stats first
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                avail_c = stats['available']['cpu']
                avail_r = stats['available']['ram']

                # Check if THIS specific worker fits the task
                if avail_c >= req_cpu and avail_r >= req_ram:
                    # Attempt to deploy
                    deploy_resp = requests.post(f"{info['url']}/run_task", json=data)
                    if deploy_resp.status_code == 200:
                        return jsonify({
                            "status": "deployed_locally",
                            "target_worker": w_id,
                            "worker_response": deploy_resp.json()
                        })
        except Exception as e:
            print(f"Error checking worker {w_id}: {e}")
            continue

    # --- STEP 2: Vicinity Offloading (Algorithm 4) ---
    # If we are here, NO local worker could take the task.
    print(f"[{NODE_ID}] Local deployment failed. Checking Vicinity: {MY_VICINITY}")

    for neighbor_url in MY_VICINITY:
        try:
            # Check neighbor resources WITHOUT deploying yet
            # We ask the neighbor's cluster manager for its aggregate stats
            # (Or we could just try to push the container and see if it accepts)
            
            # Optimization: Just try to push to neighbor's /run_container endpoint.
            # The neighbor will run this same logic (Local check).
            # To prevent infinite loops, we might want to add a flag like "forwarded=True"
            # but for this simulation, usually 1 hop is enough.
            
            # Note: We are forwarding the EXACT same JSON request to the neighbor
            print(f"[{NODE_ID}] Offloading to neighbor: {neighbor_url}")
            offload_resp = requests.post(f"{neighbor_url}/run_container", json=data, timeout=2)
            
            if offload_resp.status_code == 200:
                resp_data = offload_resp.json()
                # If the neighbor said "failed", keep looking. If "deployed...", success.
                if "deployed" in resp_data.get("status", "") or "offloaded" in resp_data.get("status", ""):
                    return jsonify({
                        "status": "offloaded_vicinity",
                        "target_cluster": neighbor_url,
                        "details": resp_data
                    })
        except Exception as e:
            print(f"Neighbor {neighbor_url} unreachable: {e}")

    # --- STEP 3: Total Failure ---
    return jsonify({
        "status": "failed",
        "reason": "Cluster Full & Vicinity Full or Incompatible"
    }), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
