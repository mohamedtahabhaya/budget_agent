# AI Financial Agent (Budget Agent) - v0.3

A sophisticated multi-agent financial assistant built with **FastAPI**, **LangGraph**, and **SQLAlchemy**. This agent helps individuals, couples, or families manage their finances across multiple accounts through natural language, image receipts, and voice notes.

## 🚀 Core Features (v0.3)

- **Premium Dark Mode Dashboard UI**:
    - High-end dark theme dashboard with linear gradients, glassmorphism, and Outfit/Inter modern typography.
    - **Balances Widget**: Live accounts cards grid highlighting personal, savings, and shared balances.
    - **Savings Progress Goals**: Dynamic savings goals tracking with percentage progress indicators.
    - **Live Alerts Feed**: Recent critical budget warning notifications displayed inside the dashboard.
    - **Notification Settings Toggles**: Direct switches to adjust notification preferences per user.
    - **Scrolling Optimization**: Locked viewports with independent scroll containers preventing clipped input bars.

- **Real-Time Live & Desktop Alerts**:
    - Streamed budget alerts sent in real-time over SSE (Server-Sent Events) from the backend `/chat` endpoint.
    - In-app toast alerts displaying critical warnings dynamically.
    - Browser Desktop Push Notifications via standard Web Notifications API.

- **Multi-modal Expense Capture**:
    - **Voice (Groq Whisper)**: Record voice notes directly in the browser, transcribed via Groq's high-speed `whisper-large-v3`.
    - **Vision (Llama 4 Scout)**: Upload a receipt photo for automatic details and item extraction using Groq's multimodal `meta-llama/llama-4-scout-17b-16e-instruct`.
    - **Text**: Free-form conversational entries.

- **Multi-Agent Orchestration (LangGraph)**:
    - **Supervisor**: Routes queries dynamically using high-performance text-based heuristics, resolving structured output API bottlenecks.
    - **Data Entry Expert**: Manages database writes (transactions, double-entry transfers, savings goals, recurring transactions, bank statements).
    - **Financial Analyst**: Reads and synthesizes data (multi-scope budgets, balances, custom split reconciliations, recurring schedules, notifications/alerts).
    - **Concierge**: Handles onboarding, greetings, and small talk.

- **Workspace Onboarding & Invitation Flow**:
    - Generate unique workspace invitation tokens (`create_workspace_invite`).
    - Dedicated web acceptance portal (`/invite/accept?token=...`) with beautiful animated checkmarks, dark theme presentation, and automatic user collision avoidance.
    - Track active and pending invites with the `list_invitations` tool.

- **Advanced Savings Goals Management**:
    - Create virtual savings targets.
    - Deposit money into savings goals.
    - **Goal Deletion**: Delete/cancel savings goals (`delete_savings_goal`).
    - **Goal Properties Update**: Modify goal names, target amounts, target dates, or categories (`update_savings_goal_properties`).

- **Automated Recurring Transactions**:
    - Schedule weekly or monthly subscriptions/transactions.
    - Automatic startup engine hook catches up and processes pending recurrences upon server boot.

- **Moroccan Bank CSV Statement Imports**:
    - Automated parsing of export CSV files from **Attijariwafa Bank**, **BMCE (Bank of Africa)**, and **Société Générale (SG)**.
    - Auto-categorization using local dictionaries and LLM matching.
    - Normalizes Moroccan currency formats and formats dates to `YYYY-MM-DD`.

- **Advanced Financial Features**:
    - **Three-Scoped Budgets**: Configurable budget rules checked at the *workspace*, *user*, or *account* level.
    - **Flexible Splits Calculation**: Supports Equal splits, Proportional-to-income splits, and Custom percentage ratios (via `SplitRuleModel`).
    - **Double-Entry Bookkeeping**: Bank transfers recorded symmetrically as outflow/inflow to preserve ledger integrity.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Agent Framework**: LangGraph & LangChain
- **LLMs (Groq)**: `meta-llama/llama-4-scout-17b-16e-instruct` (Main & Vision), `whisper-large-v3` (Transcription)
- **Database**: SQLite with SQLAlchemy ORM
- **UI**: Responsive Vanilla HTML / JS Web client

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

To verify features, automated transaction catch-ups, CSV importing, alerts, splits, and savings goals deletion, run the test suites:

- **v0.2 Core Features Test**:
  ```bash
  uv run python scratch/test_v02_features.py
  ```

- **v0.3 Notification Preferences & Goals Management Test**:
  ```bash
  uv run python scratch/test_v03_features.py
  ```

---
Developed as a complete cross-platform financial assistant prototype.
