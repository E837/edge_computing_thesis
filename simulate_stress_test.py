# File: simulate_stress_test.py
import requests
import time
import sys

# Configuration
CENTRAL_URL = "http://localhost:5000"
CLUSTER_1_URL = "http://localhost:5001"
# Edge Nodes in Cluster 1
EDGE_1_URL = "http://localhost:5004" # Capacity: 4.0 CPU
EDGE_2_URL = "http://localhost:5005" # Capacity: 2.0 CPU

def log(msg):
    print(f"[STRESS] {msg}")

def run():
    print("\n--- 🧪 STARTING THESIS STRESS TEST (VICINITY OFFLOADING) ---")

    # 1. Initialize Network (Calculate Neighbors)
    print("\n[1] Initializing Network Topology...")
    requests.post(f"{CENTRAL_URL}/initialize_network")
    time.sleep(2)

    # 2. Fill up Worker 1 (The "Big" Node)
    # Worker 1 has 4.0 CPU. We deploy a task needing 3.5 CPU.
    # Remaining: 0.5 CPU.
    log("🛑 Step 1: Filling Worker 1 (Allocating 3.5/4.0 CPU)...")
    res1 = requests.post(f"{CLUSTER_1_URL}/run_container", json={
        "req_cpu": 3.5, 
        "req_ram": 1000,
        "task_id": "heavy_background_task"
    })
    if res1.status_code == 200:
        print(f"    -> Success: {res1.json().get('target_worker')}")
    else:
        print(f"    -> Failed: {res1.text}")

    # 3. Fill up Worker 2 (The "Small" Node)
    # Worker 2 has 2.0 CPU. We deploy a task needing 1.5 CPU.
    # Remaining: 0.5 CPU.
    log("🛑 Step 2: Filling Worker 2 (Allocating 1.5/2.0 CPU)...")
    res2 = requests.post(f"{CLUSTER_1_URL}/run_container", json={
        "req_cpu": 1.5,
        "req_ram": 500,
        "task_id": "target_app" # This is the app we will stress test
    })
    target_worker = res2.json().get('target_worker')
    print(f"    -> Target App deployed on: {target_worker} (Expected: 2_c1)")
    
    time.sleep(2)

    # 4. Trigger The Overload
    # Current State of Cluster 1:
    # - Worker 1: 0.5 Free
    # - Worker 2: 0.5 Free
    # Total Free: 1.0 (Fragmented)
    #
    # We will simulate a user surge needing +1.0 CPU.
    # - Vertical Scale? Needs 1.5 + 1.0 = 2.5. Max Container is 2.0. -> FAILS.
    # - Horizontal Local? Needs 1.0. Worker 2 has 0.5. -> FAILS.
    # - Horizontal Cluster? Needs 1.0. Worker 1 has 0.5. -> FAILS.
    # - Vicinity? Should succeed to Cluster 2.
    
    log("🔥 Step 3: Triggering Massive Load Surge (+2.5 CPU)...")
    log("    Current Alloc: 1.5. New Load: 2.6. Need: +1.1.")
    log("    Logic: 1.5 + 1.1 > Max(2.0). Vertical Fail -> Vicinity Scale.")
    
    res3 = requests.post(f"{EDGE_2_URL}/simulate_load", json={
        "load_increase": 2.5  # <--- CHANGED FROM 1.0 TO 2.5
    })
    
    print("\n--- 🏁 FINAL RESULT ---")
    print(res3.text)

if __name__ == "__main__":
    run()