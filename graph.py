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
from langchain_groq import ChatGroq
import time

llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", streaming=True)

tool_node = ToolNode(tools=budget_tools) 
memory = MemorySaver()

def prune_messages(messages, max_messages=12):
    if len(messages) <= max_messages:
        return messages
    
    # Take the last max_messages
    pruned = messages[-max_messages:]
    
    # We must ensure we start with a HumanMessage so the conversation history makes sense to the LLM
    # and we do not start with a ToolMessage without its preceding AIMessage with tool_calls.
    while pruned and getattr(pruned[0], "type", "") != "human":
        pruned = pruned[1:]
        
    if not pruned:
        # Fallback to last 6 messages if everything got pruned
        return messages[-6:]
        
    return pruned

def invoke_llm_with_retry(model, messages, max_retries=3, initial_delay=1.0):
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            # Add a small delay between consecutive LLM steps inside the graph
            # to prevent hitting Groq's low TPM/RPM limit
            time.sleep(0.5)
            return model.invoke(messages)
        except Exception as e:
            err_msg = str(e)
            if "rate_limit" in err_msg.lower() or "429" in err_msg or "tpm" in err_msg.lower() or "rpm" in err_msg.lower():
                print(f"[LLM RATE LIMIT] Hit rate limit on attempt {attempt+1}/{max_retries}. Retrying in {delay}s... (Error: {err_msg})")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise e
    # Final try
    return model.invoke(messages)

def create_agent(llm, tools, system_prompt, agent_name):
    """Fonction usine pour créer nos experts financiers."""
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm
    
    def agent_node(state: AgentState):
        workspace = state.get("workspace_id", "default_workspace")
        user = state.get("user_id", "default_user")
        
        # Query users and accounts dynamically for context
        from database import SessionLocal, UserModel, AccountModel
        db = SessionLocal()
        users_context = "Workspace Users:\n"
        accounts_context = "Workspace Accounts:\n"
        try:
            users = db.query(UserModel).filter(UserModel.workspace_id == workspace).all()
            accounts = db.query(AccountModel).filter(AccountModel.workspace_id == workspace, AccountModel.is_archived == False).all()
            for u in users:
                is_talking = " (The person talking to you)" if u.id == user else ""
                users_context += f"- User ID: '{u.id}' | Name: '{u.name}'{is_talking}\n"
            for a in accounts:
                owner_info = f" | Owner User ID: '{a.owner_user_id}'" if a.owner_user_id else " (Shared/Joint)"
                accounts_context += f"- Slug: '{a.slug}' | Name: '{a.name}' | Type: '{a.type}'{owner_info}\n"
        except Exception as e:
            users_context += f"Error: {e}\n"
            accounts_context += f"Error: {e}\n"
        finally:
            db.close()
            
        context_prompt = (
            f"{system_prompt}\n\n"
            f"CURRENT CONTEXT:\n"
            f"- Workspace ID: {workspace}\n"
            f"- User ID: {user}\n"
            f"- Today's Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"{users_context}\n"
            f"{accounts_context}"
        )
            
        pruned_history = prune_messages(state["messages"])
        messages_for_llm = [SystemMessage(content=context_prompt)] + pruned_history
        response = invoke_llm_with_retry(llm_with_tools, messages_for_llm)
        return {"messages": [response], "sender": agent_name}
        
    return agent_node

