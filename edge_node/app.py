# File: edge_node/app.py
from flask import Flask, jsonify
import os
import requests
import time
import threading
import random

app = Flask(__name__)

# 1. Load Configuration from Docker Environment Variables
NODE_ID = os.getenv('NODE_ID')
PARENT_CLUSTER = os.getenv('PARENT_CLUSTER') # e.g., "cluster_1"
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# 2. Simulate Current Usage (initially low)
current_usage = {
    "cpu": 0.1,  # 0.1 cores used
    "ram": 100   # 100 MB used
}

def register_with_cluster():
    """
    Tries to contact the Parent Cluster to say 'I am here and ready'.
    Retries until successful.
    """
    # In Docker, hostname is the service name (e.g., http://cluster_1:5000)
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    my_url = f"http://{os.getenv('HOSTNAME')}:5000" # Docker container hostname
    
    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM}
    }
    
    while True:
        try:
            response = requests.post(cluster_url, json=payload)
            if response.status_code == 200:
                print(f"Successfully registered with {PARENT_CLUSTER}")
                break
        except Exception as e:
            print(f"Waiting for {PARENT_CLUSTER} to come online... ({e})")
        time.sleep(3)

# Start registration in a background thread so Flask can start immediately
threading.Thread(target=register_with_cluster, daemon=True).start()

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID})

# 3. Endpoint for the Cluster Manager to check my stats
@app.route('/stats')
def get_stats():
    # Simulate some fluctuation in usage to make it realistic
    # (In a real system, we would read OS metrics here)
    fluctuation = random.uniform(-0.05, 0.05)
    current_usage['cpu'] = max(0, min(TOTAL_CPU, current_usage['cpu'] + fluctuation))
    
    return jsonify({
        "id": NODE_ID,
        "capacity": {
            "cpu": TOTAL_CPU, 
            "ram": TOTAL_RAM
        },
        "usage": current_usage,
        "available": {
            "cpu": TOTAL_CPU - current_usage['cpu'],
            "ram": TOTAL_RAM - current_usage['ram']
        }
    })

@app.route('/allocate_resources', methods=['POST'])
def allocate_resources():
    data = request.json
    req_cpu = data.get('req_cpu', 0)
    req_ram = data.get('req_ram', 0)
    
    # Increase simulated usage
    current_usage['cpu'] += req_cpu
    current_usage['ram'] += req_ram
    
    print(f"Resources allocated! New Usage: CPU={current_usage['cpu']}")
    return jsonify({"status": "allocated", "new_usage": current_usage})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
