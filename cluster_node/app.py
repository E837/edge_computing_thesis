# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
# Artificial limit for a single container to force Vertical/Horizontal scaling logic
MAX_CONTAINER_SIZE = 2.0 

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
        print(f"[{NODE_ID}] Vicinity Updated: {MY_VICINITY}")
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = { "url": data['worker_url'], "capacity": data['capacity'] }
    print(f"[{NODE_ID}] Worker registered: {w_id}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    total_cpu = 0.0; avail_cpu = 0.0; total_ram = 0; avail_ram = 0
    active_count = 0
    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                avail_cpu += stats['available']['cpu']
                total_ram += stats['capacity']['ram']
                avail_ram += stats['available']['ram']
                active_count += 1
        except: continue
    return jsonify({
        "cluster_id": NODE_ID, "active_workers": active_count,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

@app.route('/run_container', methods=['POST'])
def run_container():
    """
    Standard Placement for NEW applications.
    Logic: Try Local Workers -> Try Vicinity
    """
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))

    print(f"[{NODE_ID}] Placement Request: {req_cpu} CPU")

    # 1. Try Local Workers
    for w_id, info in WORKERS.items():
        try:
            # Check real-time stats
            stats = requests.get(f"{info['url']}/stats", timeout=1).json()
            if stats['available']['cpu'] >= req_cpu and stats['available']['ram'] >= req_ram:
                # Deploy
                dep = requests.post(f"{info['url']}/run_task", json=data)
                if dep.status_code == 200:
                    print(f"[{NODE_ID}] ✅ Deployed locally on {w_id}")
                    # KEY FIX: Return 'target_worker' so the test script can find it
                    return jsonify({"status": "deployed_locally", "target_worker": w_id})
        except Exception as e:
            print(f"Error checking {w_id}: {e}")
            continue
    
    # 2. Try Vicinity Offloading
    if not data.get('is_offloaded', False):
        print(f"[{NODE_ID}] Local full. Trying Vicinity: {MY_VICINITY}")
        data['is_offloaded'] = True
        for neigh in MY_VICINITY:
            try:
                resp = requests.post(f"{neigh}/run_container", json=data, timeout=2)
                if resp.status_code == 200:
                    resp_data = resp.json()
                    # KEY FIX: Pass through the target_worker from the neighbor
                    target = resp_data.get('target_worker')
                    print(f"[{NODE_ID}] ➡ Offloaded to {neigh} -> {target}")
                    return jsonify({"status": "offloaded", "target_worker": target})
            except: continue

    print(f"[{NODE_ID}] ❌ Placement Failed")
    return jsonify({"status": "failed", "reason": "no_resources"}), 400


# --- AUTOSCALING LOGIC (Runtime Lifecycle) ---
@app.route('/autoscale_request', methods=['POST'])
def autoscale_request():
    data = request.json
    source_node = data['source_node']
    task_id = data['task_id']
    needed_cpu = float(data['needed_cpu'])
    current_alloc = float(data['current_alloc'])
    
    print(f"[{NODE_ID}] ⚡ AUTOSCALE ALERT from {source_node} (Task {task_id}). Need +{needed_cpu:.2f} CPU.")

    # 1. ATTEMPT VERTICAL SCALING (Scale Up)
    if (current_alloc + needed_cpu) <= MAX_CONTAINER_SIZE:
        worker_url = WORKERS[source_node]['url']
        try:
            print(f"[{NODE_ID}] ... Attempting Vertical Scale on {source_node}")
            resp = requests.post(f"{worker_url}/resize_task", json={"task_id": task_id, "add_cpu": needed_cpu})
            if resp.status_code == 200:
                print(f"[{NODE_ID}] ✅ Vertical Scaling SUCCESS.")
                return jsonify({"status": "scaled_vertically", "node": source_node})
        except Exception as e:
            print(f"Error contacting worker: {e}")

    # 2. ATTEMPT HORIZONTAL SCALING (New Replica)
    print(f"[{NODE_ID}] ... Vertical failed/skipped. Attempting Horizontal (Replica).")
    replica_id = f"{task_id}_rep_{os.urandom(2).hex()}"
    replica_req = { "task_id": replica_id, "req_cpu": needed_cpu, "req_ram": 50 }

    # Search Local
    for w_id, info in WORKERS.items():
        try:
            stats = requests.get(f"{info['url']}/stats", timeout=1).json()
            if stats['available']['cpu'] >= needed_cpu:
                dep_resp = requests.post(f"{info['url']}/run_task", json=replica_req)
                if dep_resp.status_code == 200:
                    decision = "horizontal_local" if w_id == source_node else "horizontal_cluster"
                    print(f"[{NODE_ID}] ✅ {decision.upper()} SUCCESS on {w_id}.")
                    return jsonify({"status": decision, "target_worker": w_id})
        except: continue

    # 3. ATTEMPT VICINITY
    print(f"[{NODE_ID}] ... Cluster full. Attempting Vicinity Offload.")
    for neighbor_url in MY_VICINITY:
        try:
            resp = requests.post(f"{neighbor_url}/run_container", json=replica_req, timeout=2)
            if resp.status_code == 200:
                 print(f"[{NODE_ID}] ✅ VICINITY SCALE SUCCESS to {neighbor_url}.")
                 return jsonify({"status": "scaled_vicinity", "target_cluster": neighbor_url})
        except: continue

    print(f"[{NODE_ID}] ❌ ALL SCALING METHODS FAILED.")
    return jsonify({"status": "failed", "reason": "global_exhaustion"}), 503

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
