# AI Financial Agent (Budget Agent) - v0.1

A sophisticated multi-agent financial assistant built with **FastAPI**, **LangGraph**, and **SQLAlchemy**. This agent helps individuals, couples, or families manage their finances across multiple accounts through natural language, image receipts, and voice notes.

## 🚀 Core Features (v0.1)

- **Multi-modal Expense Capture**:
    - **Voice (Whisper)**: Record voice notes directly in the browser to log transactions hands-free.
    - **Vision (Llama-4-Scout)**: Upload a receipt photo for automatic details and item extraction.
    - **Text**: Free-form conversational entries.
- **Multi-Agent Orchestration (LangGraph)**:
    - **Supervisor**: Routes queries dynamically and controls recursion limits.
    - **Data Entry Expert**: Manages database writes (transactions, double-entry transfers, savings goals).
    - **Financial Analyst**: Reads and synthesizes data (multi-scope budgets, balances, custom split reconciliations).
    - **Concierge**: Handles onboarding, greetings, and small talk.
- **Advanced Financial Features**:
    - **Three-Scoped Budgets**: Configurable budget rules checked at the *workspace*, *user*, or *account* level.
    - **Flexible Splits Calculation**: Supports Equal splits, Proportional-to-income splits, and Custom percentage ratios (via `SplitRuleModel`).
    - **Linked Savings Goals**: Set and monitor savings goals linked directly to physical accounts.
    - **Double-Entry Bookkeeping**: Bank transfers recorded symmetrically as outflow/inflow to preserve ledger integrity.
    - **Moroccan Localized Pre-categorization**: High-speed keyword mapping for Moroccan entities (BIM, Marjane, Lydec, etc.) to minimize latency and LLM costs.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Agent Framework**: LangGraph & LangChain
- **LLMs**: Llama-3.3-70b-versatile (Groq) & Llama-4-Scout
- **Database**: SQLite with SQLAlchemy ORM
- **Transcription**: Whisper-large-v3 (Groq)
- **UI**: Vanilla HTML / JS Web client

## 📦 Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd budget_agent
   ```

2. **Install dependencies** (using `uv`):
   ```bash
   uv sync
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

4. **Initialize Database**:
   The database is automatically created and seeded with dummy accounts, categories, and custom split rules on the first run.

5. **Run the Application**:
   ```bash
   uv run main.py
   ```
   Open your browser and navigate to:
   ```
   http://127.0.0.1:8000/
   ```
   *Note: Using this URL is required to grant browser microphone permissions for testing voice note capture.*

## 🧪 Running Tests

To verify the database models, scoped budget checks, custom split math, and report generation, run the test script:
```bash
uv run python3 scratch/test_db_and_tools.py
```

---
Developed as a complete cross-platform financial assistant prototype.
