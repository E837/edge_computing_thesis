# File: cluster_node/app.py
from flask import Flask, request, jsonify
import os
import requests
import threading
import time
from collections import defaultdict

app = Flask(__name__)

NODE_ID = os.getenv('NODE_ID', 'unknown')
PARENT_NODE = os.getenv('PARENT_NODE', 'central_node')

# State
MY_VICINITY = []
WORKERS = {}

# Cluster URL Mapping (for indirect termination)
CLUSTER_URLS = {
    "1": "http://cluster_1:5000",
    "2": "http://cluster_2:5000",
    "3": "http://cluster_3:5000"
}

# --- Application Tracking ---
APPLICATIONS = {}
REPLICA_SIZE = 1.0
REQUESTS_TO_CPU_RATIO = 0.01

# Cost Priority for Scale Down
COST_HIERARCHY = {
    "local": 1,
    "vicinity": 5,
    "global": 10
}

def classify_worker_location(worker_id):
    """Determine if a worker is local, vicinity, or global"""
    if '_' not in worker_id:
        return "unknown"
    
    cluster_suffix = worker_id.split('_')[-1]
    my_suffix = f"c{NODE_ID}"
    
    if cluster_suffix == my_suffix:
        return "local"
    
    for neighbor_url in MY_VICINITY:
        neighbor_id = neighbor_url.split('_')[-1].split(':')[0]
        if cluster_suffix == f"c{neighbor_id}":
            return "vicinity"
    
    return "global"

def get_worker_cluster_id(worker_id):
    """Extract cluster ID from worker_id. E.g., '3_c2' -> '2'"""
    if '_' not in worker_id:
        return None
    cluster_suffix = worker_id.split('_')[-1]  # "c2"
    if cluster_suffix.startswith('c'):
        return cluster_suffix[1:]  # "2"
    return None

@app.route('/')
def health_check():
    return jsonify({"status": "online", "id": NODE_ID, "workers": len(WORKERS)})

@app.route('/update_vicinity', methods=['POST'])
def update_vicinity():
    data = request.json
    if 'neighbors' in data:
        MY_VICINITY[:] = data['neighbors']
        print(f"[{NODE_ID}] Updated Vicinity: {MY_VICINITY}")
        return jsonify({"status": "success"}), 200
    return jsonify({"error": "missing data"}), 400

@app.route('/register_worker', methods=['POST'])
def register_worker():
    data = request.json
    w_id = data['worker_id']
    WORKERS[w_id] = {
        "url": data['worker_url'],
        "capacity": data['capacity']
    }
    print(f"[{NODE_ID}] Worker registered: {w_id}")
    return jsonify({"status": "registered"}), 200

@app.route('/cluster_resources')
def get_cluster_resources():
    total_cpu = 0.0
    avail_cpu = 0.0
    total_ram = 0
    avail_ram = 0
    active_count = 0

    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                total_cpu += stats['capacity']['cpu']
                total_ram += stats['capacity']['ram']
                avail_cpu += stats['available']['cpu']
                avail_ram += stats['available']['ram']
                active_count += 1
        except:
            continue

    return jsonify({
        "cluster_id": NODE_ID,
        "active_workers": active_count,
        "total_capacity": {"cpu": total_cpu, "ram": total_ram},
        "available_resources": {"cpu": avail_cpu, "ram": avail_ram}
    })

@app.route('/deploy_application', methods=['POST'])
def deploy_application():
    """Deploy initial instance of an application"""
    data = request.json
    app_id = data.get('app_id')
    req_cpu = float(data.get('req_cpu', REPLICA_SIZE))
    req_ram = int(data.get('req_ram', 100))
    
    if app_id in APPLICATIONS:
        return jsonify({"error": "Application already deployed"}), 400
    
    task_id = f"{app_id}_init"
    deploy_data = {
        "task_id": task_id,
        "req_cpu": req_cpu,
        "req_ram": req_ram,
        "is_offloaded": False
    }
    
    result = run_container_internal(deploy_data)
    
    if result['status_code'] == 200:
        worker_id = extract_worker_id(result['response'])
        location = classify_worker_location(worker_id)
        
        APPLICATIONS[app_id] = {
            "replicas": [{
                "task_id": task_id,
                "worker_id": worker_id,
                "location": location,
                "cpu": req_cpu
            }],
            "request_queue": [],
            "total_capacity": req_cpu,
            "replica_size": req_cpu
        }
        
        print(f"[{NODE_ID}] Application '{app_id}' deployed on {worker_id} ({location})")
        return jsonify({"status": "deployed", "app_id": app_id, "worker": worker_id})
    
    return jsonify(result['response']), result['status_code']

