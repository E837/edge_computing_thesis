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
TOTAL_CPU = float(os.getenv('RESOURCES_CPU', 1.0))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# --- State ---
# We track specific tasks now, not just raw numbers
TASKS = {}  # { "task_id": { "cpu": 1.0, "ram": 100, "current_load": 0.5 } }
allocated_resources = { "cpu": 0.0, "ram": 0 }

def register_with_cluster():
    """Continuously tries to register with the cluster manager."""
    time.sleep(5) # Wait for cluster to start
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    my_url = f"http://{os.getenv('HOSTNAME')}:5000"

    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": { "cpu": TOTAL_CPU, "ram": TOTAL_RAM }
    }
    
    while True:
        try:
            requests.post(cluster_url, json=payload, timeout=2)
            print(f"[{NODE_ID}] Registered with {PARENT_CLUSTER}")
            break
        except:
            time.sleep(5)

threading.Thread(target=register_with_cluster, daemon=True).start()

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "tasks": len(TASKS)})

@app.route('/stats')
def get_stats():
    """Returns real-time capacity."""
    # Recalculate usage based on tasks
    used_cpu = sum(t['cpu'] for t in TASKS.values())
    used_ram = sum(t['ram'] for t in TASKS.values())
    
    return jsonify({
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM},
        "allocated": {"cpu": used_cpu, "ram": used_ram},
        "available": {
            "cpu": TOTAL_CPU - used_cpu,
            "ram": TOTAL_RAM - used_ram
        }
    })

@app.route('/run_task', methods=['POST'])
def run_task():
    """Deploys a new task and SAVES it in the TASKS dict."""
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    # Use provided ID or generate one
    task_id = data.get('task_id', f"task_{int(time.time())}")

    used_cpu = sum(t['cpu'] for t in TASKS.values())
    used_ram = sum(t['ram'] for t in TASKS.values())

    # 1. Check Capacity
    if (used_cpu + req_cpu) > TOTAL_CPU + 0.1: # Small buffer
        return jsonify({"status": "failed", "reason": "insufficient_cpu"}), 400

    # 2. Store Task
    TASKS[task_id] = {
        "cpu": req_cpu,
        "ram": req_ram,
        "current_load": 0.1 # Start with low load
    }
    
    print(f"[{NODE_ID}] Task Started: {task_id} (Alloc: {req_cpu} CPU)")
    return jsonify({"status": "deployed", "task_id": task_id})

@app.route('/resize_task', methods=['POST'])
def resize_task():
    """Vertical Scaling handler."""
    data = request.json
    t_id = data.get('task_id')
    add_cpu = float(data.get('add_cpu', 0))
    
    if t_id in TASKS:
        TASKS[t_id]['cpu'] += add_cpu
        TASKS[t_id]['current_load'] = TASKS[t_id]['cpu'] * 0.8 # Reset load
        print(f"[{NODE_ID}] Vertical Scale: {t_id} new size {TASKS[t_id]['cpu']}")
        return jsonify({"status": "resized"})
    return jsonify({"error": "task_not_found"}), 404

@app.route('/simulate_load', methods=['POST'])
def simulate_load():
    """
    Increases load on a task. 
    If load > allocated_cpu, triggers AUTOSCALE REQUEST.
    """
    data = request.json
    increase = float(data.get('load_increase', 0))
    
    # If no specific task ID is sent, grab the first one (simplifies testing)
    if not TASKS:
        return jsonify({"error": "Task not found"}), 404
        
    target_id = data.get('task_id', list(TASKS.keys())[0])
    
    if target_id not in TASKS:
        return jsonify({"error": "Task not found"}), 404

    # Update Load
    task = TASKS[target_id]
    task['current_load'] += increase
    
    print(f"[{NODE_ID}] Task {target_id} Load: {task['current_load']:.2f} / {task['cpu']:.2f}")

    # CHECK FOR OVERLOAD
    if task['current_load'] > task['cpu']:
        needed = task['current_load'] - task['cpu'] + 0.5 # Request a bit extra
        print(f"[{NODE_ID}] 🚨 OVERLOAD! Requesting scale for {target_id}")
        
        # Call Parent Cluster to Scale
        try:
            resp = requests.post(
                f"http://{PARENT_CLUSTER}:5000/autoscale_request",
                json={
                    "source_node": NODE_ID,
                    "task_id": target_id,
                    "current_alloc": task['cpu'],
                    "needed_cpu": needed
                },
                timeout=1
            )
            return jsonify({
                "status": "overload_reported", 
                "scaling_response": resp.json()
            })
        except Exception as e:
            return jsonify({"status": "cluster_unreachable", "error": str(e)})

    return jsonify({"status": "load_updated", "current_load": task['current_load']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
