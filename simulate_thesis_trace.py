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

# COST HIERARCHY FOR SCALE DOWN (Algorithm 5)
CLUSTER_PRIORITY = {
    "c3": 10,  # Global (Remote) - Highest Cost (Kill First)
    "c2": 5,   # Vicinity - Medium Cost
    "c1": 1    # Local - Lowest Cost
}

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
    if isinstance(response, str): return "error"
    if "worker_id" in response: return response["worker_id"]
    if "target_worker" in response: return response["target_worker"]
    if "scaling_response" in response: return extract_worker_id(response["scaling_response"])
    if "target_response" in response: return extract_worker_id(response["target_response"])
    if "details" in response:
        if isinstance(response["details"], dict): return extract_worker_id(response["details"])
    return "unknown"

def get_container_name_from_id(worker_id):
    return f"edge_{worker_id}"

def get_kill_priority(task_obj):
    w_id = task_obj['worker']
    cluster_suffix = w_id.split('_')[-1]
    return CLUSTER_PRIORITY.get(cluster_suffix, 0)

# ==========================================
# 1. SETUP
# ==========================================
print_header("INITIALIZING NETWORK")

# Initialize Vicinity
docker_req("central_node", "post", "/initialize_network")
time.sleep(2)

print("--- Deploying Initial App Instance ---")
task_base_id = "thesis_app"
init_id = f"{task_base_id}_init"

init_resp = docker_req("cluster_1", "post", "/run_container", {
    "req_cpu": REPLICA_SIZE, 
    "req_ram": 100, 
    "task_id": init_id
})

active_tasks = []
first_worker = extract_worker_id(init_resp)
active_tasks.append({"task_id": init_id, "worker": first_worker})

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
    if required_cpu < 1.0: required_cpu = 1.0

    # Status tracking
    status_events = []
    
    # --- ALGORITHM 4: SCALE UP ---
    # We loop while we are UNDER provisioned
    while current_capacity < required_cpu:
        load_diff = required_cpu - current_capacity
        new_replica_id = f"{task_base_id}_m{minute}_r{current_replicas+1}"
        
        print(f"\n[Min {minute}] Demand: {required_cpu:.2f} > Current: {current_capacity:.2f} | Scaling UP...")

        payload = {"task_id": new_replica_id, "req_cpu": REPLICA_SIZE, "req_ram": 100}
        resp = docker_req(GATEWAY_NODE, "post", "/run_container", payload)
        
        action_status = str(resp).lower()
        
        if "deployed" in action_status or "scaled" in action_status or "success" in action_status:
            new_worker = extract_worker_id(resp)
            active_tasks.append({"task_id": new_replica_id, "worker": new_worker})
            
            current_replicas += 1
            current_capacity += REPLICA_SIZE
            
            if "vicinity" in action_status or "cluster_2" in str(resp):
                if "Scaled Vicinity" not in status_events: status_events.append("Scaled Vicinity")
                print(f"   >>> SUCCESS: Offloaded to Neighbor -> {new_worker}")
            elif "global" in action_status or "central" in str(resp):
                if "Scaled Global" not in status_events: status_events.append("Scaled Global")
                print(f"   >>> SUCCESS: Global Scale -> {new_worker}")
            else:
                if "Scaled Local" not in status_events: status_events.append("Scaled Local")
                print(f"   >>> SUCCESS: Local Replica -> {new_worker}")
        else:
            status_events.append("System Saturated")
            print("   >>> FAILURE: No resources available!")
            break 

    # --- ALGORITHM 5: SCALE DOWN ---
    # CORRECT LOGIC: Only kill if (Current - Replica_Size) >= Required
    # This ensures we don't kill a task and immediately become under-provisioned.
    
    while (current_capacity - REPLICA_SIZE) >= required_cpu and len(active_tasks) > 1:
        print(f"\n[Min {minute}] Demand: {required_cpu:.2f} | Current: {current_capacity:.2f} | Scaling DOWN...")
        
        # 1. Sort Tasks by Priority (Global First -> Vicinity -> Local)
        active_tasks.sort(key=get_kill_priority, reverse=True)
        
        # 2. Select Victim
        victim = active_tasks[0] 
        victim_worker = victim['worker']
        victim_id = victim['task_id']
        
        # 3. Kill it
        target_container = get_container_name_from_id(victim_worker)
        print(f"   >>> TERMINATING: {victim_id} on {victim_worker} (High Cost)")
        
        del_resp = docker_req(target_container, "post", "/terminate_task", {"task_id": victim_id})
        
        if "terminated" in str(del_resp):
            active_tasks.pop(0) 
            current_capacity -= REPLICA_SIZE
            current_replicas -= 1
            if "Scaled Down" not in status_events: status_events.append("Scaled Down")
        else:
            print(f"   >>> ERROR Terminating: {del_resp}")
            break

    # Final Status String
    if not status_events:
        final_status = "Stable"
    else:
        final_status = " + ".join(status_events)

    # Save Results
    workers_list = [t['worker'] for t in active_tasks]
    worker_str = " | ".join(workers_list)
    
    print(f"[Min {minute}] Req: {requests_count} ({required_cpu} CPU) | Alloc: {current_capacity} | Workers: {worker_str}")

    with open(OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([minute, requests_count, required_cpu, current_capacity, current_replicas, final_status, worker_str])

    time.sleep(0.2) 

print_header("SIMULATION COMPLETE")

# TODO: the simulation script shouldn't handle the scale down/up priority and it should be handled by the system