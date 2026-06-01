# AI Financial Agent (Budget Agent) - v0.2

A sophisticated multi-agent financial assistant built with **FastAPI**, **LangGraph**, and **SQLAlchemy**. This agent helps individuals, couples, or families manage their finances across multiple accounts through natural language, image receipts, and voice notes.

## 🚀 Core Features (v0.2)

- **Multi-modal Expense Capture**:
    - **Voice (OpenAI Whisper)**: Record voice notes directly in the browser to log transactions hands-free.
    - **Vision (gpt-4o-mini)**: Upload a receipt photo for automatic details and item extraction.
    - **Text**: Free-form conversational entries.
- **Multi-Agent Orchestration (LangGraph)**:
    - **Supervisor**: Routes queries dynamically and controls recursion limits.
    - **Data Entry Expert**: Manages database writes (transactions, double-entry transfers, savings goals, recurring transactions, bank statements).
    - **Financial Analyst**: Reads and synthesizes data (multi-scope budgets, balances, custom split reconciliations, recurring schedules, notifications/alerts).
    - **Concierge**: Handles onboarding, greetings, and small talk.
- **Automated Recurring Transactions**:
    - Schedule weekly or monthly subscriptions/transactions.
    - Automatic startup engine hook catches up and processes pending recurrences upon server boot.
- **Moroccan Bank CSV Statement Imports**:
    - Automated parsing of export CSV files from **Attijariwafa Bank**, **BMCE (Bank of Africa)**, and **Société Générale (SG)**.
    - Auto-categorization using local dictionaries and LLM matching.
    - Normalizes Moroccan currency formats and formats dates to `YYYY-MM-DD`.
- **System Alerts & Notifications**:
    - Logs budget warnings and critical breaches directly to a dedicated notifications table.
    - Read/unread status indicators.
- **Advanced Financial Features**:
    - **Three-Scoped Budgets**: Configurable budget rules checked at the *workspace*, *user*, or *account* level.
    - **Flexible Splits Calculation**: Supports Equal splits, Proportional-to-income splits, and Custom percentage ratios (via `SplitRuleModel`).
    - **Linked Savings Goals**: Set and monitor savings goals linked directly to physical accounts.
    - **Double-Entry Bookkeeping**: Bank transfers recorded symmetrically as outflow/inflow to preserve ledger integrity.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Agent Framework**: LangGraph & LangChain
- **LLMs**: OpenAI gpt-4o-mini
- **Database**: SQLite with SQLAlchemy ORM
- **Transcription**: OpenAI Whisper-1
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
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Initialize Database**:
   The database is automatically created and seeded with dummy accounts and categories on the first run.

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

To verify the database models, automated recurring transactions catch-up, bank statement importing, and budget warnings, run the v0.2 test script:
```bash
uv run python scratch/test_v02_features.py
```

---
Developed as a complete cross-platform financial assistant prototype.
