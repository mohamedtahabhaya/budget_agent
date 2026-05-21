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
1. EXPENSES: 'categorize' -> 'create_transaction' -> 'get_balances'.
2. SAVINGS GOALS: 'create_savings_goal' or 'update_savings_goal'.

CRITICAL: 
- Check the ENTIRE conversation history for goal names, targets, and dates. 
- If the user already provided "buying a house" or "300000" in previous messages, USE THEM. 
- Do NOT ask for information that is already in the history.
- LANGUAGE: ALWAYS respond in the user's language (English if they speak English).
"""

analyst_prompt = """You are the Financial Analyst. 
1. Always call 'get_balances' or 'list_savings_goals' to provide real data.
2. Respond in the user's language.
"""

general_prompt = """You are the Concierge. 
- ONLY for greetings. 
- NEVER ask about amounts, accounts, or goal names. 
- If user wants to do anything financial, say: "I'm routing you to my specialist teammate." and STOP."""

supervisor_prompt = """You are the Supervisor. 

ROUTING RULES:
1. Mention of money, goal names (e.g. "buying a house"), targets, or amounts -> 'data_agent'.
2. Questions about balance, budget, or progress -> 'analyst_agent'.
3. Greetings only -> 'general_agent'.
4. Task finished -> 'FINISH'.

Respond ONLY with the agent name."""

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