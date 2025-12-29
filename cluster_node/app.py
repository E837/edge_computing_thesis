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

# --- NEW: Routing Table (Service Discovery) ---
# Maps task_id -> { "type": "local"|"remote", "url": "..." }
TASK_REGISTRY = {} 

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "workers": len(WORKERS)})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY[:] = data['neighbors']
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
        except Exception:
            continue

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_count,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

# --- NEW: Traffic Gateway (Load Balancer) ---
@app.route('/simulate_traffic', methods=['POST'])
def simulate_traffic():
    """
    Entry point for User Traffic.
    Routing Logic:
    1. Check if task is known in TASK_REGISTRY.
    2. If Local: Forward to Edge Node.
    3. If Remote (Vicinity): Forward to Neighbor Cluster.
    """
    data = request.json
    task_id = data.get('task_id')

    if task_id not in TASK_REGISTRY:
        return jsonify({"error": "Task not found in routing table", "registry": list(TASK_REGISTRY.keys())}), 404

    route = TASK_REGISTRY[task_id]
    target_url = route['url']
    
    print(f"[{NODE_ID}] Routing traffic for '{task_id}' -> {route['type']} ({target_url})")

    try:
        # If local, hit the worker directly
        if route['type'] == 'local':
            resp = requests.post(f"{target_url}/simulate_load", json=data, timeout=5)
            return jsonify(resp.json()), resp.status_code
        
        # If remote (neighbor), hit the neighbor's gateway
        elif route['type'] == 'remote':
            resp = requests.post(f"{target_url}/simulate_traffic", json=data, timeout=5)
            return jsonify(resp.json()), resp.status_code

    except Exception as e:
        return jsonify({"error": f"Routing failed: {str(e)}"}), 502


@app.route('/autoscale_request', methods=['POST'])
def autoscale_request():
    data = request.json
    task_id = data.get('task_id')
    needed_cpu = float(data.get('needed_cpu', 0))
    current_alloc = float(data.get('current_alloc', 0))
    worker_url = data.get('worker_url')

    MAX_CONTAINER_SIZE = 2.0 
    new_size = current_alloc + needed_cpu

    print(f"[{NODE_ID}] Autoscale Alert for {task_id}: Needs +{needed_cpu} CPU")

    if new_size <= MAX_CONTAINER_SIZE:
        print(f"[{NODE_ID}] Attempting Vertical Scale to {new_size}")
        try:
            resize_resp = requests.post(f"{worker_url}/resize_task", json={
                "task_id": task_id, "new_cpu": new_size
            })
            if resize_resp.status_code == 200:
                return jsonify({"status": "scaled_vertical", "new_size": new_size})
        except Exception as e:
            print(f"Vertical failed: {e}")

    print(f"[{NODE_ID}] Vertical limit reached. Triggering Horizontal/Global Scale...")
    
    replica_req = {
        "req_cpu": 1.0,
        "req_ram": 100,
        "task_id": f"{task_id}_replica"
    }
    return run_container(custom_data=replica_req)

@app.route('/run_container', methods=['POST'])
def run_container(custom_data=None):
    data = custom_data if custom_data else request.json
    
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    task_id = data.get('task_id', 'unknown_task')
    is_offloaded = data.get('is_offloaded', False)

    print(f"[{NODE_ID}] Scheduling Request: {task_id}")

    # --- TIER 1: Try Local Deployment ---
    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                avail_c = stats['available']['cpu']
                avail_r = stats['available']['ram']

                if avail_c >= req_cpu and avail_r >= req_ram:
                    deploy_resp = requests.post(f"{info['url']}/run_task", json=data)
                    if deploy_resp.status_code == 200:
                        
                        # UPDATE ROUTING TABLE (Local)
                        TASK_REGISTRY[task_id] = {
                            "type": "local",
                            "url": info['url']
                        }
                        
                        return jsonify({
                            "status": "deployed_locally",
                            "target_worker": w_id,
                            "details": deploy_resp.json()
                        })
        except Exception:
            continue

    if is_offloaded:
        return jsonify({"status": "failed", "reason": "Target Cluster Full"}), 503

    # --- TIER 2: Vicinity Offloading ---
    print(f"[{NODE_ID}] Local full. Checking Vicinity...")
    
    offload_data = data.copy()
    offload_data['is_offloaded'] = True 

    for neighbor_url in MY_VICINITY:
        try:
            offload_resp = requests.post(f"{neighbor_url}/run_container", json=offload_data, timeout=2)

            if offload_resp.status_code == 200:
                
                # UPDATE ROUTING TABLE (Remote)
                # We know this task lives in the neighbor cluster now
                TASK_REGISTRY[task_id] = {
                    "type": "remote",
                    "url": neighbor_url
                }

                return jsonify({
                    "status": "scaled_vicinity",
                    "target_cluster": neighbor_url,
                    "details": offload_resp.json()
                })
        except Exception:
            continue

    # --- TIER 3: Global Scaling ---
    print(f"[{NODE_ID}] Vicinity full. Requesting GLOBAL scaling...")
    
    try:
        central_url = f"http://{PARENT_NODE}:5000/global_scale_request"
        global_req_data = offload_data.copy()
        global_req_data['requester_id'] = NODE_ID
        
        global_resp = requests.post(central_url, json=global_req_data, timeout=5)
        
        if global_resp.status_code == 200:
             # NOTE: For global scaling, the routing is complex. 
             # Ideally, we get the target cluster URL back and update registry.
             target_cluster = global_resp.json().get('cluster_url')
             if target_cluster:
                 TASK_REGISTRY[task_id] = {
                     "type": "remote",
                     "url": target_cluster
                 }

             return jsonify({
                "status": "scaled_global",
                "details": global_resp.json()
            })
            
    except Exception as e:
        print(f"Global scaling failed: {e}")

    return jsonify({"status": "failed", "reason": "System-wide Saturation"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
