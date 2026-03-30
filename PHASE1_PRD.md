This **Product Requirements Document (PRD)** focuses on **Phase 1: Foundation**, as outlined in your roadmap. The goal of this phase is to move from a conceptual architecture to a working "Crawl" stage—a functional RAG (Retrieval-Augmented Generation) system that proves the core value to internal stakeholders.

---

# PRD: AI Knowledge Platform (Phase 1 - Foundation)

## 1. Executive Summary
**Phase 1** aims to deliver a "Minimal Viable Product" (MVP) that allows a pilot group of users to query a curated set of unstructured internal documents (PDFs, DOCX) and receive accurate, source-cited conversational answers.

---

## 2. Target Audience
* **Pilot Users:** 10–20 internal team members.
* **Stakeholders:** Engineering leadership and Security/Compliance officers (to review citation accuracy and data handling).

---

## 3. User Stories
| ID | User Story |
| :--- | :--- |
| **US.1** | As a user, I want to ask natural language questions about internal policies so I don't have to read 50-page PDFs. |
| **US.2** | As a user, I want to see exactly which page/document an answer came from to verify its accuracy. |
| **US.3** | As a user, I want my chat history to be saved so I can resume a research session later. |
| **US.4** | As an admin, I want a simple way to upload a folder of documents into the system. |

---

## 4. Functional Requirements

### 4.1 Chat Interface (Frontend)
* **Conversational UI:** A clean, React-based chat window.
* **Source Citations:** Display clickable "Source Cards" below LLM responses showing document names and relevant snippets.
* **Session Management:** Sidebar showing "Recent Chats" stored in the local database.

### 4.2 Core Intelligence (Backend)
* **LLM Integration:** Integration with **Claude 3.5 Sonnet** (via API) for high-reasoning output.
* **Basic Prompt Engineering:** System prompts designed to enforce "Answer only based on the provided context" to minimize hallucinations.
* **Semantic Search:** Vector retrieval using **Qdrant** (Single Node).

### 4.3 Manual Ingestion Pipeline
* **File Support:** PDF and DOCX processing.
* **Chunking Strategy:** Fixed-size chunking (e.g., 512 tokens) with 10% overlap to maintain context.
* **CLI Loader:** A simple Python script to scan a local directory, generate embeddings, and push to Qdrant.

---

## 5. Technical Stack (Phase 1 Specific)
As per your "Phase 1" roadmap in the architecture diagrams:
* **Deployment:** Single Pod (Docker Compose) for rapid iteration.
* **Frontend:** React / Next.js.
* **API:** FastAPI (Python).
* **Vector DB:** Qdrant (Single Node).
* **Relational DB:** PostgreSQL (Local) for chat history and user metadata.
* **LLM:** Claude 3.5 Sonnet (API-based).

---

## 6. Non-Functional Requirements
* **Accuracy:** >80% relevance score on a "Golden Dataset" of 20 test questions.
* **Latency:** Initial response (Time to First Token) < 2 seconds.
* **Security:** Basic JWT-based authentication (Mock SSO for now).
* **Observability:** Basic logging of queries and retrieval hits to the console/Postgres.

---

## 7. Success Metrics (KPIs)
1.  **System Usability:** 100% of pilot users can successfully retrieve an answer from a known document.
2.  **Citation Fidelity:** 100% of generated answers must include at least one valid source citation.
3.  **Foundation Readiness:** Successful verification that the "Agent -> Tool -> Vector DB" loop is stable.

---

## 8. Out of Scope for Phase 1
* **DuckDB/Parquet Integration:** (Reserved for Phase 2).
* **Production K8s Deployment:** (Reserved for Phase 4).
* **Automated Ingestion Workers:** Files are loaded manually via CLI.
* **Fine-grained RBAC:** Everyone in the pilot sees all pilot documents.

---