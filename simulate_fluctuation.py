# File: simulate_fluctuation.py
import subprocess
import json
import time

def docker_req(container, method, endpoint, data=None):
    """Helper to run curl/requests inside the docker network"""
    cmd = [
        "docker", "exec", container, 
        "python", "-c", 
        f"import requests; import json; print(requests.{method}('http://localhost:5000{endpoint}', json={json.dumps(data) if data else 'None'}).text)"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return result.stdout

def print_header(msg):
    print(f"\n{'='*60}\n{msg}\n{'='*60}")

# ==========================================
# TEST SCENARIO
# ==========================================

print_header("INITIALIZING NETWORK & TOPOLOGY")
print(docker_req("central_node", "post", "/initialize_network"))

print_header("STEP 1: SETUP - DEPLOY TARGET APP")
# We deploy "monitor_me" (1.0 CPU). 
# Cluster 1: Worker 1 (4.0), Worker 2 (2.0). Total 6.0.
# This usually goes to Worker 2.
task_id = "monitor_me"
deploy_payload = {"req_cpu": 1.0, "req_ram": 100, "task_id": task_id}

resp = docker_req("cluster_1", "post", "/run_container", deploy_payload)
print("Deployment Response:", json.dumps(resp, indent=2))

target_worker = resp.get("target_worker") 
if not target_worker:
    print("CRITICAL ERROR: App failed to deploy. Exiting.")
    exit()

# Map worker ID to container name
worker_container_map = {
    "1_c1": "edge_1_c1", "2_c1": "edge_2_c1",
    "3_c2": "edge_3_c2", "4_c2": "edge_4_c2",
    "5_c3": "edge_5_c3", "6_c3": "edge_6_c3"
}
target_container = worker_container_map.get(target_worker)
print(f"Target App is running on Container: {target_container}")

print_header("STEP 2: SATURATE LOCAL CLUSTER (CLUSTER 1)")
# Goal: Leave < 1.0 CPU free on any single worker.
# Current: 
#   Worker 1 (4.0): Empty
#   Worker 2 (2.0): Has 'monitor_me' (1.0 used, 1.0 free)

# 1. Fill Worker 1 (4.0 capacity). Deploy 3.5 CPU. Remaining: 0.5
print("Deploying Blocker A (3.5 CPU)...")
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 3.5, "req_ram": 100, "task_id": "blocker_A"})

# 2. Fill Worker 2 (2.0 capacity). It has 1.0 left. Deploy 0.5 CPU. Remaining: 0.5
print("Deploying Blocker B (0.5 CPU)...")
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 0.5, "req_ram": 100, "task_id": "blocker_B"})

# Now Cluster 1 should have roughly 1.0 CPU free TOTAL, but fragmented (0.5 on W1, 0.5 on W2).
# A replica needing 1.0 CPU CANNOT fit.
print("Cluster 1 Resources (Should show ~1.0 avail, but fragmented):")
print(docker_req("cluster_1", "get", "/cluster_resources"))

print_header("STEP 3: CHOOSE YOUR ADVENTURE")
mode = input("Select Test Mode:\n[1] Vicinity Test (Expect Replica on Cluster 2)\n[2] Global Test (Expect Replica on Cluster 3)\nEnter 1 or 2: ")

if mode == "2":
    print("\n--- GLOBAL MODE SELECTED ---")
    print("Filling Cluster 2 (Vicinity) so it cannot accept offloading...")
    # Cluster 2: Worker 3 (4.0), Worker 4 (2.0).
    # Fill W3
    docker_req("cluster_2", "post", "/run_container", {"req_cpu": 3.5, "req_ram": 100, "task_id": "blocker_c2_A"})
    # Fill W4
    docker_req("cluster_2", "post", "/run_container", {"req_cpu": 1.5, "req_ram": 100, "task_id": "blocker_c2_B"})
    
    print("Cluster 2 Resources (Should be full):")
    print(docker_req("cluster_2", "get", "/cluster_resources"))
else:
    print("\n--- VICINITY MODE SELECTED ---")
    print("Leaving Cluster 2 empty. It should catch the overflow.")

print_header("STEP 4: TRIGGER LOAD FLUCTUATION")
print(f"Applying massive load to '{task_id}' on {target_container}...")

# Increase Load by 2.5
# Logic:
# Current Load (0.1) + Increase (2.5) = 2.6
# Allocated (1.0)
# Overload = 2.6 > 1.0
# New Size Needed = 2.6
# Max Container Size = 2.0 (Defined in app.py)
# 2.6 > 2.0 -> VERTICAL FAIL -> TRIGGER HORIZONTAL
# Replica Request = 1.0 CPU.
# Cluster 1 Free = 0.5 (W1) + 0.5 (W2). No space for 1.0.
# Result -> OFFLOAD.
load_payload = {"load_increase": 2.5, "task_id": task_id}

scaling_result = docker_req(target_container, "post", "/simulate_load", load_payload)

print("\n--- SCALING RESULT ---")
print(json.dumps(scaling_result, indent=2))

status = scaling_result.get("scaling_response", {}).get("status")
details = scaling_result.get("scaling_response", {})

if status == "scaled_vicinity":
    print("\n✅ SUCCESS: Load Fluctuation triggered VICINITY Offloading!")
    print(f"Replica moved to: {details.get('target_cluster')}")
elif status == "scaled_global":
    print("\n✅ SUCCESS: Load Fluctuation triggered GLOBAL Offloading!")
    print(f"Replica assigned by Central Node to: {details.get('details', {}).get('assigned_cluster')}")
elif status == "deployed_locally":
    print("\n❌ FAILURE: It scaled locally (Cluster wasn't fully saturated).")
elif status == "scaled_vertical":
    print("\n❌ FAILURE: It scaled Vertically only (Max Container Size logic issue).")
else:
    print(f"\n⚠️ UNKNOWN RESULT: {status}")
