# File: simulate_gateway.py
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
# TEST SCENARIO: GATEWAY LOAD BALANCING
# ==========================================

print_header("INITIALIZING NETWORK")
print(docker_req("central_node", "post", "/initialize_network"))

print_header("STEP 1: DEPLOY APP VIA CLUSTER 1")
task_id = "user_app_1"
deploy_payload = {"req_cpu": 1.0, "req_ram": 100, "task_id": task_id}

# We ask Cluster 1 to run it.
resp = docker_req("cluster_1", "post", "/run_container", deploy_payload)
print("Deployment Response:", json.dumps(resp, indent=2))

if resp.get("status") != "deployed_locally":
    print("Error: App didn't deploy locally as expected.")
    exit()

print("\n(Note: Cluster 1 now knows that 'user_app_1' is on a local worker)")

print_header("STEP 2: FILL CLUSTER 1 (To Force Offloading later)")
# Fill Worker 1 (4.0) -> Deploy 3.5
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 3.5, "req_ram": 100, "task_id": "blocker_A"})
# Fill Worker 2 (2.0) -> Deploy 0.5 (Original app is 1.0, so 0.5 left)
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 0.5, "req_ram": 100, "task_id": "blocker_B"})

print("Cluster 1 is now fragmented (no space for > 0.5 CPU).")

print_header("STEP 3: USER SENDS TRAFFIC TO GATEWAY (CLUSTER 1)")
print(f"Simulating User Traffic to Cluster 1 for Task '{task_id}'...")

# The user does NOT know about edge_1_c1. The user only knows Cluster 1.
# Traffic: 2.5 Load Increase.
load_payload = {"load_increase": 2.5, "task_id": task_id}

# HIT THE GATEWAY ENDPOINT
gateway_response = docker_req("cluster_1", "post", "/simulate_traffic", load_payload)

print("\n--- GATEWAY RESPONSE ---")
print(json.dumps(gateway_response, indent=2))

# Validation
status = gateway_response.get("scaling_response", {}).get("status")
details = gateway_response.get("scaling_response", {})

if status == "scaled_vicinity":
    print("\n✅ SUCCESS: ")
    print("1. User hit Gateway (Cluster 1).")
    print("2. Gateway routed to Local Worker.")
    print("3. Worker detected overload.")
    print("4. Worker asked Cluster 1 for help.")
    print("5. Cluster 1 offloaded Replica to Vicinity (Cluster 2)!")
    print(f"Replica moved to: {details.get('target_cluster')}")
else:
    print(f"\n⚠️ Unexpected Status: {status}")
