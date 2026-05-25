import os
from langgraph.graph import StateGraph, START, END 
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import AgentState
from finance_tools import budget_tools, data_tools, analyst_tools
from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile", streaming=True)

tool_node = ToolNode(tools=budget_tools) 
memory = MemorySaver()

def create_agent(llm, tools, system_prompt, agent_name):
    """Fonction usine pour créer nos experts financiers."""
    llm_with_tools = llm.bind_tools(tools)
    
    def agent_node(state: AgentState):
        workspace = state.get("workspace_id", "default_workspace")
        user = state.get("user_id", "default_user")
        context_prompt = f"{system_prompt}\n\nCURRENT CONTEXT:\n- Workspace ID: {workspace}\n- User ID (The person talking to you): {user}\n- Today's Date: {datetime.now().strftime('%Y-%m-%d')}"
            
        messages_for_llm = [SystemMessage(content=context_prompt)] + state["messages"]
        response = llm_with_tools.invoke(messages_for_llm)
        return {"messages": [response], "sender": agent_name}
        
    return agent_node

data_prompt = """You are the Data Entry Expert. 
Your role is to MODIFY the database: create transactions, handle transfers, and manage savings goals.

CRITICAL ACCOUNT MAPPING:
- "Joint Account", "Shared", or "Household" -> Use slug: 'joint_current' (MANDATORY).
- "Main Account", "Personal", or "I paid" -> Use slug: 'main_current'.

WORKFLOWS:
1. NEW EXPENSE: 'categorize' -> 'create_transaction' -> 'get_balances'.
2. TRANSFER: 'transfer' -> 'get_balances'.
3. SAVINGS: 'update_savings_goal'.

RULES:
- ACTION ORIENTED: Call tools immediately with defaults (date=today, merchant=Unknown) if details are missing.
- NUMBERS ONLY: Use raw floats.
- LANGUAGE: ALWAYS respond in the user's language.
"""

analyst_prompt = """You are the Financial Analyst. 
Your role is to READ and SYNTHESIZE data: balances, budgets, splits, and reports.

WORKFLOWS:
1. OVERVIEW/REPORT: Always use 'generate_report' for summaries or "how am I doing" queries.
2. SPLITS: Use 'compute_split' for "who owes what".
3. BALANCES: Use 'get_balances' for current status.

RULES:
- DATA ONLY: Never guess values. Always call your tools first.
- LANGUAGE: ALWAYS respond in user's language.
"""

general_prompt = """You are the friendly Financial Concierge. 
Your role is to greet the user. Only for greetings and small talk."""

supervisor_prompt = """You are the Supervisor of a Financial AI team. 
Analyze the conversation history. If all tasks or questions requested by the user have been answered, confirmed, or resolved in the history, you MUST return 'FINISH'.
Otherwise, choose the next expert who needs to act:
- If there are pending database updates (creating transactions, transfers, savings goals) -> 'data_agent'.
- If there are pending reads/reports (summaries, balances, budget status, splits) -> 'analyst_agent'.
- Greetings / small talk only -> 'general_agent'.

Respond ONLY with: data_agent, analyst_agent, general_agent, or FINISH."""

data_agent_node = create_agent(llm, data_tools, data_prompt, "data_agent")
analyst_agent_node = create_agent(llm, analyst_tools, analyst_prompt, "analyst_agent")
general_agent_node = create_agent(llm, [], general_prompt, "general_agent")

class SupervisorResponse(BaseModel):
    """Decide which agent should act next."""
    next_agent: Literal["data_agent", "analyst_agent", "general_agent", "FINISH"]

def supervisor_node(state: AgentState):
    print("[SUPERVISOR] Routing...")
    
    cleaned_messages = []
    for msg in state["messages"]:
        if isinstance(msg, tuple):
            role, content = msg
            if role in ["user", "human"]:
                cleaned_messages.append(HumanMessage(content=content))
            elif role in ["assistant", "ai"]:
                cleaned_messages.append(AIMessage(content=content))
            elif role == "tool":
                cleaned_messages.append(AIMessage(content=f"[Tool Result]: {content}"))
        else:
            if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
                cleaned_messages.append(HumanMessage(content=msg.content))
            elif getattr(msg, "type", "") == "ai":
                cleaned_messages.append(AIMessage(content=msg.content))
            elif getattr(msg, "type", "") == "tool":
                cleaned_messages.append(AIMessage(content=f"[Tool Result]: {msg.content}"))
            else:
                # Fallback for any other type (e.g. custom or SystemMessage)
                cleaned_messages.append(HumanMessage(content=str(msg.content) if hasattr(msg, "content") else str(msg)))
            
    messages_for_llm = [SystemMessage(content=supervisor_prompt)] + cleaned_messages
    
    try:
        llm_with_router = llm.with_structured_output(SupervisorResponse)
        response = llm_with_router.invoke(messages_for_llm)
        decision = response.next_agent
    except Exception as e:
        print(f"[SUPERVISOR ERROR] Fallback routing due to: {e}")
        res = llm.invoke(messages_for_llm)
        content = res.content.lower()
        if "data_agent" in content: decision = "data_agent"
        elif "analyst_agent" in content: decision = "analyst_agent"
        elif "general_agent" in content: decision = "general_agent"
        else: decision = "FINISH"

    print(f"[SUPERVISOR] Route -> {decision}")
    if decision == state.get("sender"):
        print(f"[SUPERVISOR] Loop detected (decision '{decision}' matches sender). Overriding to FINISH.")
        decision = "FINISH"
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

builder.add_conditional_edges(
    "supervisor",
    route_after_supervisor, 
    {
        "data_agent": "data_agent",
        "analyst_agent": "analyst_agent",
        "general_agent": "general_agent",
        END: END
    }
)

builder.add_conditional_edges("data_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("analyst_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("general_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("tools", route_after_tools, {"data_agent": "data_agent", "analyst_agent": "analyst_agent"})

graph = builder.compile(checkpointer=memory)