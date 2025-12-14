# File: simulate_thesis.py
import requests
import random
import time
import csv
import threading
import json

# Configuration
CENTRAL_NODE_URL = "http://localhost:5000"
TOTAL_TASKS = 50
CSV_FILENAME = "thesis_experiment_results.csv"

# Task Parameters
MIN_CPU = 0.5
MAX_CPU = 3.5
RAM_REQ = 100
MIN_DURATION = 10 
MAX_DURATION = 30 
SLEEP_BETWEEN_TASKS = 3 

def initialize():
    print("--- Initializing Network ---")
    try:
        resp = requests.post(f"{CENTRAL_NODE_URL}/initialize_network")
        print(resp.text)
    except Exception as e:
        print(f"Error initializing: {e}")
        exit()

# --- NEW: Background Logger ---
def log_release(duration, cpu, worker_id):
    """
    Waits for the duration, then prints that resources are back.
    """
    time.sleep(duration)
    # We print a newline first to ensure it doesn't mess up the current task line too much
    print(f"\n[EVENT] ♻️  Resources Freed: {cpu} CPU from {worker_id}")

def run_simulation():
    results = []
    print(f"\n--- Starting Simulation: {TOTAL_TASKS} Tasks ---")
    print(f"Task Duration: {MIN_DURATION}s - {MAX_DURATION}s")
    print(f"Arrival Rate: 1 task every ~{SLEEP_BETWEEN_TASKS}s")

    with open(CSV_FILENAME, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Task_ID", "Req_CPU", "Duration", "Status", "Assigned_Cluster", "Offload_Type", "Latency_Seconds"])

        for i in range(1, TOTAL_TASKS + 1):
            req_cpu = round(random.uniform(MIN_CPU, MAX_CPU), 1)
            duration = random.randint(MIN_DURATION, MAX_DURATION)
            
            print(f"Task {i}: {req_cpu} CPU / {duration}s ...", end=" ", flush=True)
            
            start_time = time.time()
            status = "Unknown"
            assigned_cluster = "N/A"
            offload_type = "N/A"
            latency = 0
            
            try:
                # Send Request
                payload = {
                    "req_cpu": req_cpu, 
                    "req_ram": RAM_REQ,
                    "duration": duration
                }
                
                # Increased timeout to handle network congestion
                response = requests.post(
                    f"{CENTRAL_NODE_URL}/deploy_application",
                    json=payload,
                    timeout=30 
                )
                
                end_time = time.time()
                latency = round(end_time - start_time, 4)

                # --- ROBUST RESPONSE HANDLING ---
                try:
                    data = response.json()
                except ValueError:
                    # If response is not JSON (e.g. 500 Error HTML), handle gracefully
                    print(f"ERROR: Invalid JSON response")
                    status = "System_Error"
                    writer.writerow([i, req_cpu, duration, status, "N/A", "Error", 0])
                    time.sleep(SLEEP_BETWEEN_TASKS)
                    continue

                # Analyze Data
                status = data.get("status", "unknown")
                assigned_cluster = data.get("assigned_cluster", "N/A")
                
                # Determine Offload Type and specific Worker ID
                target_worker_id = "Unknown"
                
                if status == "Deployment Failed":
                    offload_type = "Failed"
                    print(f"FAILED ({data.get('reason')})")
                else:
                    # Dig deeper to find the worker ID for the log
                    if "cluster_response" in data:
                        c_resp = data["cluster_response"]
                        
                        # CASE A: Vicinity Offload
                        if c_resp.get("status") == "offloaded_vicinity":
                            offload_type = "Vicinity_Offload"
                            # In vicinity, the worker ID is nested in 'details'
                            if "details" in c_resp:
                                target_worker_id = c_resp["details"].get("target_worker", "neighbor_node")
                        
                        # CASE B: Local Deployment
                        elif "deployed" in c_resp.get("status", ""):
                            offload_type = "Local"
                            target_worker_id = c_resp.get("target_worker", "local_node")

                    print(f"SUCCESS -> Cluster {assigned_cluster} ({offload_type})")

                    # --- TRIGGER THE RELEASE LOG ---
                    # Start a background thread to print the release message later
                    threading.Thread(
                        target=log_release, 
                        args=(duration, req_cpu, target_worker_id), 
                        daemon=True
                    ).start()

                # Log to CSV
                writer.writerow([i, req_cpu, duration, status, assigned_cluster, offload_type, latency])

            except Exception as e:
                print(f"ERROR: Connection Failed ({str(e)})")
                writer.writerow([i, req_cpu, duration, "Connection_Error", "N/A", "Error", 0])

            time.sleep(SLEEP_BETWEEN_TASKS)

    # Wait a bit at the end for remaining logs to print
    print("\n--- Simulation Requests Complete. Waiting for final tasks to release... ---")
    time.sleep(MAX_DURATION)
    print(f"--- Done. Results saved to {CSV_FILENAME} ---")

if __name__ == "__main__":
    initialize()
    run_simulation()
