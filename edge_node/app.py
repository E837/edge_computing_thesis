# File: edge_node/app.py
from flask import Flask, request, jsonify
import os
import requests
import threading
import time

app = Flask(__name__)

# --- Configuration ---
NODE_ID = os.getenv('NODE_ID', 'unknown_edge')
PARENT_CLUSTER = os.getenv('PARENT_CLUSTER', 'cluster_1')

# Total Physical Capacity
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# Current Allocations
allocated_resources = {
    "cpu": 0.0,
    "ram": 0
}
TASKS = {} # Stores active tasks: { "task_id": { "cpu": 1.0, "ram": 100 } }

def register_with_cluster():
    """Registers this worker with its parent cluster manager."""
    time.sleep(3)
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    my_url = f"http://{os.getenv('HOSTNAME')}:5000"

    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": { "cpu": TOTAL_CPU, "ram": TOTAL_RAM }
    }
    try:
        requests.post(cluster_url, json=payload)
        print(f"[{NODE_ID}] Registered with {PARENT_CLUSTER}")
    except Exception as e:
        print(f"[{NODE_ID}] Registration failed: {e}")

threading.Thread(target=register_with_cluster, daemon=True).start()

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID})

@app.route('/stats')
def get_stats():
    """Returns current capacity and usage."""
    return jsonify({
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM},
        "allocated": allocated_resources,
        "available": {
            "cpu": TOTAL_CPU - allocated_resources['cpu'],
            "ram": TOTAL_RAM - allocated_resources['ram']
        }
    })

@app.route('/run_task', methods=['POST'])
def run_task():
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    task_id = data.get('task_id', 'unknown')

    available_cpu = TOTAL_CPU - allocated_resources['cpu']
    available_ram = TOTAL_RAM - allocated_resources['ram']

    # Strict Check
    if req_cpu > (available_cpu + 0.01) or req_ram > available_ram:
        return jsonify({
            "status": "failed", 
            "reason": "insufficient_resources_on_node"
        }), 400

    # Allocate
    allocated_resources['cpu'] += req_cpu
    allocated_resources['ram'] += req_ram
    TASKS[task_id] = { "cpu": req_cpu, "ram": req_ram }

    print(f"[{NODE_ID}] Allocated Task {task_id}: {req_cpu} CPU")

    return jsonify({
        "status": "allocated",
        "worker_id": NODE_ID,
        "current_state": allocated_resources
    })

# --- NEW: Scale Down Logic ---
@app.route('/terminate_task', methods=['POST'])
def terminate_task():
    data = request.json
    task_id = data.get('task_id')

    if task_id in TASKS:
        # 1. Get resources used by this task
        cpu_to_free = TASKS[task_id]['cpu']
        ram_to_free = TASKS[task_id]['ram']

        # 2. Release resources
        allocated_resources['cpu'] = max(0.0, allocated_resources['cpu'] - cpu_to_free)
        allocated_resources['ram'] = max(0, allocated_resources['ram'] - ram_to_free)
        
        # 3. Remove task
        del TASKS[task_id]
        print(f"[{NODE_ID}] Terminated Task {task_id}. Freed {cpu_to_free} CPU.")
        
        return jsonify({"status": "terminated", "freed_cpu": cpu_to_free})
    
    return jsonify({"status": "not_found", "error": "Task ID not found on this node"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
