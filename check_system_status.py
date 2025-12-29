# File: check_system_status.py
import subprocess
import json

def docker_req(container, method, endpoint):
    """Helper to run curl/requests inside the docker network"""
    cmd = [
        "docker", "exec", container, 
        "python", "-c", 
        f"import requests; import json; print(requests.{method}('http://localhost:5000{endpoint}', timeout=1).text)"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except:
        return {"error": "unreachable", "raw": result.stdout}

def print_row(name, cpu_cap, cpu_avail, ram_cap, ram_avail, tasks):
    """Helper to print a formatted table row"""
    cpu_str = f"{cpu_avail:.2f}/{cpu_cap:.2f}"
    ram_str = f"{ram_avail}/{ram_cap}"
    print(f"{name:<15} | {cpu_str:<12} | {ram_str:<12} | {tasks}")

print(f"\n{'='*70}")
print(f"{'NODE NAME':<15} | {'CPU (Av/Tot)':<12} | {'RAM (Av/Tot)':<12} | {'TASKS / NOTES'}")
print(f"{'='*70}")

# --- CLUSTER 1 NODES ---
# Edge 1 (4 CPU) - Should have Blocker A (3.5)
stats = docker_req("edge_1_c1", "get", "/stats")
print_row("edge_1_c1", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: Blocker A")

# Edge 2 (2 CPU) - Should have User App + Blocker B + HIGH LOAD
stats = docker_req("edge_2_c1", "get", "/stats")
print_row("edge_2_c1", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: User App (High Load)")

print(f"{'-'*70}")

# --- CLUSTER 2 NODES ---
# Edge 3 (4 CPU) - Should be empty
stats = docker_req("edge_3_c2", "get", "/stats")
print_row("edge_3_c2", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: Empty")

# Edge 4 (2 CPU) - Should have the REPLICA (Offloaded)
stats = docker_req("edge_4_c2", "get", "/stats")
print_row("edge_4_c2", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: REPLICA HERE")

print(f"{'-'*70}")

# --- CLUSTER 3 NODES ---
# Edge 5 & 6 - Should be empty
stats = docker_req("edge_5_c3", "get", "/stats")
print_row("edge_5_c3", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: Empty")

stats = docker_req("edge_6_c3", "get", "/stats")
print_row("edge_6_c3", 
          stats['capacity']['cpu'], stats['available']['cpu'], 
          stats['capacity']['ram'], stats['available']['ram'],
          "Expected: Empty")

print(f"{'='*70}\n")
