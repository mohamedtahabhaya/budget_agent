from langgraph.graph import StateGraph, START, END 
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from state import AgentState
from finance_tools import budget_tools, data_tools, analyst_tools
from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

llm = ChatGroq(model="openai/gpt-oss-120b", streaming=True)

tool_node = ToolNode(tools=budget_tools) 

def create_agent(llm, tools, system_prompt, agent_name):
    llm_with_tools = llm.bind_tools(tools)
    def agent_node(state: AgentState):
        workspace = state.get("workspace_id", "default_workspace")
        user = state.get("user_id", "default_user")
        context_prompt = f"{system_prompt}\n\nCONTEXT: Workspace: {workspace}, User: {user}, Date: {datetime.now().strftime('%Y-%m-%d')}"
        messages_for_llm = [SystemMessage(content=context_prompt)] + state["messages"]
        response = llm_with_tools.invoke(messages_for_llm)
        return {"messages": [response], "sender": agent_name}
    return agent_node

data_prompt = """You are the Data Entry Expert. 

WORKFLOWS:
1. NEW EXPENSE: call 'categorize' -> 'create_transaction' -> 'get_balances'.
2. TRANSFER: call 'transfer' -> 'get_balances'.
3. CORRECTION: call 'list_recent_transactions' -> 'delete_transaction' -> 'get_balances'.

PROACTIVE RULES:
- DEFAULT ACCOUNT: Use 'main_current' if the user doesn't specify an account for transfers or expenses.
- ACTION FIRST: Don't ask questions if you can infer the data. Call the tools first.
- NO MATH: Always use tool results.
- LANGUAGE: Match the user's language.
"""

analyst_prompt = """You are the Financial Analyst. 
1. Always call 'get_balances' and 'check_budget' to provide real data.
2. If a user provides a short answer, check if it's related to a previous question.
"""

general_prompt = """You are the Concierge. Only for greetings and small talk. 
If user wants to log, check balance, or transfer, say you're connecting them to the expert."""

supervisor_prompt = """You are the Supervisor. 

ROUTING RULES:
1. Short answers (e.g. "from main", "yes", "500") -> Route back to the agent that was previously active (check the history).
2. Any mention of adding money, spending, receipts, transfers, or income -> 'data_agent'.
3. Any question about current balance or budget status -> 'analyst_agent'.
4. Greetings/jokes only -> 'general_agent'.
5. Task finished -> 'FINISH'.

Respond ONLY with the name."""

data_agent_node = create_agent(llm, data_tools, data_prompt, "data_agent")
analyst_agent_node = create_agent(llm, analyst_tools, analyst_prompt, "analyst_agent")
general_agent_node = create_agent(llm, [], general_prompt, "general_agent")

class SupervisorResponse(BaseModel):
    next_agent: Literal["data_agent", "analyst_agent", "general_agent", "FINISH"]

def supervisor_node(state: AgentState):
    print("[SUPERVISOR] Routing...")
    messages_for_llm = [SystemMessage(content=supervisor_prompt)] + state["messages"]
    llm_with_router = llm.with_structured_output(SupervisorResponse)
    try:
        response = llm_with_router.invoke(messages_for_llm)
        decision = response.next_agent
    except Exception as e:
        print(f"[SUPERVISOR] Error: {e}")
        decision = "FINISH"
    if decision == state.get("sender"):
        decision = "FINISH"
    print(f"[SUPERVISOR] Route -> {decision}")
    return {"next_agent": decision, "sender": "supervisor"}

def route_after_supervisor(state: AgentState):
    decision = state["next_agent"]
    if decision == "FINISH":
        return END
    return decision

def route_after_agent(state: AgentState):
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "supervisor"

def route_after_tools(state: AgentState):
    return state["sender"]

builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor_node) 
builder.add_node("data_agent", data_agent_node)
builder.add_node("analyst_agent", analyst_agent_node)
builder.add_node("general_agent", general_agent_node)
builder.add_node("tools", tool_node)
builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route_after_supervisor, {"data_agent": "data_agent", "analyst_agent": "analyst_agent", "general_agent": "general_agent", END: END})
builder.add_conditional_edges("data_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("analyst_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("general_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("tools", route_after_tools, {"data_agent": "data_agent", "analyst_agent": "analyst_agent"})
graph = builder.compile()