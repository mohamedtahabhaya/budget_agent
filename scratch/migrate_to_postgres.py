import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, make_transient

# Add project root directory to path so we can import from database
sys.path.append("/Users/mohamed-taha/Documents/budget_agent")

from database import (
    Base,
    WorkspaceModel,
    UserModel,
    AccountModel,
    CategoryModel,
    BudgetRuleModel,
    TransactionModel,
    SavingsGoalModel,
    ContributionModel,
    SplitRuleModel,
    RecurringTransactionModel,
    NotificationModel,
    InvitationModel,
    NotificationPreferenceModel
)

# Configuration
SQLITE_URL = "sqlite:///budget.db"
# Postgres URL matching the docker-compose setup
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5433/budget_db")


def migrate():
    print(f"Connecting to SQLite: {SQLITE_URL}")
    sqlite_engine = create_engine(SQLITE_URL)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SqliteSession()

    print(f"Connecting to PostgreSQL: {POSTGRES_URL}")
    postgres_engine = create_engine(POSTGRES_URL)
    PostgresSession = sessionmaker(bind=postgres_engine)
    postgres_session = PostgresSession()

    # Drop existing tables on PostgreSQL to ensure a clean slate, then recreate them
    print("Dropping existing tables on PostgreSQL...")
    Base.metadata.drop_all(bind=postgres_engine)
    print("Recreating database schema on PostgreSQL...")
    Base.metadata.create_all(bind=postgres_engine)

    # Tables in order of foreign key dependencies
    models = [
        WorkspaceModel,
        UserModel,
        AccountModel,
        CategoryModel,
        BudgetRuleModel,
        TransactionModel,
        SavingsGoalModel,
        ContributionModel,
        SplitRuleModel,
        RecurringTransactionModel,
        NotificationModel,
        InvitationModel,
        NotificationPreferenceModel
    ]

    print("\nMigrating data table by table...")
    try:
        for model in models:
            table_name = model.__tablename__
            records = sqlite_session.query(model).all()
            print(f"- Table '{table_name}': Found {len(records)} records in SQLite.")
            
            for record in records:
                # Expunge from SQLite session and make transient to insert into PostgreSQL session
                sqlite_session.expunge(record)
                make_transient(record)
                postgres_session.add(record)
                
            postgres_session.commit()
            print(f"  Successfully inserted {len(records)} records into PostgreSQL '{table_name}'.")

        # Reset sequences in PostgreSQL for tables with integer primary keys
        tables_with_sequences = [
            "accounts",
            "budget_rules",
            "transactions",
            "savings_goals",
            "contributions",
            "split_rules",
            "recurring_transactions",
            "notifications",
            "invitations",
            "notification_preferences"
        ]

        print("\nResetting PostgreSQL sequence counters...")
        for table in tables_with_sequences:
            # Check if there are any records to get max id, otherwise default to 1
            res = postgres_session.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}"))
            max_id = res.scalar()
            
            if max_id > 0:
                seq_query = f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), {max_id})"
                postgres_session.execute(text(seq_query))
                print(f"  Reset sequence for '{table}' to {max_id}")
            else:
                print(f"  No records in '{table}', sequence left at default start.")
        
        postgres_session.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        postgres_session.rollback()
        print(f"\nError during migration: {str(e)}")
        sys.exit(1)
    finally:
        sqlite_session.close()
        postgres_session.close()

if __name__ == "__main__":
    migrate()
