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
| 1998-04-30 21:37:00 | 1350 |
| 1998-04-30 21:38:00 | 532 |
| 1998-04-30 21:39:00 | 154 |
| 1998-04-30 21:40:00 | 32 |
| 1998-04-30 21:41:00 | 15 |
| 1998-04-30 21:42:00 | 2 |


## Outcome

| Minute | Requests | Required_CPU | Allocated_CPU | Replicas | Status | Worker_Distribution |
|--------|----------|--------------|----------------|----------|--------|---------------------|
| 1 | 2 | 1.0 | 1.0 | 1 | Stable | 2_c1(local) |
| 2 | 11 | 1.0 | 1.0 | 1 | Stable | 2_c1(local) |
| 3 | 16 | 1.0 | 1.0 | 1 | Stable | 2_c1(local) |
| 4 | 50 | 1.0 | 1.0 | 1 | Stable | 2_c1(local) |
| 5 | 150 | 1.5 | 2.0 | 2 | Scaled LOCAL: 2_c1 | 2_c1(local) \| 2_c1(local) |
| 6 | 400 | 4.0 | 4.0 | 4 | Scaled LOCAL: 1_c1 + Scaled LOCAL: 1_c1 | 2_c1(local) \| 2_c1(local) \| 1_c1(local) \| 1_c1(local) |
| 7 | 740 | 7.4 | 8.0 | 8 | Scaled LOCAL: 1_c1 + Scaled LOCAL: 1_c1 + Scaled VICINITY: 4_c2 + Scaled VICINITY: 4_c2 | 2_c1(local) \| 2_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) \| 4_c2(vicinity) \| 4_c2(vicinity) |
| 8 | 1350 | 13.5 | 14.0 | 14 | Scaled VICINITY: 3_c2 ×4 + Scaled GLOBAL: 6_c3 ×2 | 2_c1(local) \| 2_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) \| 4_c2(vicinity) \| 4_c2(vicinity) \| 3_c2(vicinity) \| 3_c2(vicinity) \| 3_c2(vicinity) \| 3_c2(vicinity) \| 6_c3(global) \| 6_c3(global) |
| 9 | 532 | 5.32 | 6.0 | 6 | Scaled DOWN: global ×2 + vicinity ×6 | 2_c1(local) \| 2_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) \| 1_c1(local) |
| 10 | 154 | 1.54 | 2.0 | 2 | Scaled DOWN: local ×4 | 1_c1(local) \| 1_c1(local) |
| 11 | 32 | 1.0 | 1.0 | 1 | Scaled DOWN: local | 1_c1(local) |
| 12 | 15 | 1.0 | 1.0 | 1 | Stable | 1_c1(local) |
| 13 | 2 | 1.0 | 1.0 | 1 | Stable | 1_c1(local) |



## My analysis

This shows that we are doing Scale out/in correctly, prioritising the borrowed instances when trying to free resources.