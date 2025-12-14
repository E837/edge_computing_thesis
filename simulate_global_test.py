# File: simulate_global_test.py
import requests
import time
import json

CENTRAL_URL = "http://localhost:5000"
C1_URL = "http://localhost:5001" # Mapped to 5001 in docker-compose? Check your compose file
# Assuming you mapped ports 5000-5009 in previous steps. 
# If not, use docker exec commands.
# To make it easier for this script, I will assume we use the exposed ports from previous steps.
# Cluster 1 -> 5001, Cluster 2 -> 5002, Cluster 3 -> 5003
# IF NOT MAPPED, WE USE 'docker exec' style via python's subprocess, 
# but let's assume direct HTTP for simplicity if ports are mapped.
# **CRITICAL**: If your docker-compose doesn't expose Cluster ports to host, 
# this script needs to be run INSIDE the network or use subprocess.

# Let's use the robust subprocess method to match previous successful tests
import subprocess

def docker_req(container, method, endpoint, data=None):
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

def print_section(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

# 1. Initialize
print_section("1. Initializing Network")
print(docker_req("central_node", "post", "/initialize_network"))

# 2. Fill Cluster 1 (Capacity 6.0)
print_section("2. Filling Cluster 1 (Local)")
# Task A: 3.5 CPU on Worker 1 (4 Core)
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 3.5, "req_ram": 100})
# Task B: 1.5 CPU on Worker 2 (2 Core)
docker_req("cluster_1", "post", "/run_container", {"req_cpu": 1.5, "req_ram": 100})
print("Cluster 1 Status (Should be Full):")
print(docker_req("cluster_1", "get", "/cluster_resources"))

# 3. Fill Cluster 2 (Vicinity - Capacity 6.0)
print_section("3. Filling Cluster 2 (Vicinity)")
# Task C: 3.5 CPU
docker_req("cluster_2", "post", "/run_container", {"req_cpu": 3.5, "req_ram": 100})
# Task D: 1.5 CPU
docker_req("cluster_2", "post", "/run_container", {"req_cpu": 1.5, "req_ram": 100})
print("Cluster 2 Status (Should be Full):")
print(docker_req("cluster_2", "get", "/cluster_resources"))

# 4. Trigger Global Scale
print_section("4. Triggering Global Scaling Test")
print("Sending massive task to Cluster 1.")
print("Expectation: C1 Full -> C2 Full -> Central -> C3 (Success)")

# We request 2.0 CPU. C1 has ~1.0 left (frag). C2 has ~1.0 left (frag). C3 is empty.
response = docker_req("cluster_1", "post", "/run_container", {"req_cpu": 2.5, "req_ram": 100, "task_id": "global_test_task"})
# my note here: If you change the 2.5 req_cpu to 2.0 ro less, it can be assigned to the edge node "6_c3" too

print("\n--- FINAL RESULT ---")
print(json.dumps(response, indent=2))

if response.get("status") == "scaled_global":
    print("\nSUCCESS: Global Scaling Activated!")
else:
    print("\nFAILURE: Did not scale globally.")
