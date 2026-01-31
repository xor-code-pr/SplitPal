"""
SQLite to PostgreSQL Data Migration Script

This script migrates all data from the Azure Functions SQLite database 
to the FastAPI PostgreSQL database.

Usage:
1. Ensure PostgreSQL is running (via Docker or local installation)
2. Configure DATABASE_URL in .env file
3. Run: python migrate_sqlite_to_postgres.py
"""

import os
import sys
import sqlite3
import asyncio
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

# Import FastAPI models and database
from app.database import AsyncSessionLocal, engine as async_engine
from app.models import User, Group, GroupMember, Transaction, Split, TransactionHistory, RefreshToken, Base

# SQLite database path
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "../data/app.db")

# Resolve path relative to this script
script_dir = Path(__file__).parent
sqlite_path = (script_dir / SQLITE_DB_PATH).resolve()

print(f"SQLite database path: {sqlite_path}")
print(f"PostgreSQL connection: {os.getenv('DATABASE_URL', 'Not set')}")


async def create_tables():
    """Create all tables in PostgreSQL"""
    print("\n1. Creating PostgreSQL tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created successfully")


def get_sqlite_data():
    """Extract all data from SQLite database"""
    print(f"\n2. Reading data from SQLite ({sqlite_path})...")
    
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite database not found at: {sqlite_path}")
    
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row  # Access columns by name
    cursor = conn.cursor()
    
    data = {}
    
    # Read users
    cursor.execute("SELECT * FROM users ORDER BY id")
    data['users'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['users'])} users")
    
    # Read groups
    cursor.execute("SELECT * FROM groups ORDER BY id")
    data['groups'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['groups'])} groups")
    
    # Read group members
    cursor.execute("SELECT * FROM group_members ORDER BY id")
    data['group_members'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['group_members'])} group members")
    
    # Read transactions
    cursor.execute("SELECT * FROM transactions ORDER BY id")
    data['transactions'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['transactions'])} transactions")
    
    # Read splits
    cursor.execute("SELECT * FROM splits ORDER BY id")
    data['splits'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['splits'])} splits")
    
    # Read transaction history
    cursor.execute("SELECT * FROM transaction_history ORDER BY id")
    data['transaction_history'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['transaction_history'])} transaction history records")
    
    # Read refresh tokens
    cursor.execute("SELECT * FROM refresh_tokens ORDER BY id")
    data['refresh_tokens'] = [dict(row) for row in cursor.fetchall()]
    print(f"  Found {len(data['refresh_tokens'])} refresh tokens")
    
    conn.close()
    print("✓ Data extraction complete")
    
    return data


def convert_value(value, field_type):
    """Convert SQLite values to PostgreSQL-compatible types"""
    if value is None:
        return None
    
    # Convert numeric strings to Decimal
    if field_type == 'numeric':
        if isinstance(value, str):
            return Decimal(value)
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        return value
    
    # Convert timestamp strings to datetime
    if field_type == 'timestamp':
        if isinstance(value, str):
            # Handle various timestamp formats
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                try:
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except:
                    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
        return value
    
    # Convert boolean
    if field_type == 'boolean':
        if isinstance(value, (str, int)):
            return bool(int(value))
        return bool(value)
    
    return value


async def insert_data(data):
    """Insert data into PostgreSQL"""
    print("\n3. Inserting data into PostgreSQL...")
    
    async with AsyncSessionLocal() as session:
        try:
            # Insert users
            print("  Inserting users...")
            for row in data['users']:
                user = User(
                    id=row['id'],
                    name=row['name'],
                    email=row['email'],
                    password_hash=row['password_hash'],
                    global_admin=convert_value(row.get('global_admin', False), 'boolean'),
                    created_at=convert_value(row.get('created_at'), 'timestamp')
                )
                session.add(user)
            await session.flush()
            print(f"  ✓ Inserted {len(data['users'])} users")
            
            # Insert groups
            print("  Inserting groups...")
            for row in data['groups']:
                group = Group(
                    id=row['id'],
                    name=row['name'],
                    created_by=row.get('created_by'),
                    created_at=convert_value(row.get('created_at'), 'timestamp')
                )
                session.add(group)
            await session.flush()
            print(f"  ✓ Inserted {len(data['groups'])} groups")
            
            # Insert group members
            print("  Inserting group members...")
            for row in data['group_members']:
                member = GroupMember(
                    id=row['id'],
                    group_id=row['group_id'],
                    user_id=row['user_id'],
                    role=row.get('role', 'member'),
                    joined_at=convert_value(row.get('joined_at'), 'timestamp')
                )
                session.add(member)
            await session.flush()
            print(f"  ✓ Inserted {len(data['group_members'])} group members")
            
            # Insert transactions
            print("  Inserting transactions...")
            for row in data['transactions']:
                transaction = Transaction(
                    id=row['id'],
                    group_id=row['group_id'],
                    title=row.get('title'),
                    amount=convert_value(row['amount'], 'numeric'),
                    currency=row.get('currency', 'INR'),
                    payer_user_id=row['payer_user_id'],
                    note=row.get('note'),
                    created_by=row.get('created_by'),
                    created_at=convert_value(row.get('created_at'), 'timestamp'),
                    updated_at=convert_value(row.get('updated_at'), 'timestamp')
                )
                session.add(transaction)
            await session.flush()
            print(f"  ✓ Inserted {len(data['transactions'])} transactions")
            
            # Insert splits
            print("  Inserting splits...")
            for row in data['splits']:
                split = Split(
                    id=row['id'],
                    transaction_id=row['transaction_id'],
                    user_id=row['user_id'],
                    share_amount=convert_value(row['share_amount'], 'numeric'),
                    share_percent=convert_value(row.get('share_percent'), 'numeric'),
                    settled=convert_value(row.get('settled', False), 'boolean')
                )
                session.add(split)
            await session.flush()
            print(f"  ✓ Inserted {len(data['splits'])} splits")
            
            # Insert transaction history (skip records with invalid foreign keys)
            print("  Inserting transaction history...")
            valid_group_ids = {row['id'] for row in data['groups']}
            valid_transaction_ids = {row['id'] for row in data['transactions']}
            skipped_history = 0
            
            for row in data['transaction_history']:
                # Skip if references non-existent group or transaction
                if row['group_id'] not in valid_group_ids or row['transaction_id'] not in valid_transaction_ids:
                    skipped_history += 1
                    continue
                    
                history = TransactionHistory(
                    id=row['id'],
                    transaction_id=row['transaction_id'],
                    group_id=row['group_id'],
                    action=row['action'],
                    data=row.get('data'),
                    actor_user_id=row.get('actor_user_id'),
                    created_at=convert_value(row.get('created_at'), 'timestamp')
                )
                session.add(history)
            await session.flush()
            inserted_history = len(data['transaction_history']) - skipped_history
            print(f"  ✓ Inserted {inserted_history} transaction history records ({skipped_history} skipped due to invalid references)")
            
            # Insert refresh tokens (skip records with invalid user_ids)
            print("  Inserting refresh tokens...")
            valid_user_ids = {row['id'] for row in data['users']}
            skipped_tokens = 0
            
            for row in data['refresh_tokens']:
                # Skip if references non-existent user
                if row['user_id'] not in valid_user_ids:
                    skipped_tokens += 1
                    continue
                    
                token = RefreshToken(
                    id=row['id'],
                    user_id=row['user_id'],
                    token_hash=row['token_hash'],
                    expires_at=convert_value(row['expires_at'], 'timestamp'),
                    revoked=convert_value(row.get('revoked', False), 'boolean'),
                    created_at=convert_value(row.get('created_at'), 'timestamp')
                )
                session.add(token)
            await session.flush()
            inserted_tokens = len(data['refresh_tokens']) - skipped_tokens
            print(f"  ✓ Inserted {inserted_tokens} refresh tokens ({skipped_tokens} skipped due to invalid user references)")
            
            # Update sequences for auto-increment IDs
            print("\n  Updating ID sequences...")
            
            tables = [
                ('users', len(data['users'])),
                ('groups', len(data['groups'])),
                ('group_members', len(data['group_members'])),
                ('transactions', len(data['transactions'])),
                ('splits', len(data['splits'])),
                ('transaction_history', len(data['transaction_history'])),
                ('refresh_tokens', len(data['refresh_tokens']))
            ]
            
            for table_name, count in tables:
                if count > 0:
                    # Set sequence to max ID + 1
                    await session.execute(
                        text(f"SELECT setval('{table_name}_id_seq', (SELECT MAX(id) FROM {table_name}))")
                    )
            
            print("  ✓ Sequences updated")
            
            # Commit all changes
            await session.commit()
            print("\n✓ All data inserted successfully")
            
        except Exception as e:
            await session.rollback()
            print(f"\n✗ Error during insertion: {e}")
            raise


async def verify_migration():
    """Verify the migration was successful"""
    print("\n4. Verifying migration...")
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func
        
        tables = [
            (User, 'users'),
            (Group, 'groups'),
            (GroupMember, 'group_members'),
            (Transaction, 'transactions'),
            (Split, 'splits'),
            (TransactionHistory, 'transaction_history'),
            (RefreshToken, 'refresh_tokens')
        ]
        
        print("\nPostgreSQL record counts:")
        for model, name in tables:
            result = await session.execute(select(func.count()).select_from(model))
            count = result.scalar()
            print(f"  {name}: {count}")
    
    print("\n✓ Verification complete")


async def main():
    """Main migration process"""
    print("=" * 60)
    print("SQLite to PostgreSQL Migration")
    print("=" * 60)
    
    try:
        # Check if PostgreSQL connection is configured
        if not os.getenv('DATABASE_URL'):
            print("\n✗ ERROR: DATABASE_URL not set in .env file")
            print("Please configure your PostgreSQL connection and try again.")
            return
        
        # Step 1: Create tables
        await create_tables()
        
        # Step 2: Extract data from SQLite
        data = get_sqlite_data()
        
        # Step 3: Insert data into PostgreSQL
        await insert_data(data)
        
        # Step 4: Verify migration
        await verify_migration()
        
        print("\n" + "=" * 60)
        print("Migration completed successfully! 🎉")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Test the FastAPI application with the migrated data")
        print("2. Verify all functionality works as expected")
        print("3. Backup the SQLite database: copy data\\app.db data\\app.db.backup")
        
    except FileNotFoundError as e:
        print(f"\n✗ ERROR: {e}")
        print("\nPlease ensure the SQLite database exists at the specified path.")
    except Exception as e:
        print(f"\n✗ ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
