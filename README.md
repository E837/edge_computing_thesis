# 🌐 Hierarchical Edge Auto-Scaling System

[![Python](https://img.shields.io/badge/Python-3.9-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg)](https://www.docker.com/)
[![Flask](https://img.shields.io/badge/Flask-Microservices-lightgrey.svg)](https://flask.palletsprojects.com/)

Welcome to the official repository for my Computer Science M.Sc. thesis: **"A Proactive Container-based Auto-scaling Approach for a Hierarchical Orchestration Framework for Edge Computing."**

This project tackles the inherent resource limitations of Edge Computing. When localized edge clusters face traffic bursts, they quickly saturate. This system introduces a **Vicinity-Aware, 3-Layer Hierarchical Scaling Engine** that dynamically offloads tasks to geographic neighbors or the central cloud before any degradation in Quality of Service (QoS) occurs.

---

## 🏗️ System Architecture

The project is built using Python/Flask microservices orchestrated by Docker Compose, precisely modeling a 3-layer edge topology:

1. **☀️ Layer 1: Central Cloud Node (`central_node/app.py`)**
   - The global orchestrator.
   - Maps network topology via a latency matrix and defines neighboring relationships ($Vicinity \le Threshold$).
   - Acts as the final fallback layer for **Global Scaling** when entire edge regions are saturated.

2. **🧠 Layer 2: Cluster Managers (`cluster_node/app.py`)**
   - Geographically localized managers.
   - Each manages a pool of Edge Worker nodes.
   - Maintains a `MY_VICINITY` list to know which neighboring clusters to ask for help during traffic spikes.
   - Routes container requests using a strict 3-tier fallback logic.

3. **👷 Layer 3: Edge Workers (`edge_node/app.py`)**
   - The actual machines/VMs running workloads close to the user.
   - Defined by strict physical constraints (e.g., $CPU = 4.0$, $RAM = 8192 MB$).
   - Manages task allocation, strictly monitoring `$CPU_{allocated}$` and `$RAM_{allocated}$`.

---

## 🚀 The 3-Tier Auto-Scaling Logic

When a burst of traffic requires a new application instance, the routing engine executes the core thesis algorithm:

1. **Tier 1 (Local Scheduling):** The Cluster Manager attempts to place the task on its local Edge Workers.
2. **Tier 2 (Vicinity Offloading):** If all local workers are full, the manager forwards the request (`is_offloaded=True`) to its predefined Vicinity (neighboring clusters with low latency).
3. **Tier 3 (Global Scaling):** If the local cluster *and* its vicinity are completely saturated, the request is escalated to the Central Cloud, which searches globally for any available resource.

### 📉 Scale-In Cost Hierarchy
When traffic subsides (Algorithm 5), the system must terminate tasks to save cost/energy. The simulator uses a **Cost-Aware Priority Queue** to kill instances in this order:
- **Highest Cost ($Priority = 10$)**: Global/Remote instances.
- **Medium Cost ($Priority = 5$)**: Vicinity/Neighbor instances.
- **Lowest Cost ($Priority = 1$)**: Local instances.

---

## 📂 Project Structure
```text
edge_computing_thesis/
├── central_node/
│   ├── app.py             # Cloud manager & network initializer
│   ├── Dockerfile         
│   └── requirements.txt
├── cluster_node/
│   ├── app.py             # 3-tier scaling logic & local routing
│   ├── Dockerfile         
│   └── requirements.txt
├── edge_node/
│   ├── app.py             # Resource tracking & task execution
│   ├── Dockerfile         
│   └── requirements.txt
├── docker-compose.yml     # provisions 1 central, 3 clusters, 6 edge nodes
├── simulate_thesis_trace.py # The workload trace simulation engine
└── test_log_bursts_modified.csv # The input workload dataset
```

---

## ⚙️ Getting Started & Simulation

### 1. Spin up the Environment
Ensure you have Docker and Docker Compose installed. The `docker-compose.yml` file will provision the complete 3-layer network on a shared bridge.

```bash
docker-compose up --build -d
```
*Wait a few seconds for all edge workers to register themselves with their respective cluster managers.*

### 2. Run the Workload Simulator
The simulation script reads a trace dataset (`test_log_bursts_modified.csv`) and mimics dynamic traffic patterns. It translates requests to CPU demands using the formula:

$$RequiredCPU = Requests \times 0.01$$

Run the simulation:
```bash
python simulate_thesis_trace.py
```

### 3. Observe the Magic
As the simulation runs, you will see the system gracefully navigate capacity limits:
*   `[Minute X] Demand: 3.5 > Current: 1.0 | Scaling UP...`
*   `[Cluster 1] All Local Workers Full. Trying Vicinity...`
*   `[Cluster 1] Vicinity Full. Requesting Global Scale from Central Node...`

The final state and scaling decisions per minute will be saved to `thesis_simulation_results.csv`.

---

## 🤝 Contribution & Feedback
This repository houses my ongoing M.Sc. thesis project. While the core algorithms are complete, I am always open to architectural discussions, optimization ideas, and networking!

Feel free to open an issue or reach out if you're interested in Fog/Edge computing, Docker orchestration, or predictive auto-scaling.

**Author**: [Ehsan Moradi](https://www.linkedin.com/in/its-ehsan-moradi)<br>
**Advisor**: [S.A. Javadi](https://ir.linkedin.com/in/sajavadi)