@app.route('/app_request', methods=['POST'])
def app_request():
    """Handle incoming user requests for an application"""
    data = request.json
    app_id = data.get('app_id')
    request_count = int(data.get('request_count', 0))
    
    if app_id not in APPLICATIONS:
        return jsonify({"error": "Application not found. Deploy it first."}), 404
    
    app = APPLICATIONS[app_id]
    
    required_cpu = max(1.0, round(request_count * REQUESTS_TO_CPU_RATIO, 2))
    current_capacity = app['total_capacity']
    
    print(f"\n[{NODE_ID}] App '{app_id}' | Requests: {request_count} | Required: {required_cpu} | Current: {current_capacity}")
    
    actions = []
    
    # --- ALGORITHM 4: SCALE UP ---
    while current_capacity < required_cpu:
        print(f"[{NODE_ID}] Scaling UP for '{app_id}'...")
        
        replica_num = len(app['replicas']) + 1
        new_task_id = f"{app_id}_r{replica_num}"
        
        deploy_data = {
            "task_id": new_task_id,
            "req_cpu": app['replica_size'],
            "req_ram": 100,
            "is_offloaded": False
        }
        
        result = run_container_internal(deploy_data)
        
        if result['status_code'] == 200:
            worker_id = extract_worker_id(result['response'])
            location = classify_worker_location(worker_id)
            
            app['replicas'].append({
                "task_id": new_task_id,
                "worker_id": worker_id,
                "location": location,
                "cpu": app['replica_size']
            })
            
            current_capacity += app['replica_size']
            app['total_capacity'] = current_capacity
            
            action_msg = f"Scaled {location.upper()}: {worker_id}"
            actions.append(action_msg)
            print(f"[{NODE_ID}] {action_msg}")
        else:
            actions.append("Scale UP FAILED - System Saturated")
            print(f"[{NODE_ID}] Scale UP failed")
            break
    
    # --- ALGORITHM 5: SCALE DOWN ---
    while (current_capacity - app['replica_size']) >= required_cpu and len(app['replicas']) > 1:
        print(f"[{NODE_ID}] Scaling DOWN for '{app_id}'...")
        
        # Sort by cost priority (Global > Vicinity > Local)
        app['replicas'].sort(key=lambda r: COST_HIERARCHY.get(r['location'], 0), reverse=True)
        
        victim = app['replicas'][0]
        
        print(f"[{NODE_ID}] Terminating: {victim['task_id']} on {victim['worker_id']} ({victim['location']})")
        
        # --- KEY FIX: Route termination based on location ---
        success = False
        
        if victim['location'] == 'local':
            # Direct termination (we own this worker)
            worker_info = WORKERS.get(victim['worker_id'])
            if worker_info:
                try:
                    term_resp = requests.post(
                        f"{worker_info['url']}/terminate_task",
                        json={"task_id": victim['task_id']},
                        timeout=2
                    )
                    if term_resp.status_code == 200:
                        success = True
                except Exception as e:
                    print(f"[{NODE_ID}] Error terminating local task: {e}")
        
        else:  # vicinity or global
            # Indirect termination (ask the owner cluster)
            target_cluster_id = get_worker_cluster_id(victim['worker_id'])
            
            if target_cluster_id and target_cluster_id in CLUSTER_URLS:
                target_cluster_url = CLUSTER_URLS[target_cluster_id]
                try:
                    print(f"[{NODE_ID}] Requesting Cluster {target_cluster_id} to terminate {victim['task_id']}")
                    term_resp = requests.post(
                        f"{target_cluster_url}/terminate_remote_task",
                        json={
                            "task_id": victim['task_id'],
                            "worker_id": victim['worker_id']
                        },
                        timeout=3
                    )
                    if term_resp.status_code == 200:
                        success = True
                except Exception as e:
                    print(f"[{NODE_ID}] Error requesting remote termination: {e}")
        
        if success:
            app['replicas'].pop(0)
            current_capacity -= app['replica_size']
            app['total_capacity'] = current_capacity
            actions.append(f"Scaled DOWN: {victim['location']}")
            print(f"[{NODE_ID}] Successfully terminated {victim['task_id']}")
        else:
            print(f"[{NODE_ID}] Failed to terminate {victim['task_id']}")
            break
    
    # Summary
    status_msg = " + ".join(actions) if actions else "Stable"
    replica_locations = [f"{r['worker_id']}({r['location']})" for r in app['replicas']]
    
    return jsonify({
        "app_id": app_id,
        "request_count": request_count,
        "required_cpu": required_cpu,
        "allocated_cpu": current_capacity,
        "replicas": len(app['replicas']),
        "status": status_msg,
        "replica_distribution": replica_locations
    })