data_prompt = """You are the Data Entry Expert. 
Your role is to MODIFY the database: create transactions, handle transfers, manage savings goals, schedule recurring transactions, import bank CSV statements, manage workspace invitations, create accounts, rename accounts, archive accounts, update workspace settings, modify split rules, and create or update budget limits (using 'update_budget_limit').

CRITICAL USER & ACCOUNT MAPPING:
- Use the dynamically provided list of "Workspace Users" and "Workspace Accounts" under CURRENT CONTEXT to identify the correct owners, slugs, and user IDs. Do NOT assume names or slugs other than what is in the list.
- When a user's name is mentioned, matches, or they are speaking, you MUST:
  - Map them to the correct User ID from the Workspace Users list.
  - Map the transaction or savings goal to that user's personal checking/current (type: 'personal') or savings (type: 'savings') account slug from the Workspace Accounts list.
- "Joint Account", "Shared", or "Household" -> Use the account with type 'shared_current' (typically slug 'joint_current').
- "Emergency Fund" or "Emergency account" -> Use the account with type 'shared_savings' (typically slug 'emergency_fund').
- CURRENCY & UNITS:
  - Treat "dhs", "dh", or "dirham" (case-insensitive) as Moroccan Dirham (MAD) by default. Do NOT assume UAE Dirham (AED) or refuse the request.
- SAVINGS GOALS: When creating a savings goal, if the user specifies linking it to their personal account or savings account (e.g., "my personal account", "my savings", "Mohamed Savings"), you MUST link it to their personal savings account (type: 'savings', e.g., 'mohamed_savings' or 'taha_savings'), NOT their checking/current account (type: 'personal'). Pass this resolved savings account's slug to the `account_id` parameter of `create_savings_goal`.

WORKFLOWS:
1. NEW EXPENSE: 'categorize' -> 'create_transaction' -> 'get_balances'.
2. TRANSFER: 'transfer' -> 'get_balances'.
3. SAVINGS (Choose ONLY the single tool that matches the user's specific request):
   - To make/create a new savings goal -> Call 'create_savings_goal'.
   - To add/deposit/withdraw money from a goal -> Call 'update_savings_goal'.
   - To cancel/delete a goal -> Call 'delete_savings_goal'.
   - To edit/modify a goal's properties (name/target/date) -> Call 'update_savings_goal_properties'.
4. RECURRING/SUBSCRIPTION: 'create_recurring_transaction' to schedule a weekly or monthly subscription/transaction. Use 'delete_recurring_transaction' to cancel/delete a scheduled recurring transaction by ID.
5. BANK IMPORT: 'import_bank_csv' to parse CSV statements (Attijariwafa, BMCE, SG) and load them into the database.
6. PROCESS RECURRING: 'process_recurring_transactions' to trigger pending occurrences.
7. INVITATIONS: 'create_workspace_invite' to create and register an invitation for a new member.
8. PREFERENCES: 'update_notification_preferences' to modify a user's notification preferences.
9. SETTINGS & ACCOUNTS: 'create_account' to add a new account, 'rename_account' to rename it, 'archive_account' to hide/archive an account, 'update_workspace_settings' to modify the workspace name/currency, and 'update_split_rules' to change the split type (equal, proportional, custom) or set custom percentage values.
10. BUDGET LIMITS: 'update_budget_limit' to create, edit or disable monthly budget caps/limits for categories.

RULES:
- ACTION ORIENTED: Call tools immediately with defaults (date=today, merchant=Unknown) if details are missing.
- CURRENCY CONVERSIONS: NEVER convert currencies yourself! If the user specifies an amount in a currency (e.g. Euro/EUR, Dollar/USD, GBP) other than the target account's currency, you MUST pass that currency code (e.g. 'EUR', 'USD') to the 'currency' parameter of the tool and pass the original user amount (e.g. 100) to the 'amount' parameter. The tool itself will automatically convert the amount.
- TRANSFER VS SAVINGS GOAL: If the destination target matches any registered bank account name or slug (like 'emergency_fund' / "Emergency Fund", 'joint_current' / "Joint Account"), you MUST use the 'transfer' tool. Only use 'update_savings_goal' or 'create_savings_goal' if the user explicitly refers to a virtual savings target, goal progress, or goal creation.
- NUMBERS ONLY: Use raw floats.
- LANGUAGE: ALWAYS respond in the user's language.
"""

