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
    print(f"Worker {w_id} registered at {data['worker_url']}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    total_cpu = 0
    total_ram = 0
    avail_cpu = 0
    avail_ram = 0
    active_workers = 0

    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=2)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                active_workers += 1
        except:
            print(f"Worker {w_id} unreachable")

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_workers,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

@app.route('/run_container', methods=['POST'])
def run_container():
    data = request.json
    
    # 1. Select a worker (First available for now)
    target_worker = None
    if len(WORKERS) > 0:
        target_worker = list(WORKERS.keys())[0]

    if not target_worker:
        return jsonify({"status": "error", "message": "No workers registered"}), 500

    # 2. Forward request to Edge Node
    worker_url = WORKERS[target_worker]['url']
    print(f"Forwarding deployment to {target_worker} at {worker_url}")

    try:
        # We REMOVED the try/pass block. Now we catch and report errors.
        resp = requests.post(f"{worker_url}/allocate_resources", json=data, timeout=5)
        
        if resp.status_code == 200:
            return jsonify({
                "status": "deployed", 
                "target_worker": target_worker,
                "worker_response": resp.json()
            })
        else:
            return jsonify({"status": "failed", "reason": f"Edge Node returned {resp.status_code}"}), 500
            
    except Exception as e:
        print(f"DEPLOYMENT ERROR: {str(e)}")
        return jsonify({"status": "failed", "reason": f"Connection failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
