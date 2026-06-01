from sqlalchemy import create_engine, Column, String, Float, Integer, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///budget.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class WorkspaceModel(Base):
    __tablename__ = "workspaces"
    id = Column(String, primary_key=True)
    name = Column(String)
    currency = Column(String, default="MAD")
    split_rule = Column(String, default="equal")

class UserModel(Base): 
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"))
    name = Column(String)
    role = Column(String)
    email = Column(String)
    income_mad = Column(Float, default=0.0)

class AccountModel(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String, index=True)
    name = Column(String)
    slug = Column(String, unique=True, index=True)
    type = Column(String)
    owner_user_id = Column(String, nullable=True)
    currency = Column(String, default="MAD")
    balance = Column(Float, default=0.0)

    transactions = relationship("TransactionModel", back_populates="account")

class CategoryModel(Base):
    __tablename__ = "categories"
    
    id = Column(String, primary_key=True, index=True)
    workspace_id = Column(String, index=True)
    name = Column(String)
    icon = Column(String)
    kind = Column(String)
    parent_id = Column(String, nullable=True)

class BudgetRuleModel(Base):
    __tablename__ = "budget_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(String, ForeignKey("categories.id"))
    scope_type = Column(String)
    scope_id = Column(String, nullable=True)
    monthly_cap = Column(Float)
    alert_threshold_pct = Column(Float)

class TransactionModel(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"))
    category_id = Column(String)
    amount = Column(Float) 
    date = Column(String)
    merchant = Column(String)
    note = Column(String, default="")
    is_shared = Column(Boolean, default=False)

    account = relationship("AccountModel", back_populates="transactions")

class SavingsGoalModel(Base):
    __tablename__ = "savings_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String, index=True)
    name = Column(String)
    category = Column(String)
    target = Column(Float)
    current = Column(Float, default=0.0)
    target_date = Column(String)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

class ContributionModel(Base):
    __tablename__ = "contributions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float)

class SplitRuleModel(Base):
    __tablename__ = "split_rules"
    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"), unique=True)
    member_percentages = Column(String)

Base.metadata.create_all(bind=engine)

def seed_database():
    with SessionLocal() as db:
        ws_id = "workspace_coloc_taha_mohamed"
        if db.query(WorkspaceModel).count() == 0:
            ws = WorkspaceModel(id=ws_id, name="Coloc Taha & Mohamed", split_rule="equal")
            db.add(ws)
            u1 = UserModel(id="user_mohamed", workspace_id=ws_id, name="Mohamed", role="owner", income_mad=15000.0)
            u2 = UserModel(id="user_taha", workspace_id=ws_id, name="Taha", role="member", income_mad=10000.0)
            db.add_all([u1, u2])
            
            import json
            coloc_split = SplitRuleModel(
                workspace_id=ws_id,
                member_percentages=json.dumps({"user_mohamed": 0.5, "user_taha": 0.5})
            )
            db.add(coloc_split)

        if db.query(AccountModel).count() == 0:
            mohamed_account = AccountModel(
                workspace_id=ws_id,
                name="Mohamed Personal",
                slug="main_current",
                type="personal",
                owner_user_id="user_mohamed",
                currency="MAD",
                balance=5000.0
            )
            taha_account = AccountModel(
                workspace_id=ws_id,
                name="Taha Personal",
                slug="taha_personal",
                type="personal",
                owner_user_id="user_taha",
                currency="MAD",
                balance=5000.0
            )
            savings_account = AccountModel(
                workspace_id=ws_id,
                name="Emergency Fund",
                slug="emergency_fund",
                type="shared_savings",
                owner_user_id="user_mohamed",
                currency="MAD",
                balance=0.0
            )
            joint_account = AccountModel(
                workspace_id=ws_id, 
                name="Joint Account", 
                slug="joint_current", 
                type="shared_current", 
                owner_user_id=None, 
                balance=0.0
            )
            db.add_all([mohamed_account, taha_account, savings_account, joint_account])

        if db.query(CategoryModel).count() == 0:
            default_categories = [
                CategoryModel(id="cat_groceries", workspace_id=ws_id, name="Groceries", icon="🛒", kind="expense"),
                CategoryModel(id="cat_rent", workspace_id=ws_id, name="Rent", icon="🏠", kind="expense"),
                CategoryModel(id="cat_utilities", workspace_id=ws_id, name="Utilities", icon="⚡", kind="expense"),
                CategoryModel(id="cat_transport", workspace_id=ws_id, name="Transport", icon="🚗", kind="expense"),
                CategoryModel(id="cat_dining", workspace_id=ws_id, name="Dining out", icon="🍽️", kind="expense"),
                CategoryModel(id="cat_health", workspace_id=ws_id, name="Health", icon="💊", kind="expense"),
                CategoryModel(id="cat_personal", workspace_id=ws_id, name="Personal care", icon="💇", kind="expense"),
                CategoryModel(id="cat_leisure", workspace_id=ws_id, name="Leisure & shopping", icon="🛍️", kind="expense"),
                CategoryModel(id="cat_travel", workspace_id=ws_id, name="Travel", icon="✈️", kind="expense"),
                CategoryModel(id="cat_kids", workspace_id=ws_id, name="Kids & family", icon="🧸", kind="expense"),
                CategoryModel(id="cat_savings", workspace_id=ws_id, name="Savings transfer", icon="💰", kind="transfer"),
                CategoryModel(id="cat_income", workspace_id=ws_id, name="Income", icon="💵", kind="income")
            ]
            db.add_all(default_categories)

            demo_budget = BudgetRuleModel(
                category_id="cat_groceries",
                scope_type="workspace",
                scope_id=None,
                monthly_cap=2000.0,
                alert_threshold_pct=80.0
            )
            db.add(demo_budget)
        db.commit()

seed_database()