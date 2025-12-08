# File: simulate_lifecycle.py
import requests
import time
import json
import random

CENTRAL_URL = "http://localhost:5000"
CLUSTER_1_URL = "http://localhost:5001" # Mapped port for Cluster 1

def log(msg):
    print(f"[TEST] {msg}")

def run_simulation():
    log("Initializing Network...")
    requests.post(f"{CENTRAL_URL}/initialize_network")
    time.sleep(5)

    # 1. Initial Deployment
    task_id = "App_Netflix_Stream"
    log(f"🚀 Deploying Initial App '{task_id}' (Req: 1.0 CPU)...")
    
    payload = {"req_cpu": 1.0, "req_ram": 100, "task_id": task_id}
    resp = requests.post(f"{CLUSTER_1_URL}/run_container", json=payload)
    
    if resp.status_code != 200:
        log("Initial deployment failed. Exiting.")
        return
        
    data = resp.json()
    target_worker = data.get('target_worker')
    log(f"✅ Deployed on Worker: {target_worker}")

    # We need to find the URL of the worker to send load updates
    # In a real scenario, we'd route through ingress. 
    # Here, we assume standard port mapping for simulation:
    # 1_c1 -> localhost:5004 (Cluster 1 Node 1)
    # 2_c1 -> localhost:5005 (Cluster 1 Node 2)
    # We will "guess" the port based on the worker ID for this script
    
    # Mapping based on your docker-compose logic
    # Adjust these ports if your docker-compose differs!
    # Usually: 
    # cluster_1: 5001
    # 1_c1: 5004, 2_c1: 5005
    # cluster_2: 5002
    # 3_c2: 5006, 4_c2: 5007
    
    worker_port_map = {
        "1_c1": 5004, "2_c1": 5005,
        "3_c2": 5006, "4_c2": 5007,
        "5_c3": 5008, "6_c3": 5009
    }
    
    target_port = worker_port_map.get(target_worker)
    if not target_port:
        log(f"Could not map worker {target_worker} to localhost port. Ensure ports are exposed in docker-compose.")
        return

    worker_url = f"http://localhost:{target_port}"

    # 2. Ramping Up Load (Simulating Users)
    # Current Allocation: 1.0. Max Container: 2.0. Node Cap: 4.0 or 2.0.
    
    load_steps = [
        0.5,  # Total 1.5 (Vertical Scale should handle this)
        0.8,  # Total 2.3 (Exceeds Max Cont Size 2.0 -> Should Horizontal Scale Local/Cluster)
        2.0,  # Huge Spike (Should force Vicinity if Cluster is full)
    ]

    current_simulated_load = 1.0 # Initial usage match

    for increase in load_steps:
        time.sleep(4)
        log(f"📈 INCREASING LOAD by +{increase} CPU...")
        
        try:
            # We hit the Edge Node directly to simulate "User Traffic"
            load_payload = {
                "task_id": task_id,
                "load_increase": increase
            }
            res = requests.post(f"{worker_url}/simulate_load", json=load_payload)
            
            print(json.dumps(res.json(), indent=2))
            
            # Allow time for the background threads to settle
            time.sleep(2)
            
        except Exception as e:
            log(f"Communication error: {e}")

    log("Simulation Complete. Check Cluster Logs for 'AUTOSCALE ALERT' messages.")

if __name__ == "__main__":
    run_simulation()
