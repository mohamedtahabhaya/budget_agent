import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.append("/Users/mohamed-taha/Documents/budget_agent")
os.environ["DATABASE_URL"] = "sqlite:///test_budget.db"

from graph import graph
from database import SessionLocal, BudgetRuleModel

# 1. Clean test DB and make sure a groceries category exists
from database import CategoryModel, Base, engine
with SessionLocal() as db:
    # Ensure groceries category
    cat = db.query(CategoryModel).filter(CategoryModel.id == "cat_groceries").first()
    if not cat:
        cat = CategoryModel(id="cat_groceries", workspace_id="ws_test", name="Groceries", icon="🛒", kind="expense")
        db.add(cat)
    # Clear any old groceries budget cap
    db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == "cat_groceries").delete()
    db.commit()

input_data = {
    "messages": [("user", "Hello! Can you update my groceries budget limit (cap) to 3000 MAD for the workspace?")],
    "workspace_id": "ws_test",
    "user_id": "user_mohamed"
}
import uuid
config = {"configurable": {"thread_id": f"test_session_{uuid.uuid4()}"}}

print("=== Running Graph to update budget limit ===")
for state_update in graph.stream(input_data, config=config):
    for node, value in state_update.items():
        print(f"\n--- Node: {node} ---")
        if "messages" in value:
            for msg in value["messages"]:
                print(f"Message: {msg.content}")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    print(f"Tool calls: {msg.tool_calls}")

# Verify limit updated in DB
with SessionLocal() as db:
    rule = db.query(BudgetRuleModel).filter(BudgetRuleModel.category_id == "cat_groceries").first()
    if rule:
        print(f"\nVerification: Groceries monthly cap is {rule.monthly_cap} MAD (Scope: {rule.scope_type})")
        assert rule.monthly_cap == 3000.0
    else:
        print("\nVerification: No groceries budget cap found in DB!")
        assert False, "Groceries budget cap was not created!"
