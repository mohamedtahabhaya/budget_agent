# AI Financial Agent (Budget Agent) - v0.1

A sophisticated multi-agent financial assistant built with **FastAPI**, **LangGraph**, and **SQLAlchemy**. This agent helps individuals and families manage their finances across multiple accounts through natural language, images, and voice.

## 🚀 Core Features (v0.1)

- **Multi-modal Expense Capture**: 
    - **Vision**: Snap a photo of a receipt (powered by Llama-4-Scout) for automatic JSON extraction.
    - **Voice**: Send audio notes (Whisper-large-v3) to log transactions hands-free.
    - **Text**: Free-form natural language entry.
- **Multi-Agent Orchestration (LangGraph)**:
    - **Supervisor**: Intelligently routes requests to the right specialist.
    - **Data Entry Expert**: Handles all database modifications (transactions, transfers, savings).
    - **Financial Analyst**: Provides insights, checks budgets, and generates reports.
    - **Concierge**: Manages greetings and general small talk.
- **Financial Management**:
    - **Multi-Account & Multi-User**: Track personal and joint accounts (e.g., Mohamed & Sarah).
    - **Budgets & Alerts**: Monthly caps per category with real-time threshold warnings.
    - **Savings Goals**: Create and track progress for virtual or real savings buckets.
    - **Member Split**: Automated "Who owes what" calculations for shared expenses.
    - **Monthly Reports**: Comprehensive Markdown summaries of balances, spending, and goals.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python)
- **Agent Framework**: LangGraph / LangChain
- **LLMs**: Llama-3.3-70b-versatile & Llama-4-Scout (Groq), OpenAI models.
- **Database**: SQLite with SQLAlchemy ORM.
- **Transcription**: Whisper-large-v3.
- **UI**: Interactive streaming Web Interface (HTML/JS).

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
   Create a `.env` file with:
   ```env
   GROQ_API_KEY=your_groq_key
   ```

4. **Initialize Database**:
   The database is automatically seeded with demo accounts and categories on the first run.

5. **Run the Server**:
   ```bash
   uv run main.py
   ```
   Open `index.html` in your browser to start chatting with your agent.

## 📈 Roadmap

- **v0.2**: Recurring transactions, CSV imports from Moroccan banks, and push notifications.
- **v1.0**: Mobile App (Expo/React Native), PostgreSQL migration, and Open Banking integration.

---
Developed as a complete cross-platform financial assistant prototype.