# --- NEW: Remote Task Termination Endpoint ---
@app.route('/terminate_remote_task', methods=['POST'])
def terminate_remote_task():
    """
    Called by another cluster to terminate a task on our workers.
    This is how cross-cluster termination works.
    """
    data = request.json
    task_id = data.get('task_id')
    worker_id = data.get('worker_id')
    
    print(f"[{NODE_ID}] Received termination request for {task_id} on {worker_id}")
    
    # Check if we own this worker
    worker_info = WORKERS.get(worker_id)
    if not worker_info:
        return jsonify({"error": f"Worker {worker_id} not registered in this cluster"}), 404
    
    # Forward termination to the worker
    try:
        term_resp = requests.post(
            f"{worker_info['url']}/terminate_task",
            json={"task_id": task_id},
            timeout=2
        )
        
        if term_resp.status_code == 200:
            print(f"[{NODE_ID}] Successfully terminated {task_id} on {worker_id}")
            return jsonify({"status": "terminated", "task_id": task_id}), 200
        else:
            return jsonify({"error": "Worker failed to terminate task"}), 500
    except Exception as e:
        print(f"[{NODE_ID}] Error forwarding termination: {e}")
        return jsonify({"error": str(e)}), 500

def extract_worker_id(response):
    """Extract worker ID from deployment response"""
    if isinstance(response, str):
        return "error"
    if "worker_id" in response:
        return response["worker_id"]
    if "target_worker" in response:
        return response["target_worker"]
    if "scaling_response" in response:
        return extract_worker_id(response["scaling_response"])
    if "target_response" in response:
        return extract_worker_id(response["target_response"])
    if "details" in response and isinstance(response["details"], dict):
        return extract_worker_id(response["details"])
    return "unknown"

def run_container_internal(data):
    """Internal method for running container"""
    req_cpu = float(data.get('req_cpu', 0))
    req_ram = int(data.get('req_ram', 0))
    is_offloaded = data.get('is_offloaded', False)
    
    # TIER 1: Local Deployment
    for w_id, info in WORKERS.items():
        try:
            resp = requests.get(f"{info['url']}/stats", timeout=1)
            if resp.status_code == 200:
                stats = resp.json()
                if stats['available']['cpu'] >= req_cpu and stats['available']['ram'] >= req_ram:
                    deploy_resp = requests.post(f"{info['url']}/run_task", json=data, timeout=2)
                    
                    if deploy_resp.status_code == 200:
                        return {
                            "status_code": 200,
                            "response": {
                                "status": "deployed_locally",
                                "target_worker": w_id,
                                "details": deploy_resp.json()
                            }
                        }
        except Exception as e:
            continue
    
    if is_offloaded:
        return {"status_code": 503, "response": {"status": "failed", "reason": "Target Cluster Full"}}
    
    # TIER 2: Vicinity Offloading
    offload_data = data.copy()
    offload_data['is_offloaded'] = True
    
    for neighbor_url in MY_VICINITY:
        try:
            offload_resp = requests.post(f"{neighbor_url}/run_container", json=offload_data, timeout=2)
            if offload_resp.status_code == 200:
                return {
                    "status_code": 200,
                    "response": {
                        "status": "scaled_vicinity",
                        "target_cluster": neighbor_url,
                        "scaling_response": offload_resp.json()
                    }
                }
        except:
            continue
    
    # TIER 3: Global Scaling
    try:
        central_url = f"http://{PARENT_NODE}:5000/global_scale_request"
        global_req_data = offload_data.copy()
        global_req_data['requester_id'] = NODE_ID
        
        global_resp = requests.post(central_url, json=global_req_data, timeout=5)
        
        if global_resp.status_code == 200:
            return {
                "status_code": 200,
                "response": {
                    "status": "scaled_global",
                    "scaling_response": global_resp.json()
                }
            }
    except:
        pass
    
    return {"status_code": 503, "response": {"status": "failed", "reason": "System Saturated"}}

@app.route('/run_container', methods=['POST'])
def run_container():
    """Legacy endpoint for backward compatibility"""
    data = request.json
    result = run_container_internal(data)
    return jsonify(result['response']), result['status_code']

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
