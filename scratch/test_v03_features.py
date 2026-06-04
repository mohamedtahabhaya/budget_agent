import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Add the project directory to path so we can import from database and finance_tools
sys.path.append("/Users/mohamed-taha/Documents/budget_agent")
load_dotenv()
os.environ["DATABASE_URL"] = "sqlite:///test_budget.db"

from database import SessionLocal, Base, engine, WorkspaceModel, UserModel, AccountModel, CategoryModel, TransactionModel, BudgetRuleModel, NotificationModel, NotificationPreferenceModel, SavingsGoalModel
from finance_tools import (
    create_transaction, check_budget, get_notification_preferences, update_notification_preferences, list_notifications
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
        db.query(NotificationModel).delete()
        db.query(NotificationPreferenceModel).delete()
        db.query(SavingsGoalModel).delete()
        db.commit()
        
        # 1. Create Workspace
        ws = WorkspaceModel(id="ws_test", name="Test Workspace", split_rule="equal")
        db.add(ws)
        
        # 2. Create Users
        u1 = UserModel(id="user_mohamed", workspace_id="ws_test", name="Mohamed", role="owner", income_mad=15000.0)
        u2 = UserModel(id="user_taha", workspace_id="ws_test", name="Taha", role="member", income_mad=10000.0)
        db.add_all([u1, u2])
        
        # 3. Create Default Preferences
        p1 = NotificationPreferenceModel(user_id="user_mohamed")
        p2 = NotificationPreferenceModel(user_id="user_taha")
        db.add_all([p1, p2])
        
        # 4. Create Accounts
        a1 = AccountModel(workspace_id="ws_test", name="Mohamed Personal", slug="main_current", type="personal", owner_user_id="user_mohamed", currency="MAD", balance=5000.0)
        db.add(a1)
        
        # 5. Create Categories
        c1 = CategoryModel(id="cat_groceries", workspace_id="ws_test", name="Groceries", icon="🛒", kind="expense")
        db.add(c1)
        
        # 6. Create Groceries Budget limit (100 MAD)
        br = BudgetRuleModel(
            category_id="cat_groceries",
            scope_type="workspace",
            scope_id=None,
            monthly_cap=100.0,
            alert_threshold_pct=80.0
        )
        db.add(br)
        
        db.commit()
    print("Database setup complete.")

def test_notification_preferences_logic():
    print("\n--- Testing Notification Preferences & Conditional Alerts ---")
    
    # 1. Check default preferences
    print("Fetching default preferences...")
    res = get_notification_preferences.invoke({"user_id": "user_mohamed"})
    print(res)
    assert "Budget Alerts: Enabled" in res
    
    # 2. Disable budget alerts for Mohamed
    print("\nDisabling budget alerts for user_mohamed...")
    update_res = update_notification_preferences.invoke({
        "user_id": "user_mohamed",
        "budget_alerts_enabled": False
    })
    print(update_res)
    assert "Budget Alerts: Disabled" in update_res
    
    # Verify in DB
    with SessionLocal() as db:
        pref = db.query(NotificationPreferenceModel).filter(NotificationPreferenceModel.user_id == "user_mohamed").first()
        assert pref.budget_alerts_enabled == False, "Expected budget alerts to be disabled in DB"
        
    # 3. Log budget breach transaction.
    # Since alerts are disabled for Mohamed, NO notification should be written to the database!
    print("\nLogging 150 MAD groceries transaction (Limit is 100 MAD) while budget alerts are disabled...")
    tx_res = create_transaction.invoke({
        "account_slug": "main_current",
        "amount": 150.0,
        "date": date.today().strftime("%Y-%m-%d"),
        "merchant": "BIM Bread",
        "category_id": "cat_groceries",
        "paid_by": "user_mohamed"
    })
    print(tx_res)
    
    # Verify that notifications list is empty
    with SessionLocal() as db:
        notifs = db.query(NotificationModel).all()
        print(f"Notifications generated: {len(notifs)}")
        assert len(notifs) == 0, f"Expected 0 notification logs, got {len(notifs)}"
        
    # 4. Re-enable budget alerts for Mohamed
    print("\nRe-enabling budget alerts for user_mohamed...")
    update_notification_preferences.invoke({
        "user_id": "user_mohamed",
        "budget_alerts_enabled": True
    })
    
    # 5. Log another budget breach transaction.
    # This time, an alert SHOULD be written to the database!
    print("Logging another 150 MAD groceries transaction while budget alerts are enabled...")
    tx_res2 = create_transaction.invoke({
        "account_slug": "main_current",
        "amount": 150.0,
        "date": date.today().strftime("%Y-%m-%d"),
        "merchant": "BIM Bread 2",
        "category_id": "cat_groceries",
        "paid_by": "user_mohamed"
    })
    print(tx_res2)
    
    # Verify that a notification WAS generated
    with SessionLocal() as db:
        notifs = db.query(NotificationModel).all()
        print(f"Notifications generated: {len(notifs)}")
        assert len(notifs) >= 1, "Expected at least 1 notification warning written in DB"
        print(f"Notification details: {notifs[0].message}")
        assert "CRITICAL" in notifs[0].message
        
def test_preferences_api_endpoints():
    print("\n--- Testing Preferences API Endpoints ---")
    from fastapi.testclient import TestClient
    from api import app
    
    client = TestClient(app)
    
    # 1. GET preferences
    print("GET /preferences/user_mohamed...")
    response = client.get("/preferences/user_mohamed")
    assert response.status_code == 200
    json_data = response.json()
    print(json_data)
    assert json_data["user_id"] == "user_mohamed"
    assert json_data["budget_alerts_enabled"] == True
    
    # 2. POST preference update
    print("\nPOST /preferences/user_mohamed (disabling recurring_tx and csv_import)...")
    post_res = client.post("/preferences/user_mohamed", json={
        "recurring_tx_enabled": False,
        "csv_import_enabled": False
    })
    assert post_res.status_code == 200
    res_data = post_res.json()
    print(res_data)
    assert res_data["success"] == True
    assert res_data["preferences"]["recurring_tx_enabled"] == False
    assert res_data["preferences"]["csv_import_enabled"] == False
    assert res_data["preferences"]["budget_alerts_enabled"] == True
    
    # Verify GET preferences matches updated values
    get_res = client.get("/preferences/user_mohamed")
    get_data = get_res.json()
    assert get_data["recurring_tx_enabled"] == False
    assert get_data["csv_import_enabled"] == False
    
    # 3. Test invalid user preferences
    print("\nGET /preferences/invalid_user...")
    err_res = client.get("/preferences/invalid_user")
    assert err_res.status_code == 200
    assert "error" in err_res.json()
    print(err_res.json())

def test_savings_goals_management():
    print("\n--- Testing Savings Goal Deletion & Modification ---")
    from finance_tools import create_savings_goal, delete_savings_goal, update_savings_goal_properties, list_savings_goals
    
    # 1. Create a goal
    create_res = create_savings_goal.invoke({
        "workspace_id": "ws_test",
        "name": "North Travel",
        "target": 3000.0,
        "target_date": "2027-06-04",
        "category": "Travel"
    })
    print(create_res)
    assert "North Travel" in create_res
    
    # Verify in list
    goals_list = list_savings_goals.invoke({"workspace_id": "ws_test"})
    assert "North Travel" in goals_list
    
    # 2. Modify properties (target date to 2026-07-01)
    mod_res = update_savings_goal_properties.invoke({
        "workspace_id": "ws_test",
        "goal_name": "North Travel",
        "new_target_date": "2026-07-01"
    })
    print(mod_res)
    assert "2026-07-01" in mod_res
    
    # Verify in DB
    with SessionLocal() as db:
        g = db.query(SavingsGoalModel).filter(SavingsGoalModel.workspace_id == "ws_test", SavingsGoalModel.name == "North Travel").first()
        assert g.target_date == "2026-07-01", "Expected date to be updated to 2026-07-01"
        
    # 3. Delete the goal
    del_res = delete_savings_goal.invoke({
        "workspace_id": "ws_test",
        "goal_name": "North Travel"
    })
    print(del_res)
    assert "deleted" in del_res
    
    # Verify not in list
    goals_list_after = list_savings_goals.invoke({"workspace_id": "ws_test"})
    assert "North Travel" not in goals_list_after

if __name__ == "__main__":
    setup_test_db()
    test_notification_preferences_logic()
    test_preferences_api_endpoints()
    test_savings_goals_management()
    print("\nAll v0.3 preference and savings goal management tests completed successfully!")
