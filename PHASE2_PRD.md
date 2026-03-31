# 📘 PRD: AI Knowledge Platform (Phase 2 - The Hybrid Brain)

## 1. Executive Summary
**Phase 2** expands the foundational RAG system by introducing an Agentic Tool Router. The system will now intelligently route natural language queries to either a Vector Database (for unstructured text) or a local Analytical Database (for structured Parquet data). Additionally, it introduces Semantic Caching to drastically reduce LLM costs and latency for repeated queries.

---

## 2. Target Audience
* **Expanded Pilot Group:** 30–50 users, specifically including members from Finance, HR, or Operations who rely on tabular data (e.g., budgets, headcounts).
* **System Administrators:** Who need to monitor API costs and observe cache hit rates.

---

## 3. User Stories
| ID | User Story |
| :--- | :--- |
| **US.1** | As a user, I want to ask analytical questions (e.g., "What was the total travel spend in Q3?") and get an accurate answer calculated from real data. |
| **US.2** | As a user, I want to ask hybrid questions (e.g., "Based on the travel policy, was John's $500 flight in Q3 compliant?") without manually combining reports. |
| **US.3** | As a user, I want to see the SQL query the AI generated so I can verify its math. |
| **US.4** | As a system owner, I want frequent, identical questions (e.g., "Where is the holiday calendar?") to be answered instantly without querying the LLM, to save money. |

---

## 4. Functional Requirements

### 4.1 The Tool Router (Agent Logic)
* **Function Calling:** Upgrade the LLM integration to use Claude 3.5 Sonnet's native tool-calling capabilities.
* **Tool 1: `search_documents`:** Executes the Phase 1 Qdrant vector search.
* **Tool 2: `query_parquet`:** Translates the user's question into a DuckDB SQL query.
* **Multi-Step Reasoning:** The agent must be able to call *both* tools in a single chain if the user asks a hybrid question.

### 4.2 DuckDB Analytics Engine
* **Local Parquet Connection:** DuckDB must map to a local folder of `.parquet` files (representing structured data exports).
* **Read-Only Sandboxing:** The AI must only have `SELECT` permissions. It cannot `DROP`, `INSERT`, or `ALTER` data.
* **Schema Injection:** The agent must be provided with the exact schema (column names and data types) of the Parquet files in its system prompt so it can write valid SQL.

### 4.3 Semantic Cache
* **Cache Collection:** Create a secondary collection in Qdrant named `semantic_cache`.
* **Flow:** Before sending a query to the LLM, embed the user's question and search the `semantic_cache`.
* **Threshold:** If a previous question matches with a cosine similarity of **> 0.92**, return the cached answer immediately. (Configurable via environment variables).

### 4.4 Basic Security (JWT)
* **Authentication Middleware:** Implement FastAPI middleware to require and validate a standard JWT Bearer token.
* **Identity Context:** Extract the `user_id` from the JWT and inject it into the application state for future audit logging.

---

## 5. Technical Stack Additions
* **Database:** `duckdb` (Python package).
* **Agent Framework:** Native `anthropic` tool calling (or lightweight LangChain agent executor).
* **Data Format:** `.parquet` (sample data needed for testing).
* **Security:** `python-jose` or `PyJWT` for token validation.

---

## 6. Non-Functional Requirements
* **SQL Safety:** DuckDB queries must have a strict timeout (e.g., 5 seconds) to prevent poorly written AI-SQL from locking the thread.
* **Cache Latency:** A "Cache Hit" response must be delivered to the frontend in `< 500ms`.
* **Cost Efficiency:** The Semantic Cache should aim to intercept at least 15% of total queries during the pilot.

---

## 7. Success Metrics (KPIs)
1. **Tool Accuracy:** The LLM selects the correct tool (`search_documents` vs `query_parquet`) >95% of the time based on a golden dataset of 50 varied questions.
2. **SQL Execution Success:** >85% of AI-generated SQL queries execute successfully without syntax errors on the first try.
3. **Cost Reduction:** Average LLM token cost per 100 queries drops by at least 15% compared to Phase 1, due to the Semantic Cache.

---