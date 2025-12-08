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
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))
MAX_CONTAINER_CPU = 2.0 # Artificial limit to force Horizontal Scaling tests

# --- State ---
allocated_resources = { "cpu": 0.0, "ram": 0 }
# TASKS: { "task_id": { "allocated_cpu": 1.0, "current_load": 0.5, "ram": 100 } }
TASKS = {} 

def register_with_cluster():
    time.sleep(3)
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    my_url = f"http://{os.getenv('HOSTNAME')}:5000"
    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM}
    }
    try:
        requests.post(cluster_url, json=payload)
        print(f"[{NODE_ID}] Registered with {PARENT_CLUSTER}")
    except Exception as e:
        print(f"[{NODE_ID}] Registration failed: {e}")

threading.Thread(target=register_with_cluster, daemon=True).start()

@app.route('/stats')
def get_stats():
    return jsonify({
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM},
        "allocated": allocated_resources,
        "available": {
            "cpu": TOTAL_CPU - allocated_resources['cpu'],
            "ram": TOTAL_RAM - allocated_resources['ram']
        },
        "tasks": TASKS
    })

@app.route('/run_task', methods=['POST'])
def run_task():
    """Initial deployment or Scale Out replica placement"""
    data = request.json
    task_id = data.get('task_id') # Crucial for tracking
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))

    avail_cpu = TOTAL_CPU - allocated_resources['cpu']
    avail_ram = TOTAL_RAM - allocated_resources['ram']

    if req_cpu > (avail_cpu + 0.01) or req_ram > avail_ram:
        return jsonify({"status": "failed", "reason": "insufficient_resources"}), 400

    allocated_resources['cpu'] += req_cpu
    allocated_resources['ram'] += req_ram
    
    TASKS[task_id] = {
        "allocated_cpu": req_cpu,
        "current_load": 0.1, # Starts low
        "ram": req_ram
    }

    print(f"[{NODE_ID}] Deployed Task {task_id}. Alloc: {req_cpu}")
    return jsonify({"status": "allocated", "node_id": NODE_ID})

@app.route('/resize_task', methods=['POST'])
def resize_task():
    """Vertical Scaling Action"""
    data = request.json
    task_id = data.get('task_id')
    add_cpu = float(data.get('add_cpu', 0))
    
    if task_id not in TASKS:
        return jsonify({"status": "failed", "reason": "task_not_found"}), 404

    # Check capacity
    avail_cpu = TOTAL_CPU - allocated_resources['cpu']
    if add_cpu > (avail_cpu + 0.01):
        return jsonify({"status": "failed", "reason": "node_full_for_vertical"}), 400
        
    # Apply Resize
    TASKS[task_id]['allocated_cpu'] += add_cpu
    allocated_resources['cpu'] += add_cpu
    print(f"[{NODE_ID}] 🔼 Vertical Scale SUCCESS for {task_id}. New Size: {TASKS[task_id]['allocated_cpu']}")
    
    return jsonify({"status": "success", "new_size": TASKS[task_id]['allocated_cpu']})

@app.route('/simulate_load', methods=['POST'])
def simulate_load():
    """
    Simulates users hitting the app. 
    If load > allocation, triggers autoscaling request to Cluster Manager.
    """
    data = request.json
    task_id = data.get('task_id')
    load_increase = float(data.get('load_increase', 0))
    
    if task_id not in TASKS:
        return jsonify({"error": "Task not found"}), 404
        
    task = TASKS[task_id]
    task['current_load'] += load_increase
    
    print(f"[{NODE_ID}] 📊 Task {task_id} Load: {task['current_load']:.2f} / Alloc: {task['allocated_cpu']:.2f}")

    # --- AUTOSCALING TRIGGER LOGIC ---
    if task['current_load'] > task['allocated_cpu']:
        deficit = task['current_load'] - task['allocated_cpu']
        print(f"[{NODE_ID}] ⚠️ OVERLOAD DETECTED on {task_id}. Deficit: {deficit:.2f}. Requesting Scale...")
        
        # Call Cluster Manager to handle the decision
        try:
            scale_payload = {
                "source_node": NODE_ID,
                "task_id": task_id,
                "needed_cpu": deficit,
                "current_alloc": task['allocated_cpu']
            }
            # We assume the cluster manager is the parent
            resp = requests.post(f"http://{PARENT_CLUSTER}:5000/autoscale_request", json=scale_payload, timeout=2)
            return jsonify({"status": "overload_reported", "scaling_response": resp.json()})
        except Exception as e:
            print(f"Autoscale request failed: {e}")
            return jsonify({"status": "error_contacting_cluster_manager"}), 500

    return jsonify({"status": "load_updated", "current_load": task['current_load']})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
