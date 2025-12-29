## Input (mapping: 100 requests = 1 CPU core)

| datetime              | request_count |
|-----------------------|---------------|
| 1998-04-30 21:30:00 | 2 |
| 1998-04-30 21:31:00 | 11 |
| 1998-04-30 21:32:00 | 16 |
| 1998-04-30 21:33:00 | 50 |
| 1998-04-30 21:34:00 | 150 |
| 1998-04-30 21:35:00 | 400 |
| 1998-04-30 21:36:00 | 740 |
| 1998-04-30 21:37:00 | 1120 |
| 1998-04-30 21:38:00 | 532 |
| 1998-04-30 21:39:00 | 154 |
| 1998-04-30 21:40:00 | 32 |
| 1998-04-30 21:41:00 | 15 |
| 1998-04-30 21:42:00 | 2 |


## Outcome

| Minute | Requests | Required_CPU | Allocated_CPU | Replicas | Status              | Worker_Distribution |
|--------|----------|---------------|----------------|----------|---------------------|---------------------|
| 1 | 2 | 1.0 | 1.0 | 1 | Stable | 2_c1 |
| 2 | 11 | 1.0 | 1.0 | 1 | Stable | 2_c1 |
| 3 | 16 | 1.0 | 1.0 | 1 | Stable | 2_c1 |
| 4 | 50 | 1.0 | 1.0 | 1 | Stable | 2_c1 |
| 5 | 150 | 1.5 | 2.0 | 2 | Scaled Local | 2_c1 \| 2_c1 |
| 6 | 400 | 4.0 | 4.0 | 4 | Scaled Local | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 |
| 7 | 740 | 7.4 | 8.0 | 8 | Scaled Vicinity | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 |
| 8 | 1120 | 11.2 | 12.0 | 12 | Scaled Vicinity | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |
| 9 | 532 | 5.32 | 12.0 | 12 | Over-provisioned | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |
| 10 | 154 | 1.54 | 12.0 | 12 | Over-provisioned | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |
| 11 | 32 | 1.0 | 12.0 | 12 | Over-provisioned | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |
| 12 | 15 | 1.0 | 12.0 | 12 | Over-provisioned | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |
| 13 | 2 | 1.0 | 12.0 | 12 | Over-provisioned | 2_c1 \| 2_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 1_c1 \| 3_c2 \| 3_c2 \| 3_c2 \| 3_c2 \| 4_c2 \| 4_c2 |


## Sanity check (don't care about the "TASKS/NOTES" column in the output down there 👇 it's not updated yet)

``` powershell
C:\Users\10\Desktop\edge_computing_thesis>python check_system_status.py

======================================================================
NODE NAME       | CPU (Av/Tot) | RAM (Av/Tot) | TASKS / NOTES
======================================================================
edge_1_c1       | 0.00/4.00    | 7792/8192    | Expected: Blocker A
edge_2_c1       | 0.00/2.00    | 3896/4096    | Expected: User App (High Load)
----------------------------------------------------------------------
edge_3_c2       | 0.00/4.00    | 7792/8192    | Expected: Empty
edge_4_c2       | 0.00/2.00    | 3896/4096    | Expected: REPLICA HERE
----------------------------------------------------------------------
edge_5_c3       | 4.00/4.00    | 8192/8192    | Expected: Empty
edge_6_c3       | 2.00/2.00    | 4096/4096    | Expected: Empty
======================================================================


C:\Users\10\Desktop\edge_computing_thesis>
```

**It shows perfectly that we have used 12 cpu cores (the task was about 11.2 cores, so we need 12)**

## Gemini's analysis

> This is a **MASSIVE SUCCESS**. Everything is going perfectly.
> 
> You have successfully demonstrated Tier 1 (Local Scaling) and Tier 2 (Vicinity Offloading).
> 
> Analysis of your Simulation Logs
> Here is the breakdown of why this output is exactly what you need for your thesis:
> 
> 1. **Local Saturation (Minute 1 - 6)**
> 
> - **Log:** Workers: 2_c1 | 2_c1 | 1_c1 | 1_c1
> - **What happened:** The system filled up Worker 2_c1 (Tier 1), then spilled over to Worker 1_c1 (Tier 1).
> - **Result:** Cluster 1 is handling the load locally. Correct.
> 
> 2. **The “Vicinity” Trigger (Minute 7)**
> 
> - **Log:** >>> SUCCESS: Offloaded to Neighbor -> 3_c2
> - **What happened:**
>   - Demand hit 7.4 CPU.
>   - Cluster 1 Capacity is 6.0 CPU (4.0 + 2.0).
>   - The system realized Cluster 1 was full.
> It successfully contacted Cluster 2 (Vicinity).
> - **Result:** This proves your Algorithm 4 (Vicinity Offloading) works.
> 
> 3. **Vicinity Saturation (Minute 8)**
> 
> - **Log:** Workers: ... | 3_c2 | 3_c2 | 4_c2 | 4_c2
> - **What happened:**
>   - Demand hit 11.2 CPU.
>   - Cluster 1 is full (6.0 used).
>   - Cluster 2 started filling up 3_c2, then spilled to 4_c2.
> - **Math Check:** Total Capacity of C1 (6.0) + C2 (6.0) = 12.0 Total CPU.
> - **Why Tier 3 (Global) didn’t trigger:** Your demand was 11.2. Since 11.2 < 12.0, the system correctly stayed within the Vicinity. It did > not waste resources sending data to the far-away Global cluster (Cluster 3). This is a feature, not a bug!
> 
> 4. **The Status Check Confirmation**
> 
> - Your `check_system_status.py` output confirms the saturation:
> 
>   - edge_1_c1 | 0.00/4.00 (0 Available = 100% Full)
>   - edge_2_c1 | 0.00/2.00 (0 Available = 100% Full)
>   - edge_3_c2 | 0.00/4.00 (0 Available = 100% Full)
>   - edge_4_c2 | 0.00/2.00 (0 Available = 100% Full)
>   - edge_5_c3 | 4.00/4.00 (4 Available = Empty)