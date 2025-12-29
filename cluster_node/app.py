# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
PARENT_NODE = os.getenv('PARENT_NODE', 'central_node')

# State
MY_VICINITY = [] 
WORKERS = {}

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "workers": len(WORKERS)})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY[:] = data['neighbors']
        print(f"[{NODE_ID}] Updated Vicinity: {MY_VICINITY}")
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = {
        "url": data['worker_url'],
        "capacity": data['capacity']
    }
    print(f"[{NODE_ID}] Worker registered: {w_id}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    total_cpu = 0.0
    avail_cpu = 0.0
    total_ram = 0
    avail_ram = 0
    active_count = 0

    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                active_count += 1
        except:
            continue

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_count,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

@app.route('/run_container', methods=['POST'])
def run_container():
    # Input: { "req_cpu": 1.0, "req_ram": 100, "task_id": "unique_id", "is_offloaded": False }
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    is_offloaded = data.get('is_offloaded', False)

    print(f"[{NODE_ID}] Scheduling Request: {data.get('task_id')} (CPU={req_cpu}) | Offloaded: {is_offloaded}")

    # --- TIER 1: Local Deployment ---
    # We iterate ALL workers. If one fails, we try the next.
    for w_id, info in WORKERS.items():
        try:
            # 1. Check stats (Optimistic locking)
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                if stats['available']['cpu'] >= req_cpu and stats['available']['ram'] >= req_ram:
                    
                    # 2. Attempt Deployment
                    deploy_resp = requests.post(f"{info['url']}/run_task", json=data, timeout=2)
                    
                    if deploy_resp.status_code == 200:
                        return jsonify({
                            "status": "deployed_locally",
                            "target_worker": w_id,
                            "details": deploy_resp.json()
                        })
                    else:
                        print(f"[{NODE_ID}] Worker {w_id} rejected task (Full).")
        except Exception as e:
            print(f"Error checking worker {w_id}: {e}")

    # Stop here if this request came from another cluster (Prevent infinite ping-pong)
    if is_offloaded:
        return jsonify({"status": "failed", "reason": "Target Cluster Full"}), 503

    # --- TIER 2: Vicinity Offloading ---
    print(f"[{NODE_ID}] All Local Workers Full. Trying Vicinity: {MY_VICINITY}")
    
    offload_data = data.copy()
    offload_data['is_offloaded'] = True 

    for neighbor_url in MY_VICINITY:
        try:
            # We assume neighbor URL is like http://cluster_2:5000
            print(f"[{NODE_ID}] Offloading to {neighbor_url}...")
            offload_resp = requests.post(f"{neighbor_url}/run_container", json=offload_data, timeout=2)

            if offload_resp.status_code == 200:
                return jsonify({
                    "status": "scaled_vicinity",
                    "target_cluster": neighbor_url,
                    "scaling_response": offload_resp.json()
                })
        except Exception as e:
            print(f"Neighbor {neighbor_url} unreachable: {e}")

    # --- TIER 3: Global Scaling ---
    print(f"[{NODE_ID}] Vicinity Full. Requesting Global Scale from Central Node...")
    
    try:
        central_url = f"http://{PARENT_NODE}:5000/global_scale_request"
        global_req_data = offload_data.copy()
        global_req_data['requester_id'] = NODE_ID

        global_resp = requests.post(central_url, json=global_req_data, timeout=5)

        if global_resp.status_code == 200:
             return jsonify({
                "status": "scaled_global",
                "scaling_response": global_resp.json()
            })
    except Exception as e:
        print(f"Global scaling failed: {e}")

    return jsonify({"status": "failed", "reason": "System Saturated"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
