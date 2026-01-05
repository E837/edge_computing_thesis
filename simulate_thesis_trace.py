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
APP_ID = "thesis_app"
GATEWAY_CLUSTER = "cluster_1"

def docker_req(container, method, endpoint, data=None):
    """Helper to run requests inside the docker network"""
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

# ==========================================
# 1. SETUP
# ==========================================
print_header("INITIALIZING NETWORK")

# Initialize Vicinity
docker_req("central_node", "post", "/initialize_network")
time.sleep(2)

# Deploy Initial Application
print("--- Deploying Application ---")
deploy_resp = docker_req(GATEWAY_CLUSTER, "post", "/deploy_application", {
    "app_id": APP_ID,
    "req_cpu": 1.0,
    "req_ram": 100
})
print(f"Deployment Response: {deploy_resp}")
time.sleep(1)

# Initialize CSV
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
    
    print(f"\n[Minute {minute}] Sending {requests_count} requests to {APP_ID}...")
    
    # Send requests to cluster manager - IT handles all scaling logic
    resp = docker_req(GATEWAY_CLUSTER, "post", "/app_request", {
        "app_id": APP_ID,
        "request_count": requests_count
    })
    
    print(f"Response: {resp}")
    
    # Extract metrics from response
    allocated_cpu = resp.get('allocated_cpu', 0)
    replicas = resp.get('replicas', 0)
    status = resp.get('status', 'Unknown')
    worker_dist = ' | '.join(resp.get('replica_distribution', []))
    required_cpu = resp.get('required_cpu', 0)
    
    # Write to CSV
    with open(OUTPUT_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([minute, requests_count, required_cpu, allocated_cpu, replicas, status, worker_dist])
    
    time.sleep(0.5)

print_header("SIMULATION COMPLETE")
print(f"Results saved to: {OUTPUT_FILE}")
