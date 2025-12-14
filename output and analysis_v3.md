```
C:\Users\10\Desktop\edge_computing_thesis>python simulate_global_test.py

==================================================
1. Initializing Network
==================================================
{'results': {'cluster_1': 'Success', 'cluster_2': 'Success', 'cluster_3': 'Success'}, 'status': 'Network Initialized'}

==================================================
2. Filling Cluster 1 (Local)
==================================================
Cluster 1 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '1', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
3. Filling Cluster 2 (Vicinity)
==================================================
Cluster 2 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '2', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
4. Triggering Global Scaling Test
==================================================
Sending massive task to Cluster 1.
Expectation: C1 Full -> C2 Full -> Central -> C3 (Success)

--- FINAL RESULT ---
{
  "details": {
    "assigned_cluster": "3",
    "cluster_url": "http://cluster_3:5000",
    "status": "success",
    "target_response": {
      "details": {
        "status": "deployed",
        "task_id": "global_test_task"
      },
      "status": "deployed_locally",
      "target_worker": "6_c3"
    }
  },
  "status": "scaled_global"
}

SUCCESS: Global Scaling Activated!

C:\Users\10\Desktop\edge_computing_thesis>
```


# Gemini 3 pro analysis - NO, it's my own analysis this time

link: https://gapgpt.app/chat/486735b5-ac5c-42eb-8914-1687d5a6959e

---

first, the code above shows that if we give the cluster 1 and 2 some tasks so they become full, when we try to request another task with 2.0 cpus requirement, it will trigger the global scaling and for this test, it is assigned to the "`6_c3`" (it's the worker with 2 cpu cores available)

but this python test doesn't free up the space, so if we run it again:

```
C:\Users\10\Desktop\edge_computing_thesis>python simulate_global_test.py

==================================================
1. Initializing Network
==================================================
{'results': {'cluster_1': 'Success', 'cluster_2': 'Success', 'cluster_3': 'Success'}, 'status': 'Network Initialized'}

==================================================
2. Filling Cluster 1 (Local)
==================================================
Cluster 1 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '1', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
3. Filling Cluster 2 (Vicinity)
==================================================
Cluster 2 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '2', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
4. Triggering Global Scaling Test
==================================================
Sending massive task to Cluster 1.
Expectation: C1 Full -> C2 Full -> Central -> C3 (Success)

--- FINAL RESULT ---
{
  "reason": "System-wide Saturation",
  "status": "failed"
}

FAILURE: Did not scale globally.

C:\Users\10\Desktop\edge_computing_thesis>
```

here, we can see that the simulation failed globally, because it couldn't find any space for the new incoming request

finally, if we do `docker compose down` and `docker compose up -d --build` again, and if we change the simulation to request 2.5 cpus instead of 2.0, the task will be definitely assigned to "`5_c3`":

```
C:\Users\10\Desktop\edge_computing_thesis>python simulate_global_test.py

==================================================
1. Initializing Network
==================================================
{'results': {'cluster_1': 'Success', 'cluster_2': 'Success', 'cluster_3': 'Success'}, 'status': 'Network Initialized'}

==================================================
2. Filling Cluster 1 (Local)
==================================================
Cluster 1 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '1', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
3. Filling Cluster 2 (Vicinity)
==================================================
Cluster 2 Status (Should be Full):
{'active_workers': 2, 'available_resources': {'cpu': 1.0, 'ram': 12088}, 'cluster_id': '2', 'total_capacity': {'cpu': 6.0, 'ram': 12288}}

==================================================
4. Triggering Global Scaling Test
==================================================
Sending massive task to Cluster 1.
Expectation: C1 Full -> C2 Full -> Central -> C3 (Success)

--- FINAL RESULT ---
{
  "details": {
    "assigned_cluster": "3",
    "cluster_url": "http://cluster_3:5000",
    "status": "success",
    "target_response": {
      "details": {
        "status": "deployed",
        "task_id": "global_test_task"
      },
      "status": "deployed_locally",
      "target_worker": "5_c3"
    }
  },
  "status": "scaled_global"
}

SUCCESS: Global Scaling Activated!

C:\Users\10\Desktop\edge_computing_thesis>
```