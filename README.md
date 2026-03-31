# 📘 Master Technical Specification: AI Knowledge Platform

## 1. Vision & Core Objectives
An organization-wide AI platform designed to handle **thousands of concurrent users**. It bridges the gap between **unstructured documentation** (PDFs, DOCX) and **structured analytical data** (Parquet) through a unified conversational interface.

* **Primary Goal:** Deliver precise, source-cited answers governed by strict Role-Based Access Control (RBAC).
* **Key Innovation:** A "Hybrid Brain" that uses an LLM to intelligently route queries between vector search (Qdrant) and analytical SQL (DuckDB).

---

## 2. System Architecture (The Four Layers)

| Layer | Primary Components | Responsibility |
| :--- | :--- | :--- |
| **User Layer** | React/Next.js | Chat interface, history, source visualization, and feedback loop ($+1/-1$). |
| **Gateway Layer** | Kong/Envoy, Okta/Azure AD | OIDC/SSO, JWT validation, rate limiting, and request routing. |
| **Agent Layer** | FastAPI, LLM Router, Semantic Cache | The "Intelligence" tier. Handles state, routes queries to models, and manages tools. |
| **Data Layer** | Qdrant, DuckDB, Postgres | The "Storage" tier. Vector embeddings, Parquet analytics, and relational metadata. |

---

## 3. Component Deep Dive

### 3.1 Agent Service (Core Intelligence)
* **LLM Router:** A dynamic module that selects the model based on query complexity.
    * *Executive:* Claude 3.5 Sonnet (complex reasoning).
    * *Standard:* GPT-4o-mini (cost-effective).
    * *Fallback:* Local Llama (privacy/availability).
* **Semantic Cache:** A Qdrant collection that stores question-answer pairs. If a new query has a $>0.95$ similarity to a cached item, the system returns the cached answer, saving **20-40% in API costs**.
* **Conversation Manager:** Manages Postgres-backed state and context window truncation/summarization.

### 3.2 Tool Registry
The Agent has access to three primary tools via a **Permission-Aware Router**:
1.  `search_documents`: Vector search over Qdrant.
2.  `query_parquet`: Text-to-SQL executed against DuckDB sandboxed views.
3.  `describe_dataset`: Inspects schema/metadata to help the LLM write better SQL.

---

## 4. The Data & Ingestion Pipeline

### 4.1 Ingestion Flow
1.  **File Sources:** Files are dropped into monitored directories/buckets.
2.  **Redis Queue (RQ):** Decouples ingestion from the API to prevent timeouts.
3.  **Workers ($N$):** Parse text and chunk documents (512-token chunks with 10% overlap).
4.  **GPU Embed Service:** Converts chunks to vectors using `sentence-transformers`.
5.  **Data Sink:** Vectors stored in **Qdrant**; structured data stored as **Parquet**.

### 4.2 Security & Permissions
* **Identity Translation:** The system translates JWT identity/groups into DB filters.
* **Document Level:** Qdrant queries include a `must_match` filter for `user_groups`.
* **Row Level:** DuckDB uses pre-registered views that restrict access to sensitive columns/rows.

---

## 5. Implementation Roadmap

| Phase | Milestone | Focus |
| :--- | :--- | :--- |
| **1: Foundation** | **MVP** | Basic RAG (Qdrant + Sonnet). Manual ingestion. |
| **2: Hybrid** | **Intelligence** | DuckDB integration + LLM Tool Routing + Semantic Cache. |
| **3: Pipeline** | **Automation** | Redis Workers + GPU Embedding Service + Schema Registry. |
| **4: Enterprise** | **Hardening** | K8s scaling + Multi-node Qdrant + Full RBAC + Observability. |

---

## 6. Operational & Financial Targets
* **Estimated Cost:** Approximately **$5,000 – $15,000/month** for 50k daily queries (once fully scaled).
* **Observability:** Full "LGTM" stack (Loki, Grafana, Tempo, Mimir) for log/trace/metric correlation.
* **Latency Target:** Sub-2s for time-to-first-token; sub-5s for full tool-augmented response.

---

## 7. Critical Risks & Mitigations
* **Permission Leakage:** Mitigated by "Late Binding" security where filters are applied at the database level, not the LLM level.
* **Model Drift:** Managed through the **Observability Layer** and a "Golden Dataset" for regression testing.
* **SQL Injection (AI-driven):** Mitigated by using **Read-Only views** and a timeout-limited, row-capped DuckDB execution environment.

---