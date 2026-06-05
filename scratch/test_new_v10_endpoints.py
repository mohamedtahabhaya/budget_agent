import os
import sys
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append("/Users/mohamed-taha/Documents/budget_agent")
os.environ["DATABASE_URL"] = "sqlite:///test_budget.db"

from api import app
from database import SessionLocal, Base, engine, CategoryModel, BudgetRuleModel, TransactionModel, AccountModel

client = TestClient(app)

def setup_db():
    print("Setting up test database for new endpoints...")
    # Clean and re-create tables
    with SessionLocal() as db:
        db.query(TransactionModel).delete()
        db.query(BudgetRuleModel).delete()
        db.query(CategoryModel).delete()
        db.query(AccountModel).delete()
        db.commit()
        
        # Seed categories
        c1 = CategoryModel(id="cat_groceries", workspace_id="workspace_coloc_taha_mohamed", name="Groceries", icon="🛒", kind="expense")
        c2 = CategoryModel(id="cat_leisure", workspace_id="workspace_coloc_taha_mohamed", name="Leisure", icon="🎮", kind="expense")
        db.add_all([c1, c2])
        
        # Seed account
        a = AccountModel(id=1, workspace_id="workspace_coloc_taha_mohamed", name="Mohamed Personal", slug="main_current", type="personal", balance=5000.0, currency="MAD")
        db.add(a)
        
        # Seed a transaction
        tx = TransactionModel(
            account_id=1,
            user_id="user_mohamed",
            category_id="cat_groceries",
            amount=150.0,
            date="2026-06-05",
            merchant="BIM Supermarket",
            is_shared=False
        )
        db.add(tx)
        
        db.commit()
    print("Setup complete.")

def test_budgets_endpoints():
    print("\n--- Testing GET & POST /budgets ---")
    
    # 1. GET budgets (should be empty caps)
    res = client.get("/budgets?workspace_id=workspace_coloc_taha_mohamed")
    print("GET /budgets (initial):", res.json())
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    groceries = next(x for x in data if x["category_id"] == "cat_groceries")
    assert groceries["monthly_cap"] == 0.0
    
    # 2. POST budget limit to 500 MAD
    post_res = client.post("/budgets", json={
        "category_id": "cat_groceries",
        "monthly_cap": 500.0,
        "scope_type": "workspace",
        "workspace_id": "workspace_coloc_taha_mohamed"
    })
    print("POST /budgets:", post_res.json())
    assert post_res.status_code == 200
    assert post_res.json()["success"] is True
    
    # Verify via GET
    res2 = client.get("/budgets?workspace_id=workspace_coloc_taha_mohamed")
    print("GET /budgets (after update):", res2.json())
    data2 = res2.json()
    groceries2 = next(x for x in data2 if x["category_id"] == "cat_groceries")
    assert groceries2["monthly_cap"] == 500.0
    
    # 3. Clear budget (set cap to 0)
    clear_res = client.post("/budgets", json={
        "category_id": "cat_groceries",
        "monthly_cap": 0.0,
        "workspace_id": "workspace_coloc_taha_mohamed"
    })
    print("POST /budgets (clear):", clear_res.json())
    assert clear_res.json()["success"] is True
    
    # Verify deleted
    res3 = client.get("/budgets?workspace_id=workspace_coloc_taha_mohamed")
    groceries3 = next(x for x in res3.json() if x["category_id"] == "cat_groceries")
    assert groceries3["monthly_cap"] == 0.0

def test_transactions_endpoint():
    print("\n--- Testing GET /transactions ---")
    res = client.get("/transactions?workspace_id=workspace_coloc_taha_mohamed")
    print("GET /transactions:", res.json())
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    tx = data[0]
    assert tx["merchant"] == "BIM Supermarket"
    assert tx["amount"] == 150.0
    assert tx["category_name"] == "Groceries"

if __name__ == "__main__":
    setup_db()
    test_budgets_endpoints()
    test_transactions_endpoint()
    print("\nAll new v1.0 endpoints tested successfully!")
