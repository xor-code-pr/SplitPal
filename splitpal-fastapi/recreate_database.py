"""
Recreate PostgreSQL database with CASCADE delete constraints

This script:
1. Drops the existing splitpal database
2. Creates a fresh database
3. Re-runs the migration with CASCADE constraints
"""

import asyncio
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

# Parse DATABASE_URL to get connection info
db_url = os.getenv('DATABASE_URL', '')
# Format: postgresql+asyncpg://user:pass@host:port/dbname
# Remove the +asyncpg part
db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

def recreate_database():
    """Drop and recreate the splitpal database"""
    
    # Connect to postgres database (not splitpal)
    conn = psycopg2.connect(
        dbname='postgres',
        user='postgres',
        password='password',
        host='localhost',
        port='5432'
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # Terminate existing connections
        print("Terminating existing connections to splitpal database...")
        cursor.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'splitpal'
              AND pid <> pg_backend_pid()
        """)
        print("✓ Connections terminated")
        
        # Drop existing database
        print("Dropping existing splitpal database...")
        cursor.execute("DROP DATABASE IF EXISTS splitpal")
        print("✓ Database dropped")
        
        # Create fresh database
        print("Creating fresh splitpal database...")
        cursor.execute("CREATE DATABASE splitpal")
        print("✓ Database created")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Recreate Database with CASCADE Constraints")
    print("=" * 60)
    
    recreate_database()
    
    print("\n✓ Database recreation complete!")
    print("\nNext step: Run the migration script")
    print("  python migrate_sqlite_to_postgres.py")
