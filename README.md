# AI Financial Agent (Budget Agent)

A multi-agent personal finance assistant built with **FastAPI**, **LangGraph**, and **SQLAlchemy**. It supports natural language queries, receipt image analysis, and voice transcriptions to help manage personal and shared workspace accounts.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Agent Orchestration**: LangGraph (StateGraph)
  - **Supervisor**: Direct text-routing to prevent structured output bottlenecks.
  - **Data Entry Expert**: Handles database write operations (transactions, transfers, savings goals, workspace invitations, account lifecycle, custom split rules, budget limits).
  - **Financial Analyst**: Performs data aggregation and reads (balances, spend reports, notification feeds, split calculations).
  - **Financial Concierge**: Manages greetings and initial onboarding.
- **LLM Models (Groq API)**:
  - Agent Brain & Vision: `meta-llama/llama-4-scout-17b-16e-instruct`
  - Heuristics: `llama-3.1-8b-instant`
  - Voice Note Transcription: `whisper-large-v3`
- **Database**: PostgreSQL (recommended for production) or SQLite (local fallback) using custom JSONB/VARCHAR types via SQLAlchemy ORM.

---

## ⚙️ Setup & Installation

### 1. Install Dependencies
Ensure you have the `uv` package manager installed. Then run:
```bash
uv sync
```

### 2. Configure Environment
Create a `.env` file in the root folder with the following variables:
```env
DATABASE_URL=postgresql://postgres:postgrespassword@localhost:5433/budget_db
GROQ_API_KEY=your_groq_api_key_here
CORS_ALLOWED_ORIGINS=http://localhost:8081,http://127.0.0.1:8000
```
*(If `DATABASE_URL` is omitted, the application will default to a local SQLite database `test_budget.db`)*.

### 3. Database Seeding
The database is auto-created and seeded with mock accounts, categories, split rules, and a workspace on server startup.

### 4. Run the Server
Start the backend API server:
```bash
uv run main.py
```
Access the web dashboard in your browser at `http://127.0.0.1:8000/`.

---

## 🧪 Running Automated Tests

Run the following test suites to verify database constraints, double-entry transfers, recurring transaction catch-up, and alert triggers:

```bash
# Verify core features (transactions, splits, CSV imports)
uv run python scratch/test_v02_features.py

# Verify notification preferences, savings goal deletion, and update operations
uv run python scratch/test_v03_features.py
```
