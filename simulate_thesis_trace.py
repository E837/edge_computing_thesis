# File: simulate_thesis_trace.py
import csv
import time
import json
import subprocess
import pandas as pd
import sys

# --- CONFIGURATION ---
CSV_FILE = "test_log_bursts_modified.csv"
OUTPUT_FILE = "thesis_simulation_results.csv"

# RATIO: 100 Requests = 1.0 CPU
REQUESTS_TO_CPU_RATIO = 0.01  
REPLICA_SIZE = 1.0 
GATEWAY_NODE = "cluster_1"

def docker_req(container, method, endpoint, data=None):
    """Helper to run curl/requests inside the docker network"""
    cmd = [
        "docker", "exec", container, 
        "python", "-c", 
        f"import requests; import json; print(requests.{method}('http://localhost:5000{endpoint}', json={json.dumps(data) if data else 'None'}, timeout=10).text)"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": "unreachable", "raw": result.stdout}

def print_header(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")

def extract_worker_id(response):
    """Parses complex nested JSON to find who handled the request"""
    if isinstance(response, str): return "error"
    if "target_worker" in response: return response["target_worker"]
    if "scaling_response" in response: return extract_worker_id(response["scaling_response"])
    if "details" in response:
        if isinstance(response["details"], dict): return extract_worker_id(response["details"])
    if "worker_id" in response: return response["worker_id"]
    return "unknown"

# ==========================================
# 1. SETUP
# ==========================================
print_header("INITIALIZING NETWORK (High Load Scenario)")

# Initialize Vicinity
docker_req("central_node", "post", "/initialize_network")
time.sleep(2)

print("--- Deploying Initial App Instance ---")
# Initial Task ID
task_base_id = "thesis_app"
init_resp = docker_req("cluster_1", "post", "/run_container", {
    "req_cpu": REPLICA_SIZE, 
    "req_ram": 100, 
    "task_id": f"{task_base_id}_init"
})

active_workers = [] 
first_worker = extract_worker_id(init_resp)
active_workers.append(first_worker)

current_capacity = REPLICA_SIZE
current_replicas = 1

print(f"Initial Deployment on: {first_worker}")

with open(OUTPUT_FILE, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Minute", "Requests", "Required_CPU", "Allocated_CPU", "Replicas", "Status", "Worker_Distribution"])

# ==========================================
# 2. RUN SIMULATION LOOP
# ==========================================
print_header("STARTING TRACE SIMULATION")

try:
    df = pd.read_csv(CSV_FILE)
    df.columns = df.columns.str.strip() 
except Exception as e:
    print(f"Error reading CSV: {e}")
    sys.exit(1)

for index, row in df.iterrows():
    minute = index + 1
    try:
        requests_count = int(row['request_count'])
    except KeyError:
        break

    # Calculate Demand
    required_cpu = round(requests_count * REQUESTS_TO_CPU_RATIO, 2)
    
    # Ensure minimum 1 replica
    if required_cpu < 1.0: required_cpu = 1.0

    status = "Stable"
    
    # --- SCALING LOOP ---
    # We spawn NEW replicas until we meet demand
    while current_capacity < required_cpu:
        load_diff = required_cpu - current_capacity
        
        # CRITICAL FIX: Generate UNIQUE ID for every replica
        # This forces the Edge Node to stack memory, not overwrite it.
        new_replica_id = f"{task_base_id}_m{minute}_r{current_replicas+1}"
        
        print(f"\n[Min {minute}] Demand: {required_cpu:.2f} | Current: {current_capacity:.2f} | Spawning Replica...")

        payload = {
            "task_id": new_replica_id,
            "req_cpu": REPLICA_SIZE,
            "req_ram": 100
        }
        
        # Send Request to Cluster 1 (Gateway)
        # We call run_container directly to simulate a new pod scheduling request
        resp = docker_req(GATEWAY_NODE, "post", "/run_container", payload)
        
        action_status = str(resp).lower()
        
        if "deployed" in action_status or "scaled" in action_status or "success" in action_status:
            new_worker = extract_worker_id(resp)
            active_workers.append(new_worker)
            current_replicas += 1
            current_capacity += REPLICA_SIZE
            
            if "vicinity" in action_status or "cluster_2" in str(resp):
                status = "Scaled Vicinity"
                print(f"   >>> SUCCESS: Offloaded to Neighbor -> {new_worker}")
            elif "global" in action_status or "central" in str(resp):
                status = "Scaled Global"
                print(f"   >>> SUCCESS: Global Scale -> {new_worker}")
            else:
                status = "Scaled Local"
                print(f"   >>> SUCCESS: Local Replica -> {new_worker}")
                
        elif "failed" in action_status or "503" in action_status:
            status = "System Saturated"
            print("   >>> FAILURE: No resources available anywhere!")
            break 
        else:
             print(f"   >>> UNKNOWN RESPONSE: {resp}")
             break

    if current_capacity > required_cpu + 1.5:
        status = "Over-provisioned"

    # Save Results
    worker_str = " | ".join(active_workers)
    print(f"[Min {minute}] Req: {requests_count} | Workers: {worker_str}")

    with open(OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([minute, requests_count, required_cpu, current_capacity, current_replicas, status, worker_str])

    time.sleep(0.5) 

print_header("SIMULATION COMPLETE")
