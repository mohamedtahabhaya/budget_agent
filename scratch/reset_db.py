import os
import sys
from dotenv import load_dotenv

# Add parent directory to path so we can import database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, engine, seed_database

print("⚠️ Warning: This will delete all transactions, accounts, and custom data.")
confirm = input("Are you sure you want to reset the database? (y/n): ")
if confirm.lower() != 'y':
    print("Cancelled.")
    sys.exit(0)

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)

print("Recreating tables...")
Base.metadata.create_all(bind=engine)

print("Seeding database with default accounts, users, and categories...")
seed_database()

print("✅ Database has been successfully reset and seeded!")
