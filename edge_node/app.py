# File: edge_node/app.py
from flask import Flask, request, jsonify
import os
import requests
import threading
import time

app = Flask(__name__)

# --- Configuration ---
# NODE_ID is usually passed from docker-compose (e.g., "1_c1")
NODE_ID = os.getenv('NODE_ID', 'unknown_edge')
PARENT_CLUSTER = os.getenv('PARENT_CLUSTER', 'cluster_1')

# Total Physical Capacity
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# Current Allocations (Simulated)
allocated_resources = {
    "cpu": 0.0,
    "ram": 0
}

def register_with_cluster():
    """Registers this worker with its parent cluster manager."""
    # We wait a bit for the cluster to be ready
    time.sleep(3)
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    
    # IMPORTANT: In Docker Compose, the hostname matches the service name usually,
    # but using the NODE_ID allows us to construct the URL explicitly if named consistently.
    # For this setup, we assume the container name is discoverable.
    # We send OUR address to the cluster.
    my_url = f"http://{os.getenv('HOSTNAME')}:5000" 
    
    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": {
            "cpu": TOTAL_CPU,
            "ram": TOTAL_RAM
        }
    }
    try:
        requests.post(cluster_url, json=payload)
        print(f"[{NODE_ID}] Registered with {PARENT_CLUSTER}")
    except Exception as e:
        print(f"[{NODE_ID}] Registration failed: {e}")

# Start registration in background
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
    """
    Actually reserves the resources.
    Input: { "req_cpu": 1, "req_ram": 100 }
    """
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))

    # STRICT CHECK: Do we have enough space?
    # We use a small buffer (0.01) for floating point comparisons
    available_cpu = TOTAL_CPU - allocated_resources['cpu']
    available_ram = TOTAL_RAM - allocated_resources['ram']

    if req_cpu > (available_cpu + 0.01) or req_ram > available_ram:
        return jsonify({
            "status": "failed",
            "reason": "insufficient_resources_on_node",
            "available": {"cpu": available_cpu, "ram": available_ram}
        }), 400

    # Allocate resources
    allocated_resources['cpu'] += req_cpu
    allocated_resources['ram'] += req_ram

    return jsonify({
        "status": "allocated",
        "current_state": allocated_resources
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
