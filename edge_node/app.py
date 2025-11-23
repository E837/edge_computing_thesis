# File: edge_node/app.py
from flask import Flask, request, jsonify
import os
import requests
import time
import threading
import random

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID')
PARENT_CLUSTER = os.getenv('PARENT_CLUSTER')
TOTAL_CPU = int(os.getenv('RESOURCES_CPU', 1))
TOTAL_RAM = int(os.getenv('RESOURCES_RAM', 1024))

# STATE: We separate "allocated" (persistent) from "noise" (fluctuation)
NODE_STATE = {
    "allocated_cpu": 0.0,
    "allocated_ram": 0
}

def register_with_cluster():
    cluster_url = f"http://{PARENT_CLUSTER}:5000/register_worker"
    # We explicitly use the hostname which Docker resolves to the container IP
    my_url = f"http://{os.getenv('HOSTNAME')}:5000"
    
    payload = {
        "worker_id": NODE_ID,
        "worker_url": my_url,
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM}
    }
    
    while True:
        try:
            requests.post(cluster_url, json=payload, timeout=5)
            print(f"Successfully registered with {PARENT_CLUSTER}")
            break
        except:
            time.sleep(3)

threading.Thread(target=register_with_cluster, daemon=True).start()

@app.route('/stats')
def get_stats():
    # 1. Base Usage (Simulating OS overhead)
    base_cpu = 0.1
    base_ram = 50

    # 2. Add Random Noise (Simulates real-world fluctuation)
    noise_cpu = random.uniform(0, 0.1) 
    
    # 3. Calculate Total Current Usage (Allocated + Base + Noise)
    current_cpu = NODE_STATE['allocated_cpu'] + base_cpu + noise_cpu
    current_ram = NODE_STATE['allocated_ram'] + base_ram
    
    # Cap at max limits
    current_cpu = min(TOTAL_CPU, current_cpu)
    current_ram = min(TOTAL_RAM, current_ram)

    return jsonify({
        "id": NODE_ID,
        "capacity": {"cpu": TOTAL_CPU, "ram": TOTAL_RAM},
        "usage": {"cpu": current_cpu, "ram": current_ram},
        "available": {
            "cpu": TOTAL_CPU - current_cpu,
            "ram": TOTAL_RAM - current_ram
        }
    })

@app.route('/allocate_resources', methods=['POST'])
def allocate_resources():
    data = request.json
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    
    # Persistently increase the allocated amount
    NODE_STATE['allocated_cpu'] += req_cpu
    NODE_STATE['allocated_ram'] += req_ram
    
    print(f"Accepted Task: +{req_cpu} CPU. Total Allocated: {NODE_STATE['allocated_cpu']}")
    
    return jsonify({
        "status": "allocated", 
        "current_state": NODE_STATE
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
