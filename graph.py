import os
import warnings
warnings.filterwarnings("ignore", message=".*PydanticSerializationUnexpectedValue.*")
from dotenv import load_dotenv
load_dotenv()
from langgraph.graph import StateGraph, START, END 
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import AgentState
from finance_tools import budget_tools, data_tools, analyst_tools
from pydantic import BaseModel
from typing import Literal
from datetime import datetime
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini", streaming=True)

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
Your role is to MODIFY the database: create transactions, handle transfers, manage savings goals, schedule recurring transactions, and import bank CSV statements.

CRITICAL ACCOUNT MAPPING & USERS:
- "Joint Account", "Shared", or "Household" -> Use slug: 'joint_current' (MANDATORY).
- Mohamed's Personal account / "Main Account" / "Personal" (when Mohamed speaks or default) -> Use slug: 'main_current' and set paid_by: 'user_mohamed'.
- Taha's Personal account / "Taha's account" / "Taha Personal" (when Taha speaks or Taha is mentioned) -> Use slug: 'taha_personal' and set paid_by: 'user_taha'.
- If the request states Taha paid or Taha transfers, use user_taha and taha_personal.
- If the request states Mohamed paid or Mohamed transfers, use user_mohamed and main_current.

WORKFLOWS:
1. NEW EXPENSE: 'categorize' -> 'create_transaction' -> 'get_balances'.
2. TRANSFER: 'transfer' -> 'get_balances'.
3. SAVINGS: 'update_savings_goal'.
4. RECURRING/SUBSCRIPTION: 'create_recurring_transaction' to schedule a weekly or monthly subscription/transaction. Use 'delete_recurring_transaction' to cancel/delete a scheduled recurring transaction by ID.
5. BANK IMPORT: 'import_bank_csv' to parse CSV statements (Attijariwafa, BMCE, SG) and load them into the database.
6. PROCESS RECURRING: 'process_recurring_transactions' to trigger pending occurrences.

RULES:
- ACTION ORIENTED: Call tools immediately with defaults (date=today, merchant=Unknown) if details are missing.
- NUMBERS ONLY: Use raw floats.
- LANGUAGE: ALWAYS respond in the user's language.
"""

analyst_prompt = """You are the Financial Analyst. 
Your role is to READ and SYNTHESIZE data: balances, budgets, splits, reports, recurring schedules, and notifications/alerts.

WORKFLOWS:
1. OVERVIEW/REPORT: Always use 'generate_report' for summaries or "how am I doing" queries.
2. SPLITS: Use 'compute_split' for "who owes what".
3. BALANCES: Use 'get_balances' for current status.
4. RECURRING SCHEDULES: Use 'list_recurring_transactions' to list scheduled recurring entries.
5. ALERTS/NOTIFICATIONS: Use 'list_notifications' to see recent warnings, system alerts, or budget violations.

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

data_agent_node = create_agent(llm, budget_tools, data_prompt, "data_agent")
analyst_agent_node = create_agent(llm, budget_tools, analyst_prompt, "analyst_agent")
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
        if "data" in content or "saisie" in content or "data_agent" in content or "data-agent" in content:
            decision = "data_agent"
        elif "analyst" in content or "analyse" in content or "analyst_agent" in content or "analyst-agent" in content:
            decision = "analyst_agent"
        elif "general" in content or "concierge" in content or "general_agent" in content or "general-agent" in content:
            decision = "general_agent"
        else:
            decision = "FINISH"

    print(f"[SUPERVISOR] Route -> {decision}")

    last_msg = state["messages"][-1]
    is_user_msg = False
    msg_content = ""
    if isinstance(last_msg, tuple):
        is_user_msg = last_msg[0] in ["user", "human"]
        msg_content = last_msg[1]
    else:
        is_user_msg = isinstance(last_msg, HumanMessage) or getattr(last_msg, "type", "") == "human"
        msg_content = getattr(last_msg, "content", "")

    if is_user_msg and decision == "FINISH":
        print(f"[SUPERVISOR] Overriding premature FINISH after user message.")
        msg_content_lower = str(msg_content).lower()
        if any(w in msg_content_lower for w in ["hi", "hello", "bonjour", "salut"]):
            decision = "general_agent"
        elif any(w in msg_content_lower for w in ["split", "balance", "solde", "rapport", "report", "budget"]):
            decision = "analyst_agent"
        else:
            decision = "analyst_agent"
            
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