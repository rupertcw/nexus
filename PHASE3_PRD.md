# 📘 PRD: AI Knowledge Platform (Phase 3 - The Scalable Pipeline & Visibility)

## 1. Executive Summary
**Phase 3** focuses on **Asynchronous Processing**, **Resource Optimization**, and **System Visibility**. We will decouple ingestion logic from the API using Redis, offload embedding math to a dedicated service, and provide an administrative dashboard to monitor these processes. This ensures the chat interface remains responsive even under heavy document-processing loads.

---

## 2. Target Audience
* **Data Engineers:** Manage and troubleshoot large-scale data ingestion.
* **DevOps/SREs:** Monitor system health, queue depths, and resource saturation.
* **Power Users/Admins:** Uploading large batches of documentation and requiring status updates.

---

## 3. User Stories
| ID | User Story |
| :--- | :--- |
| **US.1** | As an admin, I want to upload 500 PDFs at once and see a progress bar instead of a browser timeout. |
| **US.2** | As a developer, I want the Embedding Model on a dedicated GPU instance to avoid slowing down the API. |
| **US.3** | As a user, I want the system to automatically "discover" new Parquet files dropped into storage. |
| **US.4** | As an SRE, I want a dashboard showing queue depth and real-time failure logs for ingestion jobs. |
| **US.5** | As a dev, I want to see the specific error (e.g., "Corrupt PDF") and manually "Retry" a failed job from the UI. |

---

## 4. Functional Requirements

### 4.1 Asynchronous Ingestion (The "Worker" Pattern)
* **Redis Task Queue:** The API "produces" a job ID and returns it immediately; background **Workers** "consume" and process the files.
* **Job Lifecycle:** Statuses must move through `PENDING` ➔ `PROCESSING` ➔ `COMPLETED` / `FAILED`.
* **Retry Logic:** Automatic retries for intermittent failures with exponential backoff.

### 4.2 Dedicated GPU Embedding Service
* **Service Decoupling:** Move `sentence-transformers` out of the FastAPI process into a standalone container.
* **Batch Inference:** Support batch-requesting (e.g., embedding 32 chunks at once) to maximize GPU utilization and reduce overhead.

### 4.3 Automated Schema Registry
* **Dynamic Catalog:** A service that monitors the Parquet directory, extracts schemas, and updates a Postgres metadata table.
* **Context Injection:** The LLM Router queries this registry to determine which tables are available for the `query_parquet` tool.

### 4.4 Ingestion Admin Dashboard (Visibility)
* **Live Job Monitor:** A table view showing Job ID, Filename, Status Badge, and Processing Time.
* **Job Detail Drawer:** A slide-out panel showing metadata (page count, chunk count) and raw Python stack traces for failed jobs.
* **Control Actions:** UI buttons to "Retry Job" or "Clear Completed" to keep the queue history clean.
* **Queue Metrics:** Real-time counters for "Queue Depth," "Active Workers," and "Success Rate (Last 24h)."

### 4.5 Observability & Monitoring
* **Metrics Export:** Hook up `prometheus-client` for queue lengths and embedding latency.
* **Structured Logging:** Centralized JSON logging across all services (API, Worker, Embedder) for correlation in Grafana Loki.

---

## 5. Technical Stack Additions
* **Message Broker:** **Redis** (running in Docker).
* **Task Framework:** **Python-RQ** (for simplicity) or **Celery** (for complex workflows).
* **Monitoring:** **Prometheus** & **Grafana**.
* **Frontend Logic:** **TanStack Query (React Query)** for dashboard polling and state management.
* **Model Serving:** **FastEmbed** or **NVIDIA Triton**.

---

## 6. Infrastructure Evolution
Our `docker-compose.yml` expands into a distributed microservice architecture:
1.  **API Server:** Handles routing, chat, and job submission.
2.  **Worker Nodes:** Scalable instances ($N$) that handle parsing and logic.
3.  **Redis:** Acts as the message broker and status store.
4.  **Embed Service:** Dedicated container for vector calculations (GPU-enabled).
5.  **Data Layer:** Qdrant (Vectors), Postgres (Metadata/Jobs), DuckDB (Parquet).

---

## 7. Success Metrics (KPIs)
* **Ingestion Throughput:** Ability to process $>100$ pages per minute per worker node.
* **Resource Efficiency:** 30% reduction in API RAM usage by offloading the embedding models.
* **MTTR (Mean Time to Repair):** Admins can identify and retry a failed PDF upload via the dashboard in $<30$ seconds.
* **Visibility:** 100% of background tasks are accounted for in the UI (no "ghost" processes).
