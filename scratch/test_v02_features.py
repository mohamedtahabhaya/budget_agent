import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Add the project directory to path so we can import from database and finance_tools
sys.path.append("/Users/mohamed-taha/Documents/budget_agent")
load_dotenv()
os.environ["DATABASE_URL"] = "sqlite:///test_budget.db"

from database import SessionLocal, Base, engine, WorkspaceModel, UserModel, AccountModel, CategoryModel, TransactionModel, BudgetRuleModel, SplitRuleModel, RecurringTransactionModel, NotificationModel, InvitationModel, NotificationPreferenceModel
from finance_tools import (
    create_transaction, check_budget, compute_split, transfer, 
    generate_report, list_recent_transactions, create_recurring_transaction,
    list_recurring_transactions, process_recurring_transactions,
    import_bank_csv, list_notifications, create_workspace_invite, list_invitations
)

def setup_test_db():
    print("Clearing test database...")
    with SessionLocal() as db:
        db.query(TransactionModel).delete()
        db.query(BudgetRuleModel).delete()
        db.query(AccountModel).delete()
        db.query(UserModel).delete()
        db.query(WorkspaceModel).delete()
        db.query(CategoryModel).delete()
        db.query(SplitRuleModel).delete()
        db.query(RecurringTransactionModel).delete()
        db.query(NotificationModel).delete()
        db.query(InvitationModel).delete()
        db.query(NotificationPreferenceModel).delete()
        db.commit()
        
        # 1. Create Workspace
        ws = WorkspaceModel(id="ws_test", name="Test Workspace", split_rule="equal")
        db.add(ws)
        
        # 2. Create Users
        u1 = UserModel(id="user_mohamed", workspace_id="ws_test", name="Mohamed", role="owner", income_mad=15000.0)
        u2 = UserModel(id="user_taha", workspace_id="ws_test", name="Taha", role="member", income_mad=10000.0)
        db.add_all([u1, u2])
        
        # 3. Create Accounts
        a1 = AccountModel(workspace_id="ws_test", name="Mohamed Personal", slug="main_current", type="personal", owner_user_id="user_mohamed", currency="MAD", balance=5000.0)
        a2 = AccountModel(workspace_id="ws_test", name="Taha Personal", slug="taha_personal", type="personal", owner_user_id="user_taha", currency="MAD", balance=5000.0)
        db.add_all([a1, a2])
        
        # 4. Create Categories
        c1 = CategoryModel(id="cat_groceries", workspace_id="ws_test", name="Groceries", icon="🛒", kind="expense")
        c2 = CategoryModel(id="cat_utilities", workspace_id="ws_test", name="Utilities", icon="⚡", kind="expense")
        c3 = CategoryModel(id="cat_dining", workspace_id="ws_test", name="Dining", icon="🍽️", kind="expense")
        c4 = CategoryModel(id="cat_income", workspace_id="ws_test", name="Income", icon="💵", kind="income")
        c5 = CategoryModel(id="cat_leisure", workspace_id="ws_test", name="Leisure", icon="🛍️", kind="expense")
        db.add_all([c1, c2, c3, c4, c5])
        
        db.commit()
    print("Database setup complete.")

def test_recurring_transactions():
    print("\n--- Testing Recurring Transactions ---")
    
    # 1. Schedule a monthly Netflix subscription starting 2026-05-01 (should trigger twice: 2026-05-01 and 2026-06-01 since today is 2026-06-01)
    print("Scheduling monthly Netflix recurring transaction...")
    res = create_recurring_transaction.invoke({
        "workspace_id": "ws_test",
        "name": "Netflix Monthly",
        "amount": 95.0,
        "category_id": "cat_leisure",
        "account_slug": "main_current",
        "frequency": "monthly",
        "start_date": "2026-05-01"
    })
    print(res)
    
    # 2. List recurring transactions
    print("\nListing recurring transactions:")
    list_res = list_recurring_transactions.invoke({"workspace_id": "ws_test"})
    print(list_res)
    
    # 3. Process recurring transactions
    print("\nProcessing recurring transactions...")
    proc_res = process_recurring_transactions.invoke({"workspace_id": "ws_test"})
    print(proc_res)
    
    # 4. Assertions in DB
    with SessionLocal() as db:
        # Check that two transactions were created
        txs = db.query(TransactionModel).all()
        print(f"Total transactions generated: {len(txs)}")
        for tx in txs:
            print(f"  * {tx.date} | {tx.merchant} | {tx.amount} MAD | {tx.note}")
        assert len(txs) == 2, f"Expected 2 transactions, got {len(txs)}"
        
        # Check next occurrence date is advanced to 2026-07-01
        rec = db.query(RecurringTransactionModel).filter(RecurringTransactionModel.name == "Netflix Monthly").first()
        print(f"Next occurrence date: {rec.next_occurrence_date}")
        assert rec.next_occurrence_date == "2026-07-01", f"Expected 2026-07-01, got {rec.next_occurrence_date}"
        rec_id = rec.id

    # 5. Delete recurring transaction
    print("\nDeleting recurring transaction...")
    from finance_tools import delete_recurring_transaction
    del_res = delete_recurring_transaction.invoke({"recurring_transaction_id": rec_id})
    print(del_res)

    with SessionLocal() as db:
        rec_deleted = db.query(RecurringTransactionModel).filter(RecurringTransactionModel.id == rec_id).first()
        assert rec_deleted is None, "Expected recurring transaction to be deleted"
        print("Success: Verified recurring transaction deletion.")

def test_csv_imports():
    print("\n--- Testing CSV Statement Imports ---")
    os.makedirs("scratch", exist_ok=True)
    
    # Create mock CSV files
    attijari_path = "scratch/test_attijariwafa.csv"
    bmce_path = "scratch/test_bmce.csv"
    sg_path = "scratch/test_sg.csv"
    
    # 1. Attijariwafa (semicolon, date d'opération, libellé, montant)
    # Note: negative amount = debit/expense (should become positive in DB), positive = credit/income (should become negative in DB)
    with open(attijari_path, "w", encoding="utf-8") as f:
        f.write("Date d'opération;Libellé;Montant\n")
        f.write("15/05/2026;BIM SUPERMARKET;-150,50\n")
        f.write("20/05/2026;SALARY;15000,00\n")
        
    # 2. BMCE (comma, Date, Description, Débit, Crédit)
    # Débit = expense (positive in csv, stored positive in DB), Crédit = income (positive in csv, stored negative in DB)
    with open(bmce_path, "w", encoding="utf-8") as f:
        f.write("Date,Description,Débit,Crédit\n")
        f.write("22/05/2026,GLOVO DINING,220.00,\n")
        f.write("25/05/2026,REFUND INCOME,,350.00\n")
        
    # 3. SG (semicolon, Date de valeur, Libellé de l'opération, Montant)
    with open(sg_path, "w", encoding="utf-8") as f:
        f.write("Date de valeur;Libellé de l'opération;Montant\n")
        f.write("28/05/2026;LYDEC UTILITY;-320,00\n")
        
    # Import Attijariwafa
    print("\nImporting Attijariwafa CSV...")
    attijari_res = import_bank_csv.invoke({
        "file_path": attijari_path,
        "account_slug": "main_current",
        "workspace_id": "ws_test",
        "bank_name": "Attijariwafa"
    })
    print(attijari_res)
    
    # Import BMCE
    print("\nImporting BMCE CSV...")
    bmce_res = import_bank_csv.invoke({
        "file_path": bmce_path,
        "account_slug": "taha_personal",
        "workspace_id": "ws_test",
        "bank_name": "BMCE"
    })
    print(bmce_res)
    
    # Import SG
    print("\nImporting SG CSV...")
    sg_res = import_bank_csv.invoke({
        "file_path": sg_path,
        "account_slug": "main_current",
        "workspace_id": "ws_test",
        "bank_name": "SG"
    })
    print(sg_res)
    
    # Assertions
    with SessionLocal() as db:
        # Check balances
        mohamed_acc = db.query(AccountModel).filter(AccountModel.slug == "main_current").first()
        taha_acc = db.query(AccountModel).filter(AccountModel.slug == "taha_personal").first()
        
        print(f"Mohamed Personal Account Balance: {mohamed_acc.balance} MAD")
        print(f"Taha Personal Account Balance: {taha_acc.balance} MAD")
        
        # Mohamed balance updates:
        # Initial: 5000 MAD
        # Recurring Netflix: -95 * 2 = -190 MAD (5000 - 190 = 4810)
        # Attijari BIM: -150.50 (debit/expense is positive in DB, subtracted from balance: 4810 - 150.50 = 4659.50)
        # Attijari Salary: -(-15000.00) = +15000.00 (income is negative in DB, added to balance: 4659.50 + 15000 = 19659.50)
        # SG Lydec: -320.00 (debit/expense is positive in DB, subtracted from balance: 19659.50 - 320 = 19339.50)
        # Assert within delta
        assert abs(mohamed_acc.balance - 19339.50) < 0.01, f"Expected 19339.50, got {mohamed_acc.balance}"
        
        # Taha balance updates:
        # Initial: 5000 MAD
        # BMCE Glovo: -220.00 (debit/expense is positive in DB, subtracted: 5000 - 220 = 4780)
        # BMCE Refund: -(-350.00) = +350.00 (credit/income is negative in DB, added: 4780 + 350 = 5130)
        assert abs(taha_acc.balance - 5130.00) < 0.01, f"Expected 5130.00, got {taha_acc.balance}"
        
        # Verify categorizations
        # BIM -> cat_groceries
        # SALARY -> cat_income
        # GLOVO -> cat_dining
        # LYDEC -> cat_utilities
        tx_bim = db.query(TransactionModel).filter(TransactionModel.merchant.like("%BIM%")).first()
        print(f"BIM category: {tx_bim.category_id}")
        assert tx_bim.category_id == "cat_groceries"
        
        tx_salary = db.query(TransactionModel).filter(TransactionModel.merchant.like("%SALARY%")).first()
        print(f"Salary category: {tx_salary.category_id}")
        assert tx_salary.category_id == "cat_income"
        
        tx_glovo = db.query(TransactionModel).filter(TransactionModel.merchant.like("%GLOVO%")).first()
        print(f"Glovo category: {tx_glovo.category_id}")
        assert tx_glovo.category_id == "cat_dining"
        
        tx_lydec = db.query(TransactionModel).filter(TransactionModel.merchant.like("%LYDEC%")).first()
        print(f"Lydec category: {tx_lydec.category_id}")
        assert tx_lydec.category_id == "cat_utilities"
        
    # Clean up mock CSVs
    os.remove(attijari_path)
    os.remove(bmce_path)
    os.remove(sg_path)

def test_notifications():
    print("\n--- Testing Notifications & Warnings ---")
    
    # 1. Setup a budget rule for groceries with monthly_cap of 100 MAD
    with SessionLocal() as db:
        br = BudgetRuleModel(
            category_id="cat_groceries",
            scope_type="workspace",
            scope_id=None,
            monthly_cap=100.0,
            alert_threshold_pct=80.0
        )
        db.add(br)
        db.commit()
        
    # 2. Log transaction exceeding the budget rule (150 MAD)
    print("Logging groceries transaction of 150 MAD (exceeding monthly cap of 100)...")
    res = create_transaction.invoke({
        "account_slug": "main_current",
        "amount": 150.0,
        "date": date.today().strftime("%Y-%m-%d"),
        "merchant": "BIM Budget Breach",
        "category_id": "cat_groceries",
        "paid_by": "user_mohamed"
    })
    print(res)
    
    # 3. Check notifications
    print("\nListing notifications:")
    notifs_res = list_notifications.invoke({"workspace_id": "ws_test", "limit": 5})
    print(notifs_res)
    
    # 4. Assertion in DB
    with SessionLocal() as db:
        notifs = db.query(NotificationModel).filter(NotificationModel.workspace_id == "ws_test").all()
        print(f"Notifications count: {len(notifs)}")
        for n in notifs:
            print(f"  * {n.timestamp} | {n.message} | read={n.is_read}")
        assert len(notifs) >= 1, "Expected at least 1 notification generated"
        assert "CRITICAL" in notifs[0].message, f"Expected CRITICAL warning, got {notifs[0].message}"
        assert notifs[0].is_read == True, "Expected notification to be marked as read after listing"

def test_workspace_invitations():
    print("\n--- Testing Workspace Invitations & Acceptance Flow ---")
    
    # 1. Create a workspace invitation
    print("Creating invitation for a new member...")
    res = create_workspace_invite.invoke({
        "workspace_id": "ws_test",
        "email": "nabil@example.com",
        "name": "Nabil",
        "role": "member",
        "income_mad": 12000.0
    })
    print(res)
    assert "Success:" in res, "Failed to create invitation"
    
    # 2. Verify invitation created in DB and fetch token
    with SessionLocal() as db:
        invite = db.query(InvitationModel).filter(InvitationModel.email == "nabil@example.com").first()
        assert invite is not None, "Invitation not found in DB"
        assert invite.is_accepted == False, "Invitation should be pending"
        token = invite.token
        print(f"Verified invitation in DB. Token is: {token}")
        
    # 3. List invitations tool
    print("\nListing invitations:")
    list_res = list_invitations.invoke({"workspace_id": "ws_test"})
    print(list_res)
    assert "Nabil" in list_res, "List invitations should contain invited user name"
    assert "Pending" in list_res, "Invitation should be shown as pending"
    
    # 4. Simulate acceptance via FastAPI TestClient
    from fastapi.testclient import TestClient
    from api import app
    
    client = TestClient(app)
    
    print("\nSimulating accept invitation request...")
    response = client.get(f"/invite/accept?token={token}")
    assert response.status_code == 200, f"Expected status 200, got {response.status_code}"
    assert "Congratulations" in response.text, "Acceptance response should render confirmation HTML"
    print("Accepted invitation successfully.")
    
    # 5. Verify database changes
    with SessionLocal() as db:
        invite = db.query(InvitationModel).filter(InvitationModel.token == token).first()
        assert invite.is_accepted == True, "Invitation status should be updated to accepted"
        
        new_user = db.query(UserModel).filter(UserModel.email == "nabil@example.com").first()
        assert new_user is not None, "New user should be registered in DB"
        assert new_user.name == "Nabil", f"Expected name 'Nabil', got {new_user.name}"
        assert new_user.workspace_id == "ws_test", "New user should be linked to ws_test workspace"
        assert new_user.role == "member", f"Expected role 'member', got {new_user.role}"
        assert new_user.income_mad == 12000.0, f"Expected income 12000.0, got {new_user.income_mad}"
        print(f"Verified new user successfully added to DB with ID: {new_user.id}")
        
    # 6. Test already accepted invitation
    print("\nSimulating duplicate accept invitation request...")
    dup_response = client.get(f"/invite/accept?token={token}")
    assert dup_response.status_code == 200
    assert "Already a Member" in dup_response.text, "Should display already a member screen"
    
    # 7. Test invalid token
    print("\nSimulating invalid token acceptance...")
    err_response = client.get("/invite/accept?token=invalid_token_xyz")
    assert err_response.status_code == 404
    assert "Not Found" in err_response.text, "Should display not found screen"
    print("All invitation tests passed successfully!")

if __name__ == "__main__":
    setup_test_db()
    test_recurring_transactions()
    test_csv_imports()
    test_notifications()
    test_workspace_invitations()
    print("\nAll tests completed successfully!")
