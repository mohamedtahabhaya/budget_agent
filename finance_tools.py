import os
from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_core.tools import tool
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from database import SessionLocal, AccountModel, TransactionModel, CategoryModel, BudgetRuleModel, SavingsGoalModel, UserModel, WorkspaceModel
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
        transactions = db.query(TransactionModel).filter(
            TransactionModel.account_slug == account_slug
        ).order_by(desc(TransactionModel.id)).limit(limit).all()
        
        if not transactions: return f"No transactions found for {account_slug}."
        
        output = f"Recent transactions for {account_slug}:\n"
        for tx in transactions:
            output += f"ID: {tx.id} | {tx.date} | {tx.merchant} | {tx.amount} MAD | Note: {tx.note}\n"
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
        
        account = db.query(AccountModel).filter(AccountModel.slug == tx.account_slug).first()
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
        cat_list = ", ".join([f"{c.name} (ID: {c.id})" for c in categories])
        
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        prompt = f"Given the category list: [{cat_list}], which ID best matches: '{category_name}'? Return ONLY the ID (e.g., cat_groceries). If no match, return 'cat_leisure'."
        
        response = llm.invoke(prompt)
        return response.content.strip()
    finally:
        db.close()

class CheckBudgetSchema(BaseModel):
    workspace_id: str
    category_id: str
    date: Optional[str] = Field(default=None, description="Date in YYYY-MM-DD format to check the budget for.")

@tool(args_schema=CheckBudgetSchema)
def check_budget(workspace_id: str, category_id: str, date: Optional[str] = None) -> str:
    """Check budget for a specific category and month. Uses transaction date or current month."""
    db = SessionLocal()
    try:
        rule = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == category_id).first()
        if not rule:
            return f"Note: No budget rule set for category '{category_id}'."
        
        if date:
            target_month = date[:7]
        else:
            target_month = datetime.now().strftime("%Y-%m")
            
        total_spent = db.query(func.sum(TransactionModel.amount)).filter(
            TransactionModel.category_id == category_id,
            TransactionModel.date.like(f"{target_month}%")
        ).scalar() or 0.0
        
        remaining = rule.monthly_cap - total_spent
        pct = (total_spent / rule.monthly_cap) * 100
        
        status = "OK"
        if pct >= rule.alert_threshold_pct: status = "WARNING"
        if pct >= 100: status = "CRITICAL (OVER BUDGET)"
            
        return f"Budget for {category_id} ({target_month}): {total_spent}/{rule.monthly_cap} MAD used ({pct:.1f}%). Status: {status}. Remaining: {remaining} MAD."
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

@tool(args_schema=CreateTransactionSchema)
def create_transaction(account_slug: str, amount: float, date: str, merchant: str, category_id: str, paid_by: str, note: str = "") -> str:
    """Record a transaction. Use POSITIVE for expenses, NEGATIVE for income/wins."""
    db = SessionLocal()
    try:
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
        if not account: return f"Error: Account '{account_slug}' not found. Use 'main_current' as default."
        
        account.balance -= amount
        
        new_transaction = TransactionModel(
            account_slug=account_slug,
            user_id=paid_by,
            category_id=category_id,
            amount=amount,
            date=date,
            merchant=merchant,
            note=note
        )
        
        db.add(new_transaction)
        db.commit()
        
        budget_info = check_budget.invoke({"workspace_id": account.workspace_id, "category_id": category_id, "date": date})
        
        return f"Success: Logged {amount} {account.currency} at {merchant}. New balance: {account.balance} {account.currency}. {budget_info}"
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
    category: Optional[str] = "General"

@tool(args_schema=CreateSavingsGoalSchema)
def create_savings_goal(workspace_id: str, name: str, target: float, target_date: str, category: str = "General") -> str:
    """Create a new savings goal bucket. target MUST be a number."""
    db = SessionLocal()
    try:
        goal = SavingsGoalModel(workspace_id=workspace_id, name=name, target=target, target_date=target_date, category=category)
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
    goal_id: Optional[int] = None
    goal_name: Optional[str] = None

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
        users = db.query(UserModel).filter(UserModel.workspace_id == workspace_id).all()
        txs = db.query(TransactionModel).join(AccountModel, TransactionModel.account_slug == AccountModel.slug).filter(AccountModel.type == "shared_current").all()
        
        total_shared = sum(t.amount for t in txs)
        if total_shared == 0: return "No shared expenses found on the joint account."
        
        output = f"Split Rule: {ws.split_rule}\nTotal Shared: {total_shared} MAD\n"
        if ws.split_rule == "equal":
            share = total_shared / len(users)
            for u in users:
                user_paid = sum(t.amount for t in txs if t.user_id == u.id)
                diff = share - user_paid
                status = f"owes {diff:.2f} MAD" if diff > 0 else f"is owed {-diff:.2f} MAD"
                output += f"- {u.name}: paid {user_paid:.2f} MAD, {status}\n"
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
            outflow = db.query(func.sum(TransactionModel.amount)).filter(TransactionModel.user_id == u.id, TransactionModel.amount > 0, TransactionModel.date.like(f"{target_month}%")).scalar() or 0.0
            inflow = db.query(func.sum(TransactionModel.amount)).filter(TransactionModel.user_id == u.id, TransactionModel.amount < 0, TransactionModel.date.like(f"{target_month}%")).scalar() or 0.0
            report += f"- **{u.name}**: Spent {outflow:,.2f} | Received {-inflow:,.2f} MAD\n"
            
        report += "\n## Top Categories\n"
        cats = db.query(TransactionModel.category_id, func.sum(TransactionModel.amount).label('total')).filter(TransactionModel.amount > 0, TransactionModel.date.like(f"{target_month}%")).group_by(TransactionModel.category_id).order_by(desc('total')).limit(5).all()
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
                file=audio_file,
                response_format="text"
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
        
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": base64_image},
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

@tool(args_schema=TransferSchema)
def transfer(source_slug: str, dest_slug: str, amount: float) -> str:
    """Move money between any two accounts within the workspace."""
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