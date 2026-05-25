import os
from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_core.tools import tool
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from database import SessionLocal, AccountModel, TransactionModel, CategoryModel, BudgetRuleModel, SavingsGoalModel, UserModel, WorkspaceModel, SplitRuleModel
from datetime import datetime
from sqlalchemy import func, desc

class ListAccountsSchema(BaseModel):
    workspace_id: str = Field(..., description="The ID of the current workspace to list accounts for.")

@tool(args_schema=ListAccountsSchema)
def list_accounts(workspace_id: str) -> str:
    """List all accounts and balances for a workspace."""
    db = SessionLocal()
    try:
        accounts = db.query(AccountModel).filter(AccountModel.workspace_id == workspace_id).all()
        if not accounts:
            return "No accounts found for this workspace."
        
        output = "Accounts found:\n"
        for acc in accounts:
            output += f"- {acc.name} (Slug: {acc.slug}, Balance: {acc.balance} {acc.currency}, Type: {acc.type})\n"
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
    transaction_id: int

@tool(args_schema=DeleteTransactionSchema)
def delete_transaction(transaction_id: int) -> str:
    """Delete a transaction by its ID and restore the account balance."""
    db = SessionLocal()
    try:
        tx = db.query(TransactionModel).filter(TransactionModel.id == transaction_id).first()
        if not tx: return f"Error: Transaction {transaction_id} not found."
        
        account = db.query(AccountModel).filter(AccountModel.id == tx.account_id).first()
        if account:
            account.balance += tx.amount
            
        db.delete(tx)
        db.commit()
        return f"Success: Transaction {transaction_id} deleted. Balance restored."
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
            "acima": "cat_groceries", "hanoute": "cat_groceries", "épicerie": "cat_groceries", "souk": "cat_groceries",
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
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
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
    amount: float = Field(description="Amount: POSITIVE for expenses, NEGATIVE for income.")
    date: str = Field(description="YYYY-MM-DD")
    merchant: str = Field(description="Merchant name")
    category_id: str = Field(description="MUST be a valid category ID (e.g. cat_groceries). Call categorize first if unsure.")
    paid_by: str = Field(description="User ID")
    note: str = ""
    is_shared: bool = Field(default=False, description="Set to True if this is a personal account expense that should be split with the workspace.")

@tool(args_schema=CreateTransactionSchema)
def create_transaction(account_slug: str, amount: float, date: str, merchant: str, category_id: str, paid_by: str, note: str = "", is_shared: bool = False) -> str:
    """Record a transaction. Use POSITIVE for expenses, NEGATIVE for income/wins."""
    db = SessionLocal()
    try:
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
        if not account: return f"Error: Account '{account_slug}' not found. Use 'main_current' as default."
        
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
        
        return f"Success: Logged {amount} {account.currency} at {merchant} on {account.name}. New balance: {account.balance} {account.currency}. {budget_info}"
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

class CreateSavingsGoalSchema(BaseModel):
    workspace_id: str
    name: str
    target: float
    target_date: str
    category: str = Field(default="General", description="Category of the goal")
    account_id: Optional[int] = Field(default=None, description="Optional ID of the savings account to link.")

@tool(args_schema=CreateSavingsGoalSchema)
def create_savings_goal(workspace_id: str, name: str, target: float, target_date: str, category: str = "General", account_id: Optional[int] = None) -> str:
    """Create a new savings goal bucket. target MUST be a number."""
    db = SessionLocal()
    try:
        goal = SavingsGoalModel(workspace_id=workspace_id, name=name, target=target, target_date=target_date, category=category, account_id=account_id)
        db.add(goal)
        db.commit()
        return f"Goal '{name}' created: {target} MAD by {target_date}."
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
    workspace_id: str
    amount: float
    goal_id: Optional[int] = Field(default=None, description="Goal ID")
    goal_name: Optional[str] = Field(default=None, description="Goal Name")

@tool(args_schema=UpdateSavingsGoalSchema)
def update_savings_goal(workspace_id: str, amount: float, goal_id: Optional[int] = None, goal_name: Optional[str] = None) -> str:
    """Add money to a goal by ID or name. amount MUST be a number."""
    db = SessionLocal()
    try:
        query = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == workspace_id)
        if goal_id:
            goal = query.filter(SavingsGoalModel.id == goal_id).first()
        elif goal_name:
            goal = query.filter(SavingsGoalModel.name.ilike(f"%{goal_name}%")).first()
        else:
            return "Error: Provide goal_id or goal_name."
            
        if not goal: return "Error: Goal not found."
        goal.current += amount
        db.commit()
        return f"Updated {goal.name}: {goal.current}/{goal.target} MAD."
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
            
        report += "\n## Top Categories\n"
        cats = db.query(TransactionModel.category_id, func.sum(TransactionModel.amount).label('total')).join(
            AccountModel, TransactionModel.account_id == AccountModel.id
        ).filter(
            TransactionModel.amount > 0, 
            TransactionModel.date.like(f"{target_month}%"),
            AccountModel.workspace_id == workspace_id
        ).group_by(TransactionModel.category_id).order_by(desc('total')).limit(5).all()
        
        for cid, total in cats:
            report += f"- {cid}: {total:,.2f} MAD\n"
            
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
    amount: float = Field(description="The amount of money to transfer (must be positive).")
    initiated_by: str = Field(default="user_mohamed", description="The user ID of the person making the transfer.")

@tool(args_schema=TransferSchema)
def transfer(source_slug: str, dest_slug: str, amount: float, initiated_by: str = "user_mohamed") -> str:
    """Move money between any two accounts within the workspace. Logs transaction history."""
    if amount <= 0:
        return "Error: Transfer amount must be positive."
        
    db = SessionLocal()
    try:
        source = db.query(AccountModel).filter(AccountModel.slug == source_slug).first()
        dest = db.query(AccountModel).filter(AccountModel.slug == dest_slug).first()
        
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

data_tools = [create_transaction, delete_transaction, transfer, create_savings_goal, update_savings_goal, categorize, transcribe_audio, parse_receipt_image]
analyst_tools = [get_balances, list_recent_transactions, list_savings_goals, compute_split, list_members, generate_report, check_budget]

budget_tools = data_tools + analyst_tools