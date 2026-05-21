from langgraph.graph import StateGraph, START, END 
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, RemoveMessage, HumanMessage
from pydantic import BaseModel
from typing import Literal
from state import AgentState
from finance_tools import budget_tools
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile", streaming=True)

class SupervisorResponse(BaseModel):
    """Decide which agent should act next based on the user's financial request."""
    next_agent: Literal["data_agent", "analyst_agent", "general_agent", "FINISH"]

supervisor_prompt = """You are the Supervisor of a Financial AI team. 
Your Specialists:
- data_agent: Logs expenses, reads receipts, transcribes voice notes, creates transactions.
- analyst_agent: Checks account balances, reads budgets, does financial math.
- general_agent: Greetings, chitchat, and general questions.

ROUTING RULES:
1. Greetings/General talk -> route to 'general_agent'.
2. Adding an expense, sending an image (receipt), or sending audio -> route to 'data_agent'.
3. Asking for account balances, budgets, or money owed -> route to 'analyst_agent'.
4. If the request is completed -> route to 'FINISH'."""

def main():
    llm_with_router = llm.with_structured_output(SupervisorResponse)
    response = llm_with_router.invoke([
        SystemMessage(content=supervisor_prompt),
        HumanMessage(content="i want to do a transaction")
    ])
    decision = response.next_agent

    print(f"Supervisor decision: {decision}")

if __name__ == "__main__":
    main()