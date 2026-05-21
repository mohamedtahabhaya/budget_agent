import os
from pydantic import BaseModel, Field
from typing import Optional, List
from langchain_core.tools import tool
from groq import Groq
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from database import SessionLocal, AccountModel, TransactionModel, CategoryModel, BudgetRuleModel
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
        if not accounts: return "No accounts found."
        output = "Current Balances:\n"
        for acc in accounts:
            output += f"- {acc.name}: {acc.balance} {acc.currency} (Slug: {acc.slug})\n"
        return output
    finally:
        db.close()

@tool
def get_balances(workspace_id: str) -> str:
    """Get the absolute latest balances from the database. Use this to confirm truth."""
    return list_accounts.invoke({"workspace_id": workspace_id})

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
    """Map a raw category name to a valid database category ID. Returns only the ID string."""
    db = SessionLocal()
    try:
        categories = db.query(CategoryModel).filter(CategoryModel.workspace_id == workspace_id).all()
        cat_list = ", ".join([f"{c.name} (ID: {c.id})" for c in categories])
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
        prompt = f"Category list: [{cat_list}]. Match: '{category_name}'. Return ONLY the technical ID (e.g. cat_groceries)."
        response = llm.invoke(prompt)
        return response.content.strip()
    finally:
        db.close()

class CheckBudgetSchema(BaseModel):
    workspace_id: str
    category_id: str
    date: Optional[str] = None

@tool(args_schema=CheckBudgetSchema)
def check_budget(workspace_id: str, category_id: str, date: Optional[str] = None) -> str:
    """Check budget for a category ID and month."""
    db = SessionLocal()
    try:
        rule = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == category_id).first()
        if not rule: return f"Note: No budget rule for '{category_id}'."
        target_month = date[:7] if date else datetime.now().strftime("%Y-%m")
        total_spent = db.query(func.sum(TransactionModel.amount)).filter(
            TransactionModel.category_id == category_id,
            TransactionModel.date.like(f"{target_month}%")
        ).scalar() or 0.0
        remaining = rule.monthly_cap - total_spent
        pct = (total_spent / rule.monthly_cap) * 100
        status = "OK"
        if pct >= rule.alert_threshold_pct: status = "WARNING"
        if pct >= 100: status = "OVER BUDGET"
        return f"Budget {category_id} ({target_month}): {total_spent}/{rule.monthly_cap} MAD used ({pct:.1f}%). Status: {status}."
    finally:
        db.close()

class CreateTransactionSchema(BaseModel):
    account_slug: str
    amount: float
    date: str
    merchant: str
    category_id: str
    paid_by: str
    note: str = ""

@tool(args_schema=CreateTransactionSchema)
def create_transaction(account_slug: str, amount: float, date: str, merchant: str, category_id: str, paid_by: str, note: str = "") -> str:
    """Record a transaction. amount: POSITIVE for expense, NEGATIVE for income."""
    db = SessionLocal()
    try:
        if not category_id.startswith("cat_"):
            return "Error: Invalid category_id. You MUST call 'categorize' tool first to get a valid ID starting with 'cat_'."
        
        account = db.query(AccountModel).filter(AccountModel.slug == account_slug).first()
        if not account: return f"Error: Account '{account_slug}' not found. Use 'main_current' as default."
        
        account.balance -= amount
        new_transaction = TransactionModel(
            account_slug=account_slug, user_id=paid_by, category_id=category_id,
            amount=amount, date=date, merchant=merchant, note=note
        )
        db.add(new_transaction)
        db.commit()
        return f"Success: Logged {amount} at {merchant}. New balance: {account.balance} {account.currency}."
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

class TranscribeAudioSchema(BaseModel):
    audio_file_path: str

@tool(args_schema=TranscribeAudioSchema)
def transcribe_audio(audio_file_path: str) -> str:
    """Voice to text transcript."""
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        with open(audio_file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3", file=audio_file, response_format="text"
            )
        return f"Transcript: {transcript.text}"
    except Exception as e:
        return f"Error: {str(e)}"

class ParseReceiptSchema(BaseModel):
    base64_image: str

@tool(args_schema=ParseReceiptSchema)
def parse_receipt_image(base64_image: str) -> str:
    """Extract receipt data to JSON."""
    try:
        vision_llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0)
        prompt = "Analyze receipt and return JSON: merchant, total_amount, currency, date (YYYY-MM-DD), category_guess, items. ONLY JSON."
        message = HumanMessage(content=[{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": base64_image}}])
        response = vision_llm.invoke([message])
        return response.content.replace("```json", "").replace("```", "").strip()
    except Exception as e:
        return f"Error: {str(e)}"
    
class TransferSchema(BaseModel):
    source_slug: str
    dest_slug: str
    amount: float

@tool(args_schema=TransferSchema)
def transfer(source_slug: str, dest_slug: str, amount: float) -> str:
    """Transfer money between accounts."""
    if amount <= 0: return "Error: Amount must be positive."
    db = SessionLocal()
    try:
        source = db.query(AccountModel).filter(AccountModel.slug == source_slug).first()
        dest = db.query(AccountModel).filter(AccountModel.slug == dest_slug).first()
        if not source or not dest: return "Error: Account not found."
        if source.balance < amount: return "Error: Insufficient funds."
        source.balance -= amount
        dest.balance += amount
        db.commit()
        return f"Success: Transferred {amount}. New balances -> {source.name}: {source.balance}, {dest.name}: {dest.balance}"
    except Exception as e:
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

data_tools = [create_transaction, transcribe_audio, categorize, check_budget, get_balances, list_recent_transactions, delete_transaction]
analyst_tools = [list_accounts, transfer, check_budget, get_balances, list_recent_transactions]
budget_tools = data_tools + analyst_tools