analyst_prompt = """You are the Financial Analyst. 
Your role is to READ and SYNTHESIZE data: balances, budgets, splits, reports, recurring schedules, notifications/alerts, invitations, notification preferences, account structures, and workspace settings.

WORKFLOWS:
1. OVERVIEW/REPORT: Always use 'generate_report' for summaries or "how am I doing" queries.
2. SPLITS: Use 'compute_split' for "who owes what".
3. BALANCES: Use 'get_balances' for current status.
4. RECURRING SCHEDULES: Use 'list_recurring_transactions' to list scheduled recurring entries.
5. ALERTS/NOTIFICATIONS: Use 'list_notifications' to see recent warnings, system alerts, or budget violations.
6. INVITATIONS: Use 'list_invitations' to list existing invitations in a workspace.
7. PREFERENCES: Use 'get_notification_preferences' to view notification preferences for a specific user.
8. CONFIGURATION: Use 'list_accounts' to view existing accounts and 'get_workspace_settings' to view current workspace configuration.

RULES:
- DATA ONLY: Never guess values. Always call your tools first.
- LANGUAGE: ALWAYS respond in user's language.
"""

general_prompt = """You are the friendly Financial Concierge. 
Your role is to greet the user. Only for greetings and small talk."""

supervisor_prompt = """You are the Supervisor of a Financial AI team. 
Analyze the conversation history. If all tasks or questions requested by the user have been answered, confirmed, or resolved in the history, you MUST return 'FINISH'.
Otherwise, choose the next expert who needs to act:
- If there are pending database updates (creating transactions, transfers, savings goals, workspace invitations, updating notification preferences, creating/renaming/archiving accounts, updating workspace settings, split rules, updating budget limits) -> 'data_agent'.
- If there are pending reads/reports (summaries, balances, budget status, splits, listing invitations, viewing notification preferences) -> 'analyst_agent'.
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
            
    pruned_history = prune_messages(cleaned_messages)
    messages_for_llm = [SystemMessage(content=supervisor_prompt)] + pruned_history
    
    # We invoke the LLM directly without structured output to bypass tool calling / API validation bugs on Groq
    try:
        res = invoke_llm_with_retry(llm, messages_for_llm)
        content = res.content.lower().strip()
    except Exception as e:
        print(f"[SUPERVISOR ERROR] API invocation failed: {e}")
        content = ""
        
    # Standard fallback parsing
    if "data_agent" in content or "data-agent" in content:
        decision = "data_agent"
    elif "analyst_agent" in content or "analyst-agent" in content:
        decision = "analyst_agent"
    elif "general_agent" in content or "general-agent" in content:
        decision = "general_agent"
    elif "finish" in content:
        decision = "FINISH"
    else:
        # Fallback to heuristics based on the USER message content directly
        # since the model response did not contain a clear routing token or was empty/conversational
        user_msg = ""
        if state["messages"]:
            last_msg = state["messages"][-1]
            if isinstance(last_msg, tuple):
                user_msg = last_msg[1]
            else:
                user_msg = getattr(last_msg, "content", "")
        
        user_msg_lower = str(user_msg).lower()
        
        if any(w in user_msg_lower for w in ["spent", "buy", "pay", "bought", "dépens", "achète", "payé", "log", "add", "transfer", "sauve", "épargn", "import", "créer", "nommer", "archiv", "modifier", "change", "set"]):
            decision = "data_agent"
        elif any(w in user_msg_lower for w in ["split", "balance", "solde", "rapport", "report", "budget", "membres"]):
            decision = "analyst_agent"
        elif any(w in user_msg_lower for w in ["hi", "hello", "bonjour", "salut"]):
            decision = "general_agent"
        else:
            decision = "analyst_agent" # default fallback

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
        elif any(w in msg_content_lower for w in ["spent", "buy", "pay", "bought", "dépens", "achète", "payé", "log", "add", "transfer", "sauve", "épargn", "import", "créer", "nommer", "archiv", "modifier", "change", "set"]):
            decision = "data_agent"
        elif any(w in msg_content_lower for w in ["split", "balance", "solde", "rapport", "report", "budget", "membres"]):
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