# File: simulate_thesis.py
import requests
import random
import time
import csv
import json

# Configuration
CENTRAL_NODE_URL = "http://localhost:5000"
TOTAL_TASKS = 50
CSV_FILENAME = "thesis_experiment_results.csv"

# Task Parameters (Randomized to create realistic load)
MIN_CPU = 0.5
MAX_CPU = 3.5 # Some tasks will be big, some small
RAM_REQ = 100

def initialize():
    print("--- Initializing Network ---")
    try:
        resp = requests.post(f"{CENTRAL_NODE_URL}/initialize_network")
        print(resp.text)
    except Exception as e:
        print(f"Error initializing: {e}")
        exit()

def get_cluster_status(cluster_id):
    try:
        resp = requests.get(f"http://localhost:5000/api/forward/{cluster_id}/cluster_resources")
        # Note: Since we are outside docker, we might not reach cluster_1 directly 
        # unless mapped. For this script, we just trust the deployment logs.
        pass 
    except:
        pass

def run_simulation():
    results = []
    print(f"\n--- Starting Simulation: {TOTAL_TASKS} Tasks ---")

    # Open CSV for writing
    with open(CSV_FILENAME, mode='w', newline='') as file:
        writer = csv.writer(file)
        # Header
        writer.writerow(["Task_ID", "Req_CPU", "Status", "Assigned_Cluster", "Offload_Type", "Latency_Seconds"])

        for i in range(1, TOTAL_TASKS + 1):
            # 1. Generate Random Task
            req_cpu = round(random.uniform(MIN_CPU, MAX_CPU), 1)
            
            print(f"Task {i}/{TOTAL_TASKS}: Requesting {req_cpu} CPU...", end=" ")
            
            start_time = time.time()
            
            try:
                # 2. Send to Central Node
                response = requests.post(
                    f"{CENTRAL_NODE_URL}/deploy_application",
                    json={"req_cpu": req_cpu, "req_ram": RAM_REQ},
                    timeout=20
                )
                
                end_time = time.time()
                latency = round(end_time - start_time, 4)
                data = response.json()
                
                # 3. Analyze Result
                status = data.get("status", "unknown")
                assigned_cluster = data.get("assigned_cluster", "N/A")
                
                # Determine if it was Vicinity Offloading
                offload_type = "Local"
                
                # Check deep inside the response structure for vicinity flags
                if "cluster_response" in data:
                    c_resp = data["cluster_response"]
                    # Check if the cluster response says "offloaded_vicinity"
                    if c_resp.get("status") == "offloaded_vicinity":
                        offload_type = "Vicinity_Offload"
                        # In vicinity offload, the 'assigned_cluster' is the original one, 
                        # but the work happened elsewhere.
                
                if status == "Deployment Failed":
                    offload_type = "Failed"
                    print(f"FAILED ({data.get('reason')})")
                else:
                    print(f"SUCCESS -> Cluster {assigned_cluster} ({offload_type}) - {latency}s")

                # 4. Log to CSV
                writer.writerow([i, req_cpu, status, assigned_cluster, offload_type, latency])
                results.append(data)

            except Exception as e:
                print(f"ERROR: {e}")
                writer.writerow([i, req_cpu, "Error", "N/A", "Error", 0])

            # Small delay to allow logs to print cleanly
            time.sleep(2.0)

    print(f"\n--- Simulation Complete. Results saved to {CSV_FILENAME} ---")

if __name__ == "__main__":
    initialize()
    # Optional: Reset docker containers manually before running if you want a clean slate
    run_simulation()

# todo: global offloading
# todo: errors in the results? (ERROR: 'str' object has no attribute 'get')
# todo: in fact, we are making requests again and again from the central node, 
# so we are simulating new applications, but we need dynamic load for currently deployed applications, 
# so that vicinity comes to help and stuff