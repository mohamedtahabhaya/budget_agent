import os
from pydantic import BaseModel, Field
from typing import Optional, List, Union
from langchain_core.tools import tool
from openai import OpenAI
from groq import Groq
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from database import SessionLocal, AccountModel, TransactionModel, CategoryModel, BudgetRuleModel, SavingsGoalModel, UserModel, WorkspaceModel, SplitRuleModel, RecurringTransactionModel, NotificationModel, InvitationModel
from datetime import datetime, date, timedelta
import calendar
import csv
import io
from sqlalchemy import func, desc

class ListAccountsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the current workspace to list accounts for.")
    show_archived: Optional[Union[bool, str]] = Field(default=False, description="Whether to include archived accounts.")

@tool(args_schema=ListAccountsSchema)
def list_accounts(workspace_id: str, show_archived: Optional[Union[bool, str]] = False) -> str:
    """List all accounts and balances for a workspace."""
    def parse_bool(val):
        if val is None: return False
        if isinstance(val, bool): return val
        return val.lower().strip() in ["true", "1", "yes", "on"]
    
    show_archived_bool = parse_bool(show_archived)
    db = SessionLocal()
    try:
        query = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id)
        if not show_archived_bool:
            query = query.filter(AccountModel.is_archived == False)
        accounts = query.all()
        if not accounts:
            return "No accounts found for this workspace."
        
        output = "Accounts found:\n"
        for acc in accounts:
            status = " [Archived]" if acc.is_archived else ""
            output += f"- {acc.name} (Slug: {acc.slug}, Balance: {acc.balance} {acc.currency}, Type: {acc.type}){status}\n"
        return output
    finally:
        db.close()

@tool
def get_balances(workspace_id: str) -> str:
    """Get the absolute latest balances from the database. Use this to confirm truth."""
    return list_accounts.invoke({"workspace_id": workspace_id})

@tool
def list_members(workspace_id: str) -> str:
    """Get the list of all members (users) in the workspace and their IDs (e.g. user_mohamed)."""
    db = SessionLocal()
    try:
        users = db.query(UserModel).filter(UserModel.workspace_id == workspace_id).all()
        return "\n".join([f"{u.name} (ID: {u.id})" for u in users]) or "No members found."
    finally:
        db.close()

class ListTransactionsSchema(BaseModel):
    account_slug: str
    limit: int = 5

@tool(args_schema=ListTransactionsSchema)
def list_recent_transactions(account_slug: str, limit: int = 5) -> str:
    """List the most recent transactions for an account to find IDs for correction."""
    db = SessionLocal()
    try:
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
        if not account:
            return f"Error: Account '{account_slug}' not found."
            
        transactions = db.query(TransactionModel).filter(
            TransactionModel.account_id == account.id
        ).order_by(desc(TransactionModel.id)).limit(limit).all()
        
        if not transactions: return f"No transactions found for {account_slug}."
        
        output = f"Recent transactions for {account_slug}:\n"
        for tx in transactions:
            shared_flag = " [SHARED]" if tx.is_shared else ""
            output += f"ID: {tx.id} | {tx.date} | {tx.merchant} | {tx.amount} MAD | Note: {tx.note}{shared_flag}\n"
        return output
    finally:
        db.close()

class DeleteTransactionSchema(BaseModel):
    transaction_id: Union[int, str] = Field(..., description="The ID of the transaction to delete.")

@tool(args_schema=DeleteTransactionSchema)
def delete_transaction(transaction_id: Union[int, str]) -> str:
    """Delete a transaction by its ID and restore the account balance."""
    db = SessionLocal()
    try:
        try:
            tx_id = int(transaction_id)
        except ValueError:
            return f"Error: ID must be a number. Got '{transaction_id}'."
            
        tx = db.query(TransactionModel).filter(TransactionModel.id == tx_id).first()
        if not tx: return f"Error: Transaction {tx_id} not found."
        
        account = db.query(AccountModel).filter(AccountModel.id == tx.account_id).with_for_update().first()
        if account:

            account.balance += tx.amount
            
        db.delete(tx)
        db.commit()
        return f"Success: Transaction {tx_id} deleted. Balance restored."
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

class CategorizeSchema(BaseModel):
    workspace_id: str
    category_name: str

@tool(args_schema=CategorizeSchema)
def categorize(workspace_id: str, category_name: str) -> str:
    """Map a raw category name or description to a valid database category ID."""
    db = SessionLocal()
    try:
        categories = db.query(CategoryModel).filter(CategoryModel.workspace_id == workspace_id).all()
        name_lower = category_name.lower().strip()
        keyword_mapping = {
            "grocery": "cat_groceries", "groceries": "cat_groceries", "supermarket": "cat_groceries",
            "marjane": "cat_groceries", "carrefour": "cat_groceries", "bim": "cat_groceries",
            "hanoute": "cat_groceries", "épicerie": "cat_groceries", "souk": "cat_groceries",
            "rent": "cat_rent", "loyer": "cat_rent", "apartment": "cat_rent",
            "utilities": "cat_utilities", "utility": "cat_utilities", "lydec": "cat_utilities", 
            "onee": "cat_utilities", "electricity": "cat_utilities", "water": "cat_utilities", 
            "gas": "cat_utilities", "internet": "cat_utilities", "inwi": "cat_utilities", 
            "telecom": "cat_utilities", "iam": "cat_utilities", "orange": "cat_utilities",
            "transport": "cat_transport", "petrol": "cat_transport", "essence": "cat_transport",
            "taxi": "cat_transport", "careem": "cat_transport", "uber": "cat_transport", "indrive": "cat_transport",
            "train": "cat_transport", "oncf": "cat_transport", "bus": "cat_transport", 
            "parking": "cat_transport",
            "dining": "cat_dining", "restaurant": "cat_dining", "cafe": "cat_dining", 
            "takeaway": "cat_dining", "glovo": "cat_dining", "jumia": "cat_dining",
            "health": "cat_health", "pharmacy": "cat_health", "pharmacie": "cat_health",
            "doctor": "cat_health", "médecin": "cat_health", "clinic": "cat_health", 
            "mutuelle": "cat_health",
            "personal": "cat_personal", "salon": "cat_personal", "gym": "cat_personal", 
            "cosmetics": "cat_personal", "coiffeur": "cat_personal",
            "leisure": "cat_leisure", "shopping": "cat_leisure", "clothes": "cat_leisure", 
            "electronics": "cat_leisure", "hobbies": "cat_leisure",
            "travel": "cat_travel", "hotel": "cat_travel", "flight": "cat_travel", 
            "ram": "cat_travel", "airbnb": "cat_travel",
            "kids": "cat_kids", "school": "cat_kids", "daycare": "cat_kids", 
            "gift": "cat_kids", "family": "cat_kids",
            "savings": "cat_savings", "transfer": "cat_savings",
            "salary": "cat_income", "freelance": "cat_income", "income": "cat_income"
        }
        
        for keyword, cat_id in keyword_mapping.items():
            if keyword in name_lower:
                for c in categories:
                    if c.id == cat_id:
                        return cat_id
        
        for c in categories:
            if c.name.lower() == name_lower or c.id.lower() == name_lower:
                return c.id
                
        cat_list = ", ".join([f"{c.name} (ID: {c.id})" for c in categories])
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        prompt = f"Given the category list: [{cat_list}], which ID best matches: '{category_name}'? Return ONLY the ID (e.g., cat_groceries). If no match, return 'cat_leisure'."
        response = llm.invoke(prompt)
        matched_id = response.content.strip()
        
        if matched_id in [c.id for c in categories]:
            return matched_id
        return "cat_leisure"
    finally:
        db.close()

class CheckBudgetSchema(BaseModel):
    workspace_id: str
    category_id: str
    date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD format to check the budget for.")
    account_slug: Optional[str] = Field(default=None, description="Account slug to check specific account budget.")
    user_id: Optional[str] = Field(default=None, description="User ID to check user specific budget.")

@tool(args_schema=CheckBudgetSchema)
def check_budget(workspace_id: str, category_id: str, date: Optional[str] = None, account_slug: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """Check budget for a specific category and month. Respects workspace, user, and account scopes."""
    db = SessionLocal()
    try:
        rules = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == category_id).all()
        if not rules:
            return f"Note: No budget rule set for category '{category_id}'."
        
        target_month = date[:7] if date else datetime.now().strftime("%Y-%m")
        outputs = []
        
        for rule in rules:
            q = db.query(func.sum(TransactionModel.amount)).join(
                AccountModel, TransactionModel.account_id == AccountModel.id
            ).filter(
                TransactionModel.category_id == category_id,
                TransactionModel.date.like(f"{target_month}%"),
                AccountModel.workspace_id == workspace_id
            )
            
            scope_desc = "workspace"
            if rule.scope_type == "account":
                q = q.filter(AccountModel.id == int(rule.scope_id))
                scope_desc = f"account {rule.scope_id}"
            elif rule.scope_type == "user":
                q = q.filter(TransactionModel.user_id == rule.scope_id)
                scope_desc = f"user {rule.scope_id}"
                
            total_spent = q.scalar() or 0.0
            remaining = rule.monthly_cap - total_spent
            pct = (total_spent / rule.monthly_cap) * 100
            
            status = "OK"
            if pct >= rule.alert_threshold_pct: status = "WARNING"
            if pct >= 100: status = "CRITICAL (OVER BUDGET)"
            
            outputs.append(
                f"Budget ({scope_desc}) for {category_id} ({target_month}): {total_spent}/{rule.monthly_cap} MAD used ({pct:.1f}%). Status: {status}. Remaining: {remaining} MAD."
            )
            
        return "\n".join(outputs)
    finally:
        db.close()

class CreateTransactionSchema(BaseModel):
    account_slug: str = Field(description="Account slug (e.g. main_current)")
    amount: Union[float, str] = Field(description="Amount: POSITIVE for expenses, NEGATIVE for income.")
    date: str = Field(description="YYYY-MM-DD")
    merchant: str = Field(description="Merchant name")
    category_id: str = Field(description="MUST be a valid category ID (e.g. cat_groceries). Call categorize first if unsure.")
    paid_by: str = Field(description="User ID")
    note: str = ""
    is_shared: Union[bool, str] = Field(default=False, description="Set to True if this is a personal account expense that should be split with the workspace.")
    currency: Optional[str] = Field(default=None, description="Optional currency code of the transaction (e.g., 'EUR', 'USD', 'MAD'). If different from the account's currency, it will be auto-converted.")

@tool(args_schema=CreateTransactionSchema)
def create_transaction(
    account_slug: str, 
    amount: Union[float, str], 
    date: str, 
    merchant: str, 
    category_id: str, 
    paid_by: str, 
    note: str = "", 
    is_shared: Union[bool, str] = False,
    currency: Optional[str] = None
) -> str:
    """Record a transaction. Use POSITIVE for expenses, NEGATIVE for income/wins."""
    # Coerce parameters to correct types robustly
    if isinstance(amount, str):
        try:
            amount = float(amount.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: amount must be a number, got '{amount}'"
    if isinstance(is_shared, str):
        is_shared = is_shared.lower().strip() in ["true", "1", "yes", "on"]
        
    db = SessionLocal()
    try:
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).with_for_update().first()
        if not account: return f"Error: Account '{account_slug}' not found. Use 'main_current' as default."

        # Perform auto-conversion if currency is specified and differs from the account's currency
        EXCHANGE_RATES = {
            "MAD": 1.0,
            "EUR": 11.0,
            "USD": 10.0,
            "GBP": 13.0
        }
        
        orig_amount = amount
        orig_currency = currency.upper().strip() if currency else None
        acc_currency = account.currency.upper().strip() if account.currency else "MAD"
        
        if orig_currency and orig_currency != acc_currency:
            rate_from = EXCHANGE_RATES.get(orig_currency, 1.0)
            rate_to = EXCHANGE_RATES.get(acc_currency, 1.0)
            # Convert orig_amount to base (MAD) first, then to target currency
            amount_in_mad = amount * rate_from
            amount = amount_in_mad / rate_to
            
            conversion_note = f"[{orig_amount} {orig_currency} converted to {acc_currency}]"
            if note:
                note = f"{note} {conversion_note}"
            else:
                note = conversion_note

        account.balance -= amount
        
        new_transaction = TransactionModel(
            account_id=account.id,
            user_id=paid_by,
            category_id=category_id,
            amount=amount,
            date=date,
            merchant=merchant,
            note=note,
            is_shared=is_shared
        )
        
        db.add(new_transaction)
        db.commit()
        
        budget_info = check_budget.invoke({
            "workspace_id": account.workspace_id, 
            "category_id": category_id, 
            "date": date,
            "account_slug": account_slug,
            "user_id": paid_by
        })
        
        if "CRITICAL" in budget_info or "WARNING" in budget_info:
            from database import NotificationPreferenceModel
            user_pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == paid_by).first()
            if not user_pref or user_pref.budget_alerts_enabled:
                alert_type = "CRITICAL" if "CRITICAL" in budget_info else "WARNING"
                notif = NotificationModel(
                    workspace_id=account.workspace_id,
                    message=f"{alert_type} Budget Alert: {budget_info}",
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    is_read=False
                )
                db.add(notif)
                db.commit()
        
        return f"Success: Logged {amount} {account.currency} at {merchant} on {account.name}. New balance: {account.balance} {account.currency}. {budget_info}"
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

class CreateSavingsGoalSchema(BaseModel):
    workspace_id: str
    name: str
    target: Union[float, str]
    target_date: str
    category: str = Field(default="General", description="Category of the goal")
    account_id: Optional[Union[int, str]] = Field(default=None, description="Optional ID, name, or slug of the savings/personal account to link (e.g. 'mohamed_savings', 'taha_savings', 'Mohamed Savings').")

@tool(args_schema=CreateSavingsGoalSchema)
def create_savings_goal(workspace_id: str, name: str, target: Union[float, str], target_date: str, category: str = "General", account_id: Optional[Union[int, str]] = None) -> str:
    """Create a new savings goal bucket. target MUST be a number."""
    if isinstance(target, str):
        try:
            target = float(target.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: target must be a number, got '{target}'"
            
    db = SessionLocal()
    try:
        resolved_account_id = None
        if account_id is not None:
            account_str = str(account_id).strip()
            if account_str:
                # Try parsing as integer first
                try:
                    resolved_account_id = int(account_str)
                except ValueError:
                    # Look up by slug or exact name
                    acc = db.query(AccountModel).filter(
                        AccountModel.workspace_id == workspace_id,
                        (AccountModel.slug == account_str) | (AccountModel.name.ilike(account_str))
                    ).first()
                    if acc:
                        resolved_account_id = acc.id
                    else:
                        # Try partial case-insensitive name match
                        acc_partial = db.query(AccountModel).filter(
                            AccountModel.workspace_id == workspace_id,
                            AccountModel.name.ilike(f"%{account_str}%")
                        ).first()
                        if acc_partial:
                            resolved_account_id = acc_partial.id
                        else:
                            return f"Error: Linked account '{account_str}' not found in workspace."

        goal = SavingsGoalModel(
            workspace_id=workspace_id,
            name=name,
            target=target,
            target_date=target_date,
            category=category,
            account_id=resolved_account_id
        )
        db.add(goal)
        db.commit()
        
        linked_info = ""
        if resolved_account_id:
            linked_acc = db.query(AccountModel).filter(AccountModel.id == resolved_account_id).first()
            if linked_acc:
                linked_info = f" (linked to account '{linked_acc.name}')"
        return f"Goal '{name}' created: {target} MAD by {target_date}{linked_info}."
    finally:
        db.close()

@tool
def list_savings_goals(workspace_id: str) -> str:
    """List all savings goals and their progress."""
    db = SessionLocal()
    try:
        goals = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id).all()
        if not goals: return "No savings goals found."
        output = "Savings Goals:\n"
        for g in goals:
            pct = (g.current / g.target) * 100
            output += f"- {g.name} (ID: {g.id}): {g.current}/{g.target} MAD ({pct:.1f}%) by {g.target_date}\n"
        return output
    finally:
        db.close()

class UpdateSavingsGoalSchema(BaseModel):
    workspace_id: str = Field(description="Workspace ID")
    amount: Union[float, str] = Field(description="Amount to save (positive to deposit, negative to withdraw)")
    goal_id: Optional[Union[int, str]] = Field(default=None, description="Goal ID")
    goal_name: Optional[str] = Field(default=None, description="Goal Name")
    initiated_by: Optional[str] = Field(default="user_mohamed", description="The user ID of the person saving the money")

@tool(args_schema=UpdateSavingsGoalSchema)
def update_savings_goal(workspace_id: str, amount: Union[float, str], goal_id: Optional[Union[int, str]] = None, goal_name: Optional[str] = None, initiated_by: str = "user_mohamed") -> str:
    """Add or withdraw money from a savings goal by ID or name, executing a real database transfer between the member's personal account and the Emergency Fund."""
    if isinstance(amount, str):
        try:
            amount = float(amount.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: amount must be a number, got '{amount}'"
            
    if amount == 0:
        return "Error: Amount must be non-zero."
        
    if isinstance(goal_id, str):
        try:
            goal_id = int(goal_id.strip()) if goal_id.strip() else None
        except ValueError:
            goal_id = None
            
    db = SessionLocal()
    try:
        # Find the savings goal
        query = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id)
        if goal_id:
            goal = query.filter(SavingsGoalModel.id == goal_id).first()
        elif goal_name:
            goal = query.filter(SavingsGoalModel.name.ilike(f"%{goal_name}%")).first()
        else:
            return "Error: Provide goal_id or goal_name."
            
        if not goal:
            return "Error: Goal not found."
            
        # Locate the user's personal account and the shared savings account
        user_account = db.query(AccountModel).filter(
            AccountModel.workspace_id == workspace_id,
            AccountModel.owner_user_id == initiated_by,
            AccountModel.type == "personal"
        ).with_for_update().first()
        
        if goal.account_id:
            savings_account = db.query(AccountModel).filter(
                AccountModel.id == goal.account_id
            ).with_for_update().first()
        else:
            savings_account = db.query(AccountModel).filter(
                AccountModel.workspace_id == workspace_id,
                AccountModel.slug == "emergency_fund"
            ).with_for_update().first()
        
        if not savings_account:
            return "Error: Emergency Fund savings account ('emergency_fund') not found in this workspace."
            
        if amount > 0:
            # Deposit: Personal Account -> Emergency Fund
            source = user_account
            dest = savings_account
            if not source:
                return f"Error: Personal account for user '{initiated_by}' not found."
            if source.balance < amount:
                return f"Error: Insufficient funds in personal account '{source.name}'. Current balance is {source.balance} MAD."
                
            source.balance -= amount
            dest.balance += amount
        else:
            # Withdrawal: Emergency Fund -> Personal Account
            source = savings_account
            dest = user_account
            abs_amount = abs(amount)
            if not dest:
                return f"Error: Personal account for user '{initiated_by}' not found to return funds to."
            if source.balance < abs_amount:
                return f"Error: Insufficient funds in Emergency Fund. Current savings balance is {source.balance} MAD."
                
            source.balance -= abs_amount
            dest.balance += abs_amount
            
        # Update goal progress
        goal.current += amount
        
        # Log Transaction History
        date_str = datetime.now().strftime("%Y-%m-%d")
        note_text = f"Goal '{goal.name}' deposit" if amount > 0 else f"Goal '{goal.name}' withdrawal"
        
        tx_source = TransactionModel(
            account_id=source.id,
            user_id=initiated_by,
            category_id="cat_savings",
            amount=abs(amount),
            date=date_str,
            merchant="Savings Goal",
            note=f"{note_text} - to {dest.name}" if amount > 0 else f"{note_text} - from {source.name}"
        )
        tx_dest = TransactionModel(
            account_id=dest.id,
            user_id=initiated_by,
            category_id="cat_savings",
            amount=-abs(amount),
            date=date_str,
            merchant="Savings Goal",
            note=f"{note_text} - from {source.name}" if amount > 0 else f"{note_text} - to {dest.name}"
        )
        
        db.add_all([tx_source, tx_dest])
        db.commit()
        
        action_word = "Saved" if amount > 0 else "Withdrew"
        return f"Success: {action_word} {abs(amount)} MAD for goal '{goal.name}'. Real balances updated -> {source.name}: {source.balance} MAD, {dest.name}: {dest.balance} MAD. Goal progress -> {goal.current}/{goal.target} MAD."
    except Exception as e:
        db.rollback()
        return f"Database Error: {str(e)}"
    finally:
        db.close()

@tool
def compute_split(workspace_id: str) -> str:
    """Calculate who owes what based on shared expenses and split rule."""
    db = SessionLocal()
    try:
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
        if not ws: return "Error: Workspace not found."
        
        users = db.query(UserModel).filter(UserModel.workspace_id == workspace_id).all()
        if not users: return "No members found in this workspace."
        
        joint_accounts = db.query(AccountModel).filter(
            AccountModel.workspace_id == workspace_id,
            AccountModel.type == "shared_current"
        ).all()
        joint_acc_ids = [a.id for a in joint_accounts]
        
        target_month = datetime.now().strftime("%Y-%m")
        
        split_percentages = {}
        if ws.split_rule == "equal":
            pct = 1.0 / len(users)
            for u in users:
                split_percentages[u.id] = pct
        elif ws.split_rule == "proportional":
            total_income = sum(u.income_mad for u in users)
            if total_income == 0:
                pct = 1.0 / len(users)
                for u in users: split_percentages[u.id] = pct
            else:
                for u in users:
                    split_percentages[u.id] = u.income_mad / total_income
        else:
            rule = db.query(SplitRuleModel).filter(SplitRuleModel.workspace_id == workspace_id).first()
            if rule:
                import json
                try:
                    percentages = json.loads(rule.member_percentages)
                    for u in users:
                        split_percentages[u.id] = percentages.get(u.id, 1.0 / len(users))
                except Exception:
                    pct = 1.0 / len(users)
                    for u in users: split_percentages[u.id] = pct
            else:
                pct = 1.0 / len(users)
                for u in users: split_percentages[u.id] = pct

        joint_expenses = 0.0
        if joint_acc_ids:
            joint_expenses = db.query(func.sum(TransactionModel.amount)).filter(
                TransactionModel.account_id.in_(joint_acc_ids),
                TransactionModel.amount > 0,
                TransactionModel.date.like(f"{target_month}%"),
                TransactionModel.category_id != "cat_savings"
            ).scalar() or 0.0
            
        personal_shared_expenses_by_user = {}
        total_personal_shared = 0.0
        for u in users:
            user_shared = db.query(func.sum(TransactionModel.amount)).join(
                AccountModel, TransactionModel.account_id == AccountModel.id
            ).filter(
                AccountModel.type == "personal",
                TransactionModel.user_id == u.id,
                TransactionModel.is_shared == True,
                TransactionModel.amount > 0,
                TransactionModel.date.like(f"{target_month}%")
            ).scalar() or 0.0
            personal_shared_expenses_by_user[u.id] = user_shared
            total_personal_shared += user_shared
            
        total_household_cost = joint_expenses + total_personal_shared
        
        contributions_by_user = {}
        total_contributions = 0.0
        for u in users:
            user_contrib = 0.0
            if joint_acc_ids:
                user_contrib = db.query(func.sum(TransactionModel.amount)).filter(
                    TransactionModel.account_id.in_(joint_acc_ids),
                    TransactionModel.amount < 0,
                    TransactionModel.user_id == u.id,
                    TransactionModel.date.like(f"{target_month}%")
                ).scalar() or 0.0
                user_contrib = -user_contrib
            contributions_by_user[u.id] = user_contrib
            total_contributions += user_contrib
            
        output = f"Split Calculation ({target_month}):\n"
        output += f"- Split Rule: {ws.split_rule.upper()}\n"
        output += f"- Joint Account Expenses: {joint_expenses:,.2f} MAD\n"
        output += f"- Personal Shared Expenses: {total_personal_shared:,.2f} MAD\n"
        output += f"- Total Shared Household Cost: {total_household_cost:,.2f} MAD\n\n"
        
        output += "Member Details:\n"
        member_net_positions = {}
        for u in users:
            pct = split_percentages[u.id]
            expected_share = pct * total_household_cost
            contrib = contributions_by_user[u.id]
            direct_paid = personal_shared_expenses_by_user[u.id]
            total_paid_by_user = contrib + direct_paid
            
            net_position = expected_share - total_paid_by_user
            member_net_positions[u.id] = net_position
            
            output += (
                f"  * {u.name} (Rule Pct: {pct*100:.1f}%):\n"
                f"    - Expected Share: {expected_share:,.2f} MAD\n"
                f"    - Contributed to Joint: {contrib:,.2f} MAD\n"
                f"    - Paid directly on personal account: {direct_paid:,.2f} MAD\n"
                f"    - Net Position: {net_position:+,.2f} MAD "
                f"({'Owes' if net_position > 0.01 else 'Is Owed' if net_position < -0.01 else 'Balanced'})\n"
            )
            
        output += "\nReconciliation Suggestion:\n"
        debtors = [(uid, pos) for uid, pos in member_net_positions.items() if pos > 0.01]
        creditors = [(uid, -pos) for uid, pos in member_net_positions.items() if pos < -0.01]
        
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)
        
        suggestions = []
        d_idx, c_idx = 0, 0
        while d_idx < len(debtors) and c_idx < len(creditors):
            d_uid, d_amt = debtors[d_idx]
            c_uid, c_amt = creditors[c_idx]
            
            transfer_amt = min(d_amt, c_amt)
            d_name = db.query(UserModel).filter(UserModel.id == d_uid).first().name
            c_name = db.query(UserModel).filter(UserModel.id == c_uid).first().name
            suggestions.append(f"- **{d_name}** should pay **{transfer_amt:,.2f} MAD** to **{c_name}**")
            
            debtors[d_idx] = (d_uid, d_amt - transfer_amt)
            creditors[c_idx] = (c_uid, c_amt - transfer_amt)
            
            if debtors[d_idx][1] < 0.01: d_idx += 1
            if creditors[c_idx][1] < 0.01: c_idx += 1
            
        if not suggestions:
            output += "Everything is perfectly balanced! No transfers needed."
        else:
            output += "\n".join(suggestions)
            
        return output
    finally:
        db.close()

@tool
def generate_report(workspace_id: str, month: Optional[str] = None) -> str:
    """Produce a comprehensive financial report (spend by category, member, savings, split)."""
    db = SessionLocal()
    try:
        target_month = month or datetime.now().strftime("%Y-%m")
        report = f"# Financial Report - {target_month}\n\n"
        
        accs = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id).all()
        report += "## Balances\n"
        for a in accs:
            report += f"- **{a.name}**: {a.balance:,.2f} {a.currency}\n"
            
        users = db.query(UserModel).filter(UserModel.workspace_id == workspace_id).all()
        report += "\n## 👥 Activity per Member\n"
        for u in users:
            outflow = db.query(func.sum(TransactionModel.amount)).join(
                AccountModel, TransactionModel.account_id == AccountModel.id
            ).filter(
                TransactionModel.user_id == u.id, 
                TransactionModel.amount > 0, 
                TransactionModel.date.like(f"{target_month}%"),
                AccountModel.workspace_id == workspace_id
            ).scalar() or 0.0
            
            inflow = db.query(func.sum(TransactionModel.amount)).join(
                AccountModel, TransactionModel.account_id == AccountModel.id
            ).filter(
                TransactionModel.user_id == u.id, 
                TransactionModel.amount < 0, 
                TransactionModel.date.like(f"{target_month}%"),
                AccountModel.workspace_id == workspace_id
            ).scalar() or 0.0
            
            report += f"- **{u.name}**: Spent {outflow:,.2f} | Received {-inflow:,.2f} MAD\n"
            
        report += "\n## Top Categories & Budgets\n"
        cats = db.query(TransactionModel.category_id, func.sum(TransactionModel.amount).label('total')).join(
            AccountModel, TransactionModel.account_id == AccountModel.id
        ).filter(
            TransactionModel.amount > 0, 
            TransactionModel.date.like(f"{target_month}%"),
            AccountModel.workspace_id == workspace_id
        ).group_by(TransactionModel.category_id).order_by(desc('total')).all()
        
        for cid, total in cats:
            cat = db.query(CategoryModel).filter(CategoryModel.id == cid).first()
            cname = cat.name if cat else cid
            rule = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == cid).first()
            limit_str = f"{rule.monthly_cap:,.2f} MAD" if rule else "no limit set"
            status_str = ""
            if rule:
                pct = (total / rule.monthly_cap) * 100
                if pct >= 100:
                    status_str = " (OVER BUDGET)"
                elif pct >= rule.alert_threshold_pct:
                    status_str = " (WARNING)"
                else:
                    status_str = " (OK)"
            report += f"- **{cname}** ({cid}): {total:,.2f} MAD spent | Limit: {limit_str}{status_str}\n"
            
        report += "\n## Savings Goals\n"
        gs = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id).all()
        if not gs: report += "No goals.\n"
        for g in gs:
            pct = (g.current / g.target) * 100
            report += f"- **{g.name}**: {g.current:,.2f}/{g.target:,.2f} MAD ({pct:.1f}%)\n"
            
        report += "\n## ⚖️ Shared Split\n"
        report += compute_split.invoke({"workspace_id": workspace_id})
        
        return report
    finally:
        db.close()

class TranscribeAudioSchema(BaseModel):
    audio_file_path: str

@tool(args_schema=TranscribeAudioSchema)
def transcribe_audio(audio_file_path: str) -> str:
    """Speech-to-text on a voice note; returns the transcript."""
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3", 
                file=audio_file
            )
        return f"Transcription successful: {transcript.text}"
    except Exception as e:
        return f"Error transcribing audio: {str(e)}"

class ParseReceiptSchema(BaseModel):
    base64_image: str

@tool(args_schema=ParseReceiptSchema)
def parse_receipt_image(base64_image: str) -> str:
    """Vision call: extract merchant, total, date, line items from a receipt photo."""
    try:
        vision_llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)
        
        prompt = """
        You are an expert accountant. Analyze this receipt and extract the following information in JSON format:
        - merchant: The name of the store or merchant.
        - total_amount: The total amount paid (as a float).
        - currency: The currency symbol or code (e.g., EUR, MAD, USD).
        - date: The date of the transaction (YYYY-MM-DD).
        - category_guess: Your best guess for the expense category (e.g., Groceries, Transport, Dining out).
        - items: A brief summary of the main items purchased.
        
        Return ONLY the JSON object.
        """
        
        img_url = base64_image
        if not img_url.startswith("data:image/"):
            img_url = f"data:image/jpeg;base64,{base64_image}"

        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": img_url},
                },
            ]
        )
        
        response = vision_llm.invoke([message])
        clean_json = response.content.replace("```json", "").replace("```", "").strip()
        return clean_json
    except Exception as e:
        return f"Error parsing receipt: {str(e)}"
    
class TransferSchema(BaseModel):
    source_slug: str = Field(description="The slug of the account to take money FROM.")
    dest_slug: str = Field(description="The slug of the account to send money TO.")
    amount: Union[float, str] = Field(description="The amount of money to transfer (must be positive).")
    initiated_by: str = Field(default="user_mohamed", description="The user ID of the person making the transfer.")

@tool(args_schema=TransferSchema)
def transfer(source_slug: str, dest_slug: str, amount: Union[float, str], initiated_by: str = "user_mohamed") -> str:
    """Move money between any two accounts within the workspace. Logs transaction history."""
    if isinstance(amount, str):
        try:
            amount = float(amount.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: amount must be a number, got '{amount}'"
    if amount <= 0:
        return "Error: Transfer amount must be positive."
        
    db = SessionLocal()
    try:
        source = db.query(AccountModel).filter(AccountModel.slug == source_slug).with_for_update().first()
        dest = db.query(AccountModel).filter(AccountModel.slug == dest_slug).with_for_update().first()

        
        if not source:
            return f"Error: Source account '{source_slug}' not found."
        if not dest:
            return f"Error: Destination account '{dest_slug}' not found."
        if source.balance < amount:
            return f"Error: Insufficient funds in '{source.name}'. Current balance is {source.balance}."
        
        source.balance -= amount
        dest.balance += amount
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        tx_out = TransactionModel(
            account_id=source.id,
            user_id=initiated_by,
            category_id="cat_savings",
            amount=amount,
            date=date_str,
            merchant="Transfer",
            note=f"Transfer to {dest.name}"
        )
        tx_in = TransactionModel(
            account_id=dest.id,
            user_id=initiated_by,
            category_id="cat_savings",
            amount=-amount,
            date=date_str,
            merchant="Transfer",
            note=f"Transfer from {source.name}"
        )
        db.add_all([tx_out, tx_in])
        db.commit()
        return f"Success: Transferred {amount} {source.currency} from {source.name} to {dest.name}. New balances -> {source.name}: {source.balance}, {dest.name}: {dest.balance}"
    except Exception as e:
        db.rollback()
        return f"Database Error: {str(e)}"
    finally:
        db.close()

def parse_moroccan_date(date_str: str) -> str:
    date_str = date_str.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str

def detect_bank_and_delimiter(lines: List[str]) -> tuple:
    for i, line in enumerate(lines[:5]):
        line_lower = line.lower()
        if "date d'opération" in line_lower and "libellé" in line_lower and "montant" in line_lower:
            return "Attijariwafa", ";", lines[i:]
        elif "date de valeur" in line_lower and "libellé de l'opération" in line_lower and "montant" in line_lower:
            return "SG", ";", lines[i:]
        elif "date" in line_lower and "description" in line_lower and "débit" in line_lower and "crédit" in line_lower:
            return "BMCE", ",", lines[i:]
    
    first_line = lines[0] if lines else ""
    if ";" in first_line:
        if "valeur" in first_line.lower():
            return "SG", ";", lines
        return "Attijariwafa", ";", lines
    return "BMCE", ",", lines

def read_csv_file(file_path: str) -> str:
    for encoding in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode CSV file with standard encodings.")

class CreateRecurringTransactionSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    name: str = Field(..., description="The name of the subscription/transaction.")
    amount: Union[float, str] = Field(..., description="The positive amount for expenses, negative for income.")
    category_id: str = Field(..., description="Category ID for the transaction.")
    account_slug: str = Field(..., description="The account slug to pay from (e.g. main_current).")
    frequency: str = Field(..., description="Frequency of the transaction: 'weekly' or 'monthly'.")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format.")

@tool(args_schema=CreateRecurringTransactionSchema)
def create_recurring_transaction(workspace_id: str, name: str, amount: Union[float, str], category_id: str, account_slug: str, frequency: str, start_date: str) -> str:
    """Schedule a recurring weekly or monthly subscription/transaction."""
    if isinstance(amount, str):
        try:
            amount = float(amount.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: amount must be a number, got '{amount}'"
    db = SessionLocal()
    try:
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
        if not account:
            return f"Error: Account '{account_slug}' not found."
        
        frequency = frequency.strip().lower()
        if frequency not in ["weekly", "monthly"]:
            return f"Error: Frequency must be 'weekly' or 'monthly'. Got '{frequency}'."
            
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return f"Error: start_date must be in YYYY-MM-DD format."
            
        new_rec = RecurringTransactionModel(
            workspace_id=workspace_id,
            name=name,
            amount=amount,
            category_id=category_id,
            account_id=account.id,
            frequency=frequency,
            start_date=start_date,
            next_occurrence_date=start_date,
            is_active=True
        )
        db.add(new_rec)
        db.commit()
        db.close()
        
        process_res = ""
        try:
            from finance_tools import process_recurring_transactions
            process_res = "\n" + process_recurring_transactions.invoke({"workspace_id": workspace_id})
        except Exception as pe:
            process_res = f"\n(Auto-processing warning: {str(pe)})"
            
        return f"Success: Recurring transaction '{name}' scheduled. First occurrence: {start_date} ({frequency}).{process_res}"
    except Exception as e:
        db.rollback()
        db.close()
        return f"Error: {str(e)}"

class ListRecurringTransactionsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")

@tool(args_schema=ListRecurringTransactionsSchema)
def list_recurring_transactions(workspace_id: str) -> str:
    """List all scheduled recurring transactions."""
    db = SessionLocal()
    try:
        recs = db.query(RecurringTransactionModel).filter(RecurringTransactionModel.workspace_id == workspace_id).all()
        if not recs:
            return "No recurring transactions scheduled."
        
        output = "Recurring Transactions:\n"
        for r in recs:
            account = db.query(AccountModel).filter(AccountModel.id == r.account_id).first()
            acc_name = account.name if account else "Unknown"
            status = "Active" if r.is_active else "Inactive"
            output += f"- ID: {r.id} | {r.name} | {r.amount} MAD | Frequency: {r.frequency} | Next occurrence: {r.next_occurrence_date} | Account: {acc_name} ({status})\n"
        return output
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

class ProcessRecurringTransactionsSchema(BaseModel):
    workspace_id: Optional[str] = Field(default=None, description="Optional ID of the workspace. If not specified, processes all workspaces.")

@tool(args_schema=ProcessRecurringTransactionsSchema)
def process_recurring_transactions(workspace_id: Optional[str] = None) -> str:
    """Process any pending occurrences of recurring transactions and update their next dates."""
    db = SessionLocal()
    try:
        query = db.query(RecurringTransactionModel).filter(
            RecurringTransactionModel.is_active == True
        )
        if workspace_id:
            query = query.filter(RecurringTransactionModel.workspace_id == workspace_id)
            
        recs = query.all()
        if not recs:
            return "No active recurring transactions to process."
            
        today = date.today()
        
        triggered_count = 0
        details = []
        
        for r in recs:
            next_date_str = r.next_occurrence_date
            next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
            
            while next_date <= today:
                account = db.query(AccountModel).filter(AccountModel.id == r.account_id).first()
                if not account:
                    details.append(f"Error: Account not found for recurring transaction ID {r.id}")
                    break
                
                paid_by = account.owner_user_id
                if not paid_by:
                    owner = db.query(UserModel).filter(UserModel.workspace_id == r.workspace_id, UserModel.role == "owner").first()
                    paid_by = owner.id if owner else "user_mohamed"
                
                res = create_transaction.invoke({
                    "account_slug": account.slug,
                    "amount": r.amount,
                    "date": next_date.strftime("%Y-%m-%d"),
                    "merchant": r.name,
                    "category_id": r.category_id,
                    "paid_by": paid_by,
                    "note": f"Auto-generated recurring transaction (ID: {r.id})"
                })
                
                triggered_count += 1
                details.append(f"Generated: {r.name} - {r.amount} MAD on {next_date.strftime('%Y-%m-%d')} for account {account.name}. Result: {res}")
                
                if r.frequency == 'weekly':
                    next_date = next_date + timedelta(days=7)
                elif r.frequency == 'monthly':
                    year = next_date.year + (next_date.month // 12)
                    month = (next_date.month % 12) + 1
                    last_day = calendar.monthrange(year, month)[1]
                    day = min(next_date.day, last_day)
                    next_date = date(year, month, day)
                else:
                    next_date = next_date + timedelta(days=30)
            
            r.next_occurrence_date = next_date.strftime("%Y-%m-%d")
            
        db.commit()
        return f"Processed recurring transactions. Triggered {triggered_count} transactions.\n" + "\n".join(details)
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

class ImportBankCSVSchema(BaseModel):
    file_path: str = Field(..., description="Absolute path to the CSV file.")
    account_slug: str = Field(..., description="Account slug to import transactions into.")
    workspace_id: str = Field(..., description="The ID of the current workspace.")
    bank_name: Optional[str] = Field(default=None, description="Optional bank name: 'Attijariwafa', 'BMCE', or 'SG'. If omitted, detected automatically.")

@tool(args_schema=ImportBankCSVSchema)
def import_bank_csv(file_path: str, account_slug: str, workspace_id: str, bank_name: Optional[str] = None) -> str:
    """Import transactions from a Moroccan bank CSV statement (Attijariwafa, BMCE, SG)."""
    db = SessionLocal()
    try:
        content = read_csv_file(file_path)
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        if not lines:
            return "Error: Empty CSV file."
            
        detected_bank, delimiter, csv_lines = detect_bank_and_delimiter(lines)
        if bank_name:
            detected_bank = bank_name
            if bank_name == "BMCE":
                delimiter = ","
            else:
                delimiter = ";"
                
        reader = csv.DictReader(io.StringIO("\n".join(csv_lines)), delimiter=delimiter)
        if reader.fieldnames:
            reader.fieldnames = [f.strip().lower() for f in reader.fieldnames]
            
        imported_count = 0
        details = []
        
        for row in reader:
            cleaned_row = {k.strip().lower() if k else "": v for k, v in row.items()}
            
            raw_date = ""
            raw_merchant = ""
            raw_amount_str = "0"
            is_expense = True
            
            if detected_bank == "Attijariwafa":
                raw_date = cleaned_row.get("date d'opération", "")
                raw_merchant = cleaned_row.get("libellé", "")
                raw_amount_str = cleaned_row.get("montant", "0")
            elif detected_bank == "SG":
                raw_date = cleaned_row.get("date de valeur", "")
                raw_merchant = cleaned_row.get("libellé de l'opération", "")
                raw_amount_str = cleaned_row.get("montant", "0")
            elif detected_bank == "BMCE":
                raw_date = cleaned_row.get("date", "")
                raw_merchant = cleaned_row.get("description", "")
                debit_str = cleaned_row.get("débit", cleaned_row.get("debit", "")).strip()
                credit_str = cleaned_row.get("crédit", cleaned_row.get("credit", "")).strip()
                if debit_str:
                    raw_amount_str = debit_str
                    is_expense = True
                elif credit_str:
                    raw_amount_str = credit_str
                    is_expense = False
                else:
                    raw_amount_str = "0"
            else:
                raw_date = cleaned_row.get("date", "")
                raw_merchant = cleaned_row.get("description", cleaned_row.get("libellé", ""))
                raw_amount_str = cleaned_row.get("montant", "0")
                
            if not raw_amount_str:
                raw_amount_str = "0"
                
            cleaned_amount_str = raw_amount_str.strip().replace(" ", "").replace("\xa0", "")
            if "," in cleaned_amount_str and "." in cleaned_amount_str:
                if cleaned_amount_str.index(".") < cleaned_amount_str.index(","):
                    cleaned_amount_str = cleaned_amount_str.replace(".", "").replace(",", ".")
                else:
                    cleaned_amount_str = cleaned_amount_str.replace(",", "")
            elif "," in cleaned_amount_str:
                cleaned_amount_str = cleaned_amount_str.replace(",", ".")
                
            try:
                parsed_amount = float(cleaned_amount_str)
            except ValueError:
                parsed_amount = 0.0
                
            if detected_bank in ["Attijariwafa", "SG"]:
                if parsed_amount < 0:
                    db_amount = abs(parsed_amount)
                else:
                    db_amount = -abs(parsed_amount)
            else:
                if is_expense:
                    db_amount = abs(parsed_amount)
                else:
                    db_amount = -abs(parsed_amount)
                    
            formatted_date = parse_moroccan_date(raw_date)
            if db_amount == 0.0 or not raw_merchant or not formatted_date:
                continue
                
            category_id = categorize.invoke({
                "workspace_id": workspace_id,
                "category_name": raw_merchant
            })
            
            db_query = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
            if db_query and db_query.owner_user_id:
                paid_by = db_query.owner_user_id
            else:
                owner = db.query(UserModel).filter(UserModel.workspace_id == workspace_id, UserModel.role == "owner").first()
                paid_by = owner.id if owner else "user_mohamed"
                
            res = create_transaction.invoke({
                "account_slug": account_slug,
                "amount": db_amount,
                "date": formatted_date,
                "merchant": raw_merchant.strip(),
                "category_id": category_id,
                "paid_by": paid_by,
                "note": f"Imported from {detected_bank} statement"
            })
            
            imported_count += 1
            details.append(f"Imported: {raw_merchant.strip()} | {db_amount} MAD | Date: {formatted_date} | Category: {category_id} | Result: {res}")
            
        return f"Successfully imported {imported_count} transactions from {detected_bank} CSV statement.\n" + "\n".join(details)
    except Exception as e:
        return f"Error importing CSV: {str(e)}"
    finally:
        db.close()

class ListNotificationsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    limit: int = Field(default=10, description="The maximum number of notifications to return.")

@tool(args_schema=ListNotificationsSchema)
def list_notifications(workspace_id: str, limit: int = 10) -> str:
    """List unread or recent notifications/warnings for a workspace."""
    db = SessionLocal()
    try:
        notifs = db.query(NotificationModel).filter(
            NotificationModel.workspace_id == workspace_id
        ).order_by(desc(NotificationModel.timestamp)).limit(limit).all()
        
        if not notifs:
            return "No notifications found."
            
        output = "Recent Alerts & Notifications:\n"
        for n in notifs:
            read_flag = " [READ]" if n.is_read else " [UNREAD]"
            output += f"ID: {n.id} | {n.timestamp} | {n.message}{read_flag}\n"
            n.is_read = True
            
        db.commit()
        return output
    except Exception as e:
        return f"Error listing notifications: {str(e)}"
    finally:
        db.close()

class DeleteRecurringTransactionSchema(BaseModel):
    recurring_transaction_id: Union[int, str] = Field(..., description="The ID of the recurring transaction to delete.")

@tool(args_schema=DeleteRecurringTransactionSchema)
def delete_recurring_transaction(recurring_transaction_id: Union[int, str]) -> str:
    """Delete or cancel a scheduled recurring transaction by its ID."""
    db = SessionLocal()
    try:
        try:
            rec_id = int(recurring_transaction_id)
        except ValueError:
            return f"Error: ID must be a number. Got '{recurring_transaction_id}'."
            
        rec = db.query(RecurringTransactionModel).filter(RecurringTransactionModel.id == rec_id).first()
        if not rec:
            return f"Error: Recurring transaction ID {rec_id} not found."
        
        name = rec.name
        db.delete(rec)
        db.commit()
        return f"Success: Recurring transaction ID {rec_id} ('{name}') deleted/cancelled."
    except Exception as e:
        db.rollback()
        return f"Error deleting recurring transaction: {str(e)}"
    finally:
        db.close()

class CreateWorkspaceInviteSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace to invite the user to.")
    email: str = Field(..., description="The email address of the user being invited.")
    name: str = Field(..., description="The name of the user being invited.")
    role: str = Field(default="member", description="The role of the invited user (e.g. member, guest, admin).")
    income_mad: Union[float, str] = Field(default=0.0, description="The monthly income of the invited user in MAD.")

@tool(args_schema=CreateWorkspaceInviteSchema)
def create_workspace_invite(workspace_id: str, email: str, name: str, role: str = "member", income_mad: Union[float, str] = 0.0) -> str:
    """Create a workspace invitation for a new member, generating a unique registration/join token link."""
    if isinstance(income_mad, str):
        try:
            income_mad = float(income_mad.replace(",", ".").replace(" ", "").strip())
        except ValueError:
            return f"Error: income_mad must be a number, got '{income_mad}'"
    import uuid
    db = SessionLocal()
    try:
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
        if not ws:
            return f"Error: Workspace '{workspace_id}' not found."
        
        token = str(uuid.uuid4())
        
        invite = InvitationModel(
            workspace_id=workspace_id,
            email=email,
            name=name,
            token=token,
            role=role,
            income_mad=income_mad,
            is_accepted=False
        )
        db.add(invite)
        db.commit()
        
        accept_url = f"http://127.0.0.1:8000/invite/accept?token={token}"
        return f"Success: Workspace invitation created for {name} ({email}) under role '{role}' with income {income_mad} MAD.\nAcceptance URL: {accept_url}"
    except Exception as e:
        db.rollback()
        return f"Error creating invitation: {str(e)}"
    finally:
        db.close()

class ListInvitationsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace to list invitations for.")

@tool(args_schema=ListInvitationsSchema)
def list_invitations(workspace_id: str) -> str:
    """List all workspace invitations (both pending and accepted)."""
    db = SessionLocal()
    try:
        invites = db.query(InvitationModel).filter(InvitationModel.workspace_id == workspace_id).all()
        if not invites:
            return f"No invitations found for workspace '{workspace_id}'."
        
        output = f"Invitations for workspace '{workspace_id}':\n"
        for inv in invites:
            status = "Accepted" if inv.is_accepted else "Pending"
            output += f"- Name: {inv.name} | Email: {inv.email} | Role: {inv.role} | Income: {inv.income_mad} MAD | Status: {status} | Token: {inv.token}\n"
        return output
    except Exception as e:
        return f"Error listing invitations: {str(e)}"
    finally:
        db.close()

class GetNotificationPreferencesSchema(BaseModel):
    user_id: str = Field(..., description="The ID of the user whose notification preferences to retrieve.")

@tool(args_schema=GetNotificationPreferencesSchema)
def get_notification_preferences(user_id: str) -> str:
    """Retrieve the notification preferences for a specific user."""
    from database import NotificationPreferenceModel
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return f"Error: User '{user_id}' not found."
        
        pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == user_id).first()
        if not pref:
            pref = NotificationPreferenceModel(user_id=user_id)
            db.add(pref)
            db.commit()
            
        return f"Notification Preferences for {user.name} ({user_id}):\n" \
               f"- Budget Alerts: {'Enabled' if pref.budget_alerts_enabled else 'Disabled'}\n" \
               f"- Recurring Transactions alerts: {'Enabled' if pref.recurring_tx_enabled else 'Disabled'}\n" \
               f"- CSV Statement Import logs: {'Enabled' if pref.csv_import_enabled else 'Disabled'}\n" \
               f"- Browser Push/Desktop notifications: {'Enabled' if pref.browser_push_enabled else 'Disabled'}"
    except Exception as e:
        return f"Error retrieving preferences: {str(e)}"
    finally:
        db.close()

class UpdateNotificationPreferencesSchema(BaseModel):
    user_id: str = Field(..., description="The ID of the user whose notification preferences to update.")
    budget_alerts_enabled: Optional[Union[bool, str]] = Field(default=None, description="Enable or disable budget alerts notifications.")
    recurring_tx_enabled: Optional[Union[bool, str]] = Field(default=None, description="Enable or disable recurring transactions alerts.")
    csv_import_enabled: Optional[Union[bool, str]] = Field(default=None, description="Enable or disable CSV statement import logs.")
    browser_push_enabled: Optional[Union[bool, str]] = Field(default=None, description="Enable or disable browser push/desktop notifications.")

@tool(args_schema=UpdateNotificationPreferencesSchema)
def update_notification_preferences(
    user_id: str,
    budget_alerts_enabled: Optional[Union[bool, str]] = None,
    recurring_tx_enabled: Optional[Union[bool, str]] = None,
    csv_import_enabled: Optional[Union[bool, str]] = None,
    browser_push_enabled: Optional[Union[bool, str]] = None
) -> str:
    """Update notification preferences for a specific user."""
    def parse_bool(val):
        if val is None: return None
        if isinstance(val, bool): return val
        return val.lower().strip() in ["true", "1", "yes", "on"]
        
    budget_alerts_enabled = parse_bool(budget_alerts_enabled)
    recurring_tx_enabled = parse_bool(recurring_tx_enabled)
    csv_import_enabled = parse_bool(csv_import_enabled)
    browser_push_enabled = parse_bool(browser_push_enabled)
    from database import NotificationPreferenceModel
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            return f"Error: User '{user_id}' not found."
            
        pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == user_id).first()
        if not pref:
            pref = NotificationPreferenceModel(user_id=user_id)
            db.add(pref)
            
        changes = []
        if budget_alerts_enabled is not None:
            pref.budget_alerts_enabled = budget_alerts_enabled
            changes.append(f"Budget Alerts: {'Enabled' if budget_alerts_enabled else 'Disabled'}")
        if recurring_tx_enabled is not None:
            pref.recurring_tx_enabled = recurring_tx_enabled
            changes.append(f"Recurring Transactions alerts: {'Enabled' if recurring_tx_enabled else 'Disabled'}")
        if csv_import_enabled is not None:
            pref.csv_import_enabled = csv_import_enabled
            changes.append(f"CSV Statement Import logs: {'Enabled' if csv_import_enabled else 'Disabled'}")
        if browser_push_enabled is not None:
            pref.browser_push_enabled = browser_push_enabled
            changes.append(f"Browser Push/Desktop: {'Enabled' if browser_push_enabled else 'Disabled'}")
            
        db.commit()
        if not changes:
            return f"No preference updates provided for user '{user_id}'."
        return f"Success: Updated notification preferences for {user.name} ({user_id}):\n" + "\n".join([f"- {c}" for c in changes])
    except Exception as e:
        db.rollback()
        return f"Error updating preferences: {str(e)}"
    finally:
        db.close()

class DeleteSavingsGoalSchema(BaseModel):
    workspace_id: str = Field(description="The ID of the workspace.")
    goal_id: Optional[Union[int, str]] = Field(default=None, description="The ID of the savings goal to delete.")
    goal_name: Optional[str] = Field(default=None, description="The name of the savings goal to delete.")

@tool(args_schema=DeleteSavingsGoalSchema)
def delete_savings_goal(workspace_id: str, goal_id: Optional[Union[int, str]] = None, goal_name: Optional[str] = None) -> str:
    """Delete a savings goal entirely from the database by ID or name."""
    db = SessionLocal()
    try:
        query = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id)
        if goal_id is not None:
            if isinstance(goal_id, str):
                try:
                    goal_id = int(goal_id.strip()) if goal_id.strip() else None
                except ValueError:
                    goal_id = None
            if goal_id is not None:
                goal = query.filter(SavingsGoalModel.id == goal_id).first()
            else:
                goal = None
        elif goal_name:
            goal = query.filter(SavingsGoalModel.name.ilike(f"%{goal_name}%")).first()
        else:
            return "Error: Provide goal_id or goal_name to delete."
            
        if not goal:
            return f"Error: Savings goal not found in workspace '{workspace_id}'."
            
        name = goal.name
        db.delete(goal)
        db.commit()
        return f"Success: Savings goal '{name}' has been deleted."
    except Exception as e:
        db.rollback()
        return f"Error deleting savings goal: {str(e)}"
    finally:
        db.close()

class UpdateSavingsGoalPropertiesSchema(BaseModel):
    workspace_id: str = Field(description="The ID of the workspace.")
    goal_id: Optional[Union[int, str]] = Field(default=None, description="The ID of the savings goal to modify.")
    goal_name: Optional[str] = Field(default=None, description="The name of the savings goal to modify.")
    new_name: Optional[str] = Field(default=None, description="The new name for the goal.")
    new_target: Optional[Union[float, str]] = Field(default=None, description="The new target amount for the goal.")
    new_target_date: Optional[str] = Field(default=None, description="The new target date for the goal (YYYY-MM-DD or YYYY-MM).")
    new_category: Optional[str] = Field(default=None, description="The new category for the goal.")

@tool(args_schema=UpdateSavingsGoalPropertiesSchema)
def update_savings_goal_properties(
    workspace_id: str,
    goal_id: Optional[Union[int, str]] = None,
    goal_name: Optional[str] = None,
    new_name: Optional[str] = None,
    new_target: Optional[Union[float, str]] = None,
    new_target_date: Optional[str] = None,
    new_category: Optional[str] = None
) -> str:
    """Modify details of an existing savings goal (like changing its target date, name, target amount, or category) by ID or name."""
    db = SessionLocal()
    try:
        query = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id)
        if goal_id is not None:
            if isinstance(goal_id, str):
                try:
                    goal_id = int(goal_id.strip()) if goal_id.strip() else None
                except ValueError:
                    goal_id = None
            if goal_id is not None:
                goal = query.filter(SavingsGoalModel.id == goal_id).first()
            else:
                goal = None
        elif goal_name:
            goal = query.filter(SavingsGoalModel.name.ilike(f"%{goal_name}%")).first()
        else:
            return "Error: Provide goal_id or goal_name to identify the goal."
            
        if not goal:
            return f"Error: Savings goal not found."
            
        changes = []
        if new_name:
            old_name = goal.name
            goal.name = new_name
            changes.append(f"name renamed from '{old_name}' to '{new_name}'")
        if new_target is not None:
            if isinstance(new_target, str):
                new_target = float(new_target.replace(",", ".").replace(" ", "").strip())
            old_target = goal.target
            goal.target = new_target
            changes.append(f"target changed from {old_target} to {new_target}")
        if new_target_date:
            old_date = goal.target_date
            date_val = new_target_date.strip()
            if len(date_val) == 7: # YYYY-MM
                date_val = f"{date_val}-01"
            goal.target_date = date_val
            changes.append(f"target date changed from '{old_date}' to '{date_val}'")
        if new_category:
            old_cat = goal.category
            goal.category = new_category
            changes.append(f"category changed from '{old_cat}' to '{new_category}'")
            
        if not changes:
            return "No updates were provided."
            
        db.commit()
        return f"Success: Updated savings goal '{goal.name}': " + ", ".join(changes)
    except Exception as e:
        db.rollback()
        return f"Error updating savings goal properties: {str(e)}"
    finally:
        db.close()

class CreateAccountSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    name: str = Field(..., description="The user-friendly name of the account (e.g. 'Sarah Personal').")
    type: str = Field(..., description="The type of account: personal, shared_current, shared_savings, business, or custom.")
    owner_user_id: Optional[str] = Field(default=None, description="The user ID of the owner if type is 'personal'. Null for shared accounts.")
    currency: Optional[str] = Field(default="MAD", description="The currency of the account (default MAD).")
    balance: Optional[Union[float, str]] = Field(default=0.0, description="The initial balance of the account.")

@tool(args_schema=CreateAccountSchema)
def create_account(
    workspace_id: str,
    name: str,
    type: str,
    owner_user_id: Optional[str] = None,
    currency: str = "MAD",
    balance: Optional[Union[float, str]] = 0.0
) -> str:
    """Create a new financial account in the workspace with a unique slug."""
    db = SessionLocal()
    try:
        if balance is not None:
            if isinstance(balance, str):
                balance = float(balance.replace(",", ".").replace(" ", "").strip())
        else:
            balance = 0.0

        import re
        base_slug = re.sub(r'[^a-z0-9_]', '', name.lower().replace(' ', '_'))
        if not base_slug:
            base_slug = "account"
        
        slug = base_slug
        counter = 1
        while db.query(AccountModel).filter(AccountModel.slug == slug).first():
            slug = f"{base_slug}_{counter}"
            counter += 1

        new_acc = AccountModel(
            workspace_id=workspace_id,
            name=name,
            slug=slug,
            type=type,
            owner_user_id=owner_user_id if type == "personal" else None,
            currency=currency.upper() if currency else "MAD",
            balance=balance,
            is_archived=False
        )
        db.add(new_acc)
        db.commit()
        return f"Success: Created account '{name}' with type '{type}', currency '{new_acc.currency}', initial balance {balance} {new_acc.currency}, and slug '{slug}'."
    except Exception as e:
        db.rollback()
        return f"Error creating account: {str(e)}"
    finally:
        db.close()

class RenameAccountSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    slug: str = Field(..., description="The current slug of the account to rename.")
    new_name: str = Field(..., description="The new user-friendly name for the account.")

@tool(args_schema=RenameAccountSchema)
def rename_account(workspace_id: str, slug: str, new_name: str) -> str:
    """Rename an existing account and update its slug accordingly (preserving references)."""
    db = SessionLocal()
    try:
        acc = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id, AccountModel.slug == slug).first()
        if not acc:
            return f"Error: Account with slug '{slug}' not found in workspace '{workspace_id}'."

        old_name = acc.name
        acc.name = new_name

        import re
        base_slug = re.sub(r'[^a-z0-9_]', '', new_name.lower().replace(' ', '_'))
        if not base_slug:
            base_slug = "account"
            
        new_slug = base_slug
        counter = 1
        while db.query(AccountModel).filter(AccountModel.slug == new_slug).first():
            existing = db.query(AccountModel).filter(AccountModel.slug == new_slug).first()
            if existing.id == acc.id:
                break
            new_slug = f"{base_slug}_{counter}"
            counter += 1

        old_slug = acc.slug
        acc.slug = new_slug
        db.commit()
        return f"Success: Account '{old_name}' (slug: '{old_slug}') has been renamed to '{new_name}' (new slug: '{new_slug}')."
    except Exception as e:
        db.rollback()
        return f"Error renaming account: {str(e)}"
    finally:
        db.close()

class ArchiveAccountSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    slug: str = Field(..., description="The slug of the account to archive.")

@tool(args_schema=ArchiveAccountSchema)
def archive_account(workspace_id: str, slug: str) -> str:
    """Archive an account so that it is hidden from listings but its historical transactions remain preserved."""
    db = SessionLocal()
    try:
        acc = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id, AccountModel.slug == slug).first()
        if not acc:
            return f"Error: Account with slug '{slug}' not found in workspace '{workspace_id}'."

        acc.is_archived = True
        db.commit()
        return f"Success: Account '{acc.name}' (slug: '{slug}') has been archived successfully."
    except Exception as e:
        db.rollback()
        return f"Error archiving account: {str(e)}"
    finally:
        db.close()

class UpdateWorkspaceSettingsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    name: Optional[str] = Field(default=None, description="New workspace name.")
    currency: Optional[str] = Field(default=None, description="New default currency for the workspace (e.g. 'MAD', 'EUR').")

@tool(args_schema=UpdateWorkspaceSettingsSchema)
def update_workspace_settings(workspace_id: str, name: Optional[str] = None, currency: Optional[str] = None) -> str:
    """Update general settings of the active workspace, such as its name or default currency."""
    db = SessionLocal()
    try:
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
        if not ws:
            return f"Error: Workspace '{workspace_id}' not found."

        changes = []
        if name:
            old_name = ws.name
            ws.name = name
            changes.append(f"Workspace Name: '{old_name}' -> '{name}'")
        if currency:
            old_curr = ws.currency
            ws.currency = currency.upper().strip()
            changes.append(f"Workspace Currency: '{old_curr}' -> '{ws.currency}'")

        if not changes:
            return "No workspace updates were provided."

        db.commit()
        return f"Success: Updated workspace settings for '{workspace_id}':\n" + "\n".join([f"- {c}" for c in changes])
    except Exception as e:
        db.rollback()
        return f"Error updating workspace settings: {str(e)}"
    finally:
        db.close()

class UpdateSplitRulesSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")
    split_rule: str = Field(..., description="The split rule type: equal, proportional, or custom.")
    custom_percentages: Optional[dict] = Field(default=None, description="A dictionary map of user_id to percentage values (e.g. {'user_mohamed': 60, 'user_taha': 40}) if split_rule is 'custom'.")

@tool(args_schema=UpdateSplitRulesSchema)
def update_split_rules(workspace_id: str, split_rule: str, custom_percentages: Optional[dict] = None) -> str:
    """Update split rule mode (equal, proportional, or custom) and custom percentages mapping in the database."""
    import json
    split_rule = split_rule.lower().strip()
    if split_rule not in ["equal", "proportional", "custom"]:
        return "Error: split_rule must be one of: equal, proportional, custom."

    db = SessionLocal()
    try:
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
        if not ws:
            return f"Error: Workspace '{workspace_id}' not found."

        ws.split_rule = split_rule
        message = f"Split rule type updated to '{split_rule}'."

        if split_rule == "custom":
            if not custom_percentages:
                return "Error: custom_percentages dictionary (user_id -> percentage) is required when split_rule is 'custom'."
            
            total = 0
            for uid, val in custom_percentages.items():
                try:
                    total += float(val)
                except ValueError:
                    return f"Error: Percentage value for user '{uid}' must be a number."
            
            if not (99.9 <= total <= 100.1):
                return f"Error: Custom percentages must sum to 100%. Got {total}%."

            rule = db.query(SplitRuleModel).filter(SplitRuleModel.workspace_id == workspace_id).first()
            if not rule:
                rule = SplitRuleModel(workspace_id=workspace_id)
                db.add(rule)
            
            pct_map = {uid: float(val) for uid, val in custom_percentages.items()}
            rule.member_percentages = json.dumps(pct_map)
            message += f" Custom percentages set: {pct_map}."

        db.commit()
        return f"Success for workspace '{workspace_id}': {message}"
    except Exception as e:
        db.rollback()
        return f"Error updating split rules: {str(e)}"
    finally:
        db.close()

class GetWorkspaceSettingsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the workspace.")

@tool(args_schema=GetWorkspaceSettingsSchema)
def get_workspace_settings(workspace_id: str) -> str:
    """Retrieve settings for the workspace including name, default currency, and split rule."""
    db = SessionLocal()
    try:
        ws = db.query(WorkspaceModel).filter(WorkspaceModel.id == workspace_id).first()
        if not ws:
            return f"Error: Workspace '{workspace_id}' not found."
            
        rule = db.query(SplitRuleModel).filter(SplitRuleModel.workspace_id == workspace_id).first()
        custom_pct = rule.member_percentages if rule else {}
        
        return f"Workspace Settings:\n- ID: {ws.id}\n- Name: {ws.name}\n- Default Currency: {ws.currency}\n- Split Rule: {ws.split_rule}\n- Custom Percentages: {custom_pct}"
    finally:
        db.close()

class UpdateBudgetLimitSchema(BaseModel):
    category_id: str = Field(..., description="The ID of the category (e.g. 'cat_groceries').")
    monthly_cap: Union[float, str] = Field(..., description="The monthly budget cap (in MAD). Set to 0 to remove/disable the limit.")
    scope_type: Optional[str] = Field(default="workspace", description="Scope type: 'workspace', 'user', or 'account'.")

@tool(args_schema=UpdateBudgetLimitSchema)
def update_budget_limit(category_id: str, monthly_cap: Union[float, str], scope_type: str = "workspace") -> str:
    """Create or update a budget limit rule for a category in the database."""
    category_id = category_id.lower().strip()
    scope_type = scope_type.lower().strip()
    if scope_type not in ["workspace", "user", "account"]:
        return "Error: scope_type must be one of: workspace, user, account."
        
    try:
        monthly_cap_float = float(str(monthly_cap).replace(",", ".").strip())
    except ValueError:
        return f"Error: monthly_cap must be a valid number, got '{monthly_cap}'."

    db = SessionLocal()
    try:
        cat = db.query(CategoryModel).filter(CategoryModel.id == category_id).first()
        if not cat:
            return f"Error: Category '{category_id}' does not exist in the database."
            
        rule = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == category_id).first()
        if not rule:
            if monthly_cap_float > 0:
                rule = BudgetRuleModel(
                    category_id=category_id,
                    scope_type=scope_type,
                    scope_id=None,
                    monthly_cap=monthly_cap_float,
                    alert_threshold_pct=80.0
                )
                db.add(rule)
                db.commit()
                return f"Success: Created new budget limit of {monthly_cap_float} MAD for category '{category_id}'."
            else:
                return f"Note: No budget limit existed for category '{category_id}' and monthly_cap is 0."
        else:
            if monthly_cap_float <= 0:
                db.delete(rule)
                db.commit()
                return f"Success: Removed/disabled budget limit for category '{category_id}'."
            else:
                rule.monthly_cap = monthly_cap_float
                rule.scope_type = scope_type
                db.commit()
                return f"Success: Updated budget limit for category '{category_id}' to {monthly_cap_float} MAD."
    except Exception as e:
        db.rollback()
        return f"Error updating budget limit: {str(e)}"
    finally:
        db.close()

data_tools = [create_transaction, delete_transaction, transfer, create_savings_goal, update_savings_goal, delete_savings_goal, update_savings_goal_properties, categorize, transcribe_audio, parse_receipt_image, create_recurring_transaction, import_bank_csv, process_recurring_transactions, delete_recurring_transaction, create_workspace_invite, update_notification_preferences, create_account, rename_account, archive_account, update_workspace_settings, update_split_rules, update_budget_limit]
analyst_tools = [get_balances, list_recent_transactions, list_savings_goals, compute_split, list_members, generate_report, check_budget, list_recurring_transactions, list_notifications, list_invitations, get_notification_preferences, get_workspace_settings]

budget_tools = data_tools + analyst_tools