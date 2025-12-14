# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
# Artificial limit to force Horizontal scaling during tests
MAX_CONTAINER_SIZE = 2.0 

# State
MY_VICINITY = [] 
WORKERS = {}

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY[:] = data['neighbors']
        return jsonify({"status": "success"})
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = { "url": data['worker_url'], "capacity": data['capacity'] }
    print(f"[{NODE_ID}] Worker registered: {w_id}")
    return jsonify({"status": "registered"})

@app.route('/run_container', methods=['POST'])
def run_container():
    """Initial Deployment Logic (Local -> Vicinity)"""
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))

    # 1. Try Local
    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                avail_c = resp.json()['available']['cpu']
                if avail_c >= req_cpu:
                    deploy_resp = requests.post(f"{info['url']}/run_task", json=data)
                    if deploy_resp.status_code == 200:
                        return jsonify({
                            "status": "deployed_locally",
                            "target_worker": w_id
                        })
        except: continue

    # 2. Try Vicinity
    if not data.get('is_offloaded'):
        data['is_offloaded'] = True
        for neighbor in MY_VICINITY:
            try:
                print(f"[{NODE_ID}] Offloading to {neighbor}")
                resp = requests.post(f"{neighbor}/run_container", json=data, timeout=2)
                if resp.status_code == 200:
                    return jsonify({
                        "status": "scaled_vicinity", # Success Keyword!
                        "target_cluster": neighbor,
                        "details": resp.json()
                    })
            except: continue

    return jsonify({"status": "failed", "reason": "No capacity"}), 503

# --- NEW: The Autoscaling Decision Engine ---
@app.route('/autoscale_request', methods=['POST'])
def autoscale_request():
    """
    Called when an Edge Node is Overloaded.
    Logic: Scale Up (Vertical) -> Scale Out (Horizontal/Vicinity)
    """
    data = request.json
    print(f"[{NODE_ID}] 🚨 AUTOSCALE ALERT: {data}")
    
    task_id = data['task_id']
    current_alloc = data['current_alloc']
    needed = data['needed_cpu']
    source_node = data['source_node']
    
    # DECISION 1: Vertical Scaling (Scale Up)
    # If the new size is small enough, try to resize the existing container
    new_total = current_alloc + needed
    
    if new_total <= MAX_CONTAINER_SIZE:
        # Send resize command back to the edge node
        worker_url = WORKERS[source_node]['url']
        try:
            resp = requests.post(f"{worker_url}/resize_task", json={
                "task_id": task_id, "add_cpu": needed
            })
            if resp.status_code == 200:
                return jsonify({"status": "scaled_vertically", "new_size": new_total})
        except: pass
    
    # DECISION 2: Horizontal Scaling (Scale Out)
    # If Vertical failed or wasn't possible, we create a NEW replica.
    # We use /run_container which automatically handles Local -> Vicinity search.
    print(f"[{NODE_ID}] Vertical failed/maxed. Attempting Horizontal Scale.")
    
    replica_req = {
        "req_cpu": 1.0, # Standard replica size
        "req_ram": 100,
        "task_id": f"{task_id}_replica"
    }
    
    # This call will search Local, then search Neighbors
    return run_container_internal(replica_req)

def run_container_internal(data):
    """Internal helper to reuse the deployment logic without an HTTP request loop"""
    # Reuse the logic from run_container above
    with app.test_client() as c:
        resp = c.post('/run_container', json=data)
        return resp.get_json(), resp.status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
