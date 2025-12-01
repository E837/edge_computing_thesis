# File: edge_node/app.py
from flask import Flask, request, jsonify
import os
import requests
import threading
import time
import random

app = Flask(__name__)

# --- Configuration ---
NODE_ID = os.getenv('NODE_ID', 'unknown_edge')
PARENT_CLUSTER = os.getenv('PARENT_CLUSTER', 'cluster_1')

# Total Physical Capacity
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# --- State Management ---
# "allocated" is for Docker containers we explicitly deployed
allocated_resources = {
    "cpu": 0.0,
    "ram": 0
}

# "noise" simulates OS background processes (random fluctuation)
background_noise = {
    "cpu": 0.05, # Base noise
    "ram": 50
}

def register_with_cluster():
    """Registers this worker with its parent cluster manager."""
    time.sleep(5) # Give cluster time to boot
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
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

def simulate_background_fluctuation():
    """
    Periodically changes the 'noise' level to simulate dynamic OS load.
    This ensures the 'Available' resources are not static.
    """
    while True:
        # Randomly fluctuate CPU noise between 0.05 (5%) and 0.25 (25%) of a core
        new_cpu_noise = round(random.uniform(0.05, 0.25), 2)
        background_noise['cpu'] = new_cpu_noise
        time.sleep(5) # Update every 5 seconds

# Start background threads
threading.Thread(target=register_with_cluster, daemon=True).start()
threading.Thread(target=simulate_background_fluctuation, daemon=True).start()

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID})

@app.route('/stats')
def get_stats():
    """Returns current capacity minus allocated minus noise."""
    # Calculate Used
    used_cpu = allocated_resources['cpu'] + background_noise['cpu']
    used_ram = allocated_resources['ram'] + background_noise['ram']

    # Calculate Available (ensure non-negative)
    avail_cpu = max(0.0, TOTAL_CPU - used_cpu)
    avail_ram = max(0, TOTAL_RAM - used_ram)

    return jsonify({
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM},
        "allocated": allocated_resources,
        "noise": background_noise,
        "available": {
            "cpu": round(avail_cpu, 3),
            "ram": avail_ram
        }
    })

def release_resources(cpu_amt, ram_amt, duration):
    """
    Waits for 'duration' seconds, then frees the resources.
    """
    time.sleep(duration)
    
    # Critical Section: Update state
    allocated_resources['cpu'] = max(0.0, allocated_resources['cpu'] - cpu_amt)
    allocated_resources['ram'] = max(0, allocated_resources['ram'] - ram_amt)
    
    print(f"[{NODE_ID}] Task Finished. Released {cpu_amt} CPU. (Allocated now: {round(allocated_resources['cpu'], 2)})")

@app.route('/run_task', methods=['POST'])
def run_task():
    """
    Reserves resources for a specific DURATION.
    Input: { "req_cpu": 1, "req_ram": 100, "duration": 20 }
    """
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    duration = int(data.get('duration', 10)) # Default 10 seconds if not specified

    # 1. Check Availability (Including Noise)
    current_usage_cpu = allocated_resources['cpu'] + background_noise['cpu']
    current_usage_ram = allocated_resources['ram'] + background_noise['ram']
    
    avail_cpu = TOTAL_CPU - current_usage_cpu
    avail_ram = TOTAL_RAM - current_usage_ram

    # Buffer for float comparison issues
    if req_cpu > (avail_cpu + 0.01) or req_ram > avail_ram:
        return jsonify({
            "status": "failed",
            "reason": "insufficient_resources_on_node",
            "available": {"cpu": avail_cpu, "ram": avail_ram}
        }), 400

    # 2. Allocate
    allocated_resources['cpu'] += req_cpu
    allocated_resources['ram'] += req_ram
    
    print(f"[{NODE_ID}] Task Started: {req_cpu} CPU for {duration}s")

    # 3. Schedule Release (The "Runtime Dynamic" part)
    threading.Thread(
        target=release_resources, 
        args=(req_cpu, req_ram, duration), 
        daemon=True
    ).start()

    return jsonify({
        "status": "allocated",
        "duration": duration,
        "current_state": allocated_resources
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
