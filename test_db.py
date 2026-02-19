
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
database_url = os.getenv("DATABASE_URL")

print(f"Testing connection to: {database_url.split('@')[-1] if database_url and '@' in database_url else 'Unknown'}")

if not database_url:
    print("Error: DATABASE_URL not set in .env")
    sys.exit(1)

# Handle potential single quotes in the env file value
if database_url.startswith("'") and database_url.endswith("'"):
    database_url = database_url[1:-1]
if database_url.startswith('"') and database_url.endswith('"'):
    database_url = database_url[1:-1]

try:
    # Create engine
    engine = create_engine(database_url)
    
    # Connect
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("\n✅ Connection Successful!")
        print(f"Result: {result.fetchall()}")
        
except Exception as e:
    print("\n❌ Connection Failed!")
    print(f"Error: {str(e)}")
    sys.exit(1)
