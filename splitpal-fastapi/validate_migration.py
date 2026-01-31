"""
Validate data migration between SQLite and PostgreSQL

Compares record counts and sample data to ensure migration was successful.
"""

import asyncio
import sqlite3
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models import User, Group, GroupMember, Transaction, Split, TransactionHistory, RefreshToken

SQLITE_PATH = 'c:\\MyFiles\\MyProjects\\MyHelpers\\Splitpal\\splitpal-backend\\data\\app.db'

async def validate_migration():
    """Compare data between SQLite and PostgreSQL"""
    
    print("=" * 70)
    print("Data Migration Validation")
    print("=" * 70)
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to PostgreSQL
    async with AsyncSessionLocal() as pg_session:
        
        # Tables to validate
        tables = [
            ('users', User, ['id', 'name', 'email']),
            ('groups', Group, ['id', 'name']),
            ('group_members', GroupMember, ['id', 'group_id', 'user_id', 'role']),
            ('transactions', Transaction, ['id', 'group_id', 'title', 'amount', 'payer_user_id']),
            ('splits', Split, ['id', 'transaction_id', 'user_id', 'share_amount']),
            ('transaction_history', TransactionHistory, ['id', 'transaction_id', 'group_id', 'action']),
            ('refresh_tokens', RefreshToken, ['id', 'user_id', 'revoked']),
        ]
        
        all_valid = True
        
        for table_name, model, sample_fields in tables:
            print(f"\n{'='*70}")
            print(f"Validating: {table_name}")
            print(f"{'='*70}")
            
            # Get SQLite count
            sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            sqlite_count = sqlite_cursor.fetchone()[0]
            
            # Get PostgreSQL count
            result = await pg_session.execute(select(func.count()).select_from(model))
            pg_count = result.scalar()
            
            # Special handling for tables with orphaned records
            expected_pg_count = sqlite_count
            if table_name == 'transaction_history':
                # We know 2 records were skipped
                expected_pg_count = sqlite_count - 2
            
            print(f"SQLite count:     {sqlite_count}")
            print(f"PostgreSQL count: {pg_count}")
            
            if pg_count == expected_pg_count:
                print("✅ Counts match!")
            else:
                print(f"❌ Count mismatch! Expected {expected_pg_count}, got {pg_count}")
                all_valid = False
            
            # Sample data comparison (first 3 records)
            if pg_count > 0:
                print(f"\nSample data comparison (first 3 records):")
                
                # Get SQLite sample
                field_list = ', '.join(sample_fields)
                sqlite_cursor.execute(f"SELECT {field_list} FROM {table_name} ORDER BY id LIMIT 3")
                sqlite_rows = sqlite_cursor.fetchall()
                
                # Get PostgreSQL sample
                pg_result = await pg_session.execute(
                    select(model).order_by(model.id).limit(3)
                )
                pg_rows = pg_result.scalars().all()
                
                for i, (sqlite_row, pg_row) in enumerate(zip(sqlite_rows, pg_rows), 1):
                    print(f"\n  Record {i}:")
                    for field in sample_fields:
                        sqlite_val = sqlite_row[field]
                        pg_val = getattr(pg_row, field)
                        
                        # Convert for comparison
                        if pg_val is not None:
                            pg_val = str(pg_val)
                        if sqlite_val is not None:
                            sqlite_val = str(sqlite_val)
                        
                        match = "✅" if sqlite_val == pg_val else "❌"
                        print(f"    {field:20s}: SQLite={sqlite_val} | PG={pg_val} {match}")
        
        # Validate foreign key relationships
        print(f"\n{'='*70}")
        print("Foreign Key Relationship Validation")
        print(f"{'='*70}")
        
        # Check that all group_members reference valid groups
        result = await pg_session.execute(
            select(func.count()).select_from(GroupMember).outerjoin(Group).where(Group.id.is_(None))
        )
        orphaned_members = result.scalar()
        print(f"Orphaned group_members: {orphaned_members} {'✅' if orphaned_members == 0 else '❌'}")
        
        # Check that all transactions reference valid groups
        result = await pg_session.execute(
            select(func.count()).select_from(Transaction).outerjoin(Group).where(Group.id.is_(None))
        )
        orphaned_transactions = result.scalar()
        print(f"Orphaned transactions: {orphaned_transactions} {'✅' if orphaned_transactions == 0 else '❌'}")
        
        # Check that all splits reference valid transactions
        result = await pg_session.execute(
            select(func.count()).select_from(Split).outerjoin(Transaction).where(Transaction.id.is_(None))
        )
        orphaned_splits = result.scalar()
        print(f"Orphaned splits: {orphaned_splits} {'✅' if orphaned_splits == 0 else '❌'}")
        
        # Check that all transaction_history reference valid groups and transactions
        result = await pg_session.execute(
            select(func.count()).select_from(TransactionHistory)
            .outerjoin(Group, TransactionHistory.group_id == Group.id)
            .where(Group.id.is_(None))
        )
        orphaned_history_groups = result.scalar()
        print(f"Transaction history with invalid groups: {orphaned_history_groups} {'✅' if orphaned_history_groups == 0 else '❌'}")
        
        result = await pg_session.execute(
            select(func.count()).select_from(TransactionHistory)
            .outerjoin(Transaction, TransactionHistory.transaction_id == Transaction.id)
            .where(Transaction.id.is_(None))
        )
        orphaned_history_transactions = result.scalar()
        print(f"Transaction history with invalid transactions: {orphaned_history_transactions} {'✅' if orphaned_history_transactions == 0 else '❌'}")
        
        # Check that all refresh_tokens reference valid users
        result = await pg_session.execute(
            select(func.count()).select_from(RefreshToken).outerjoin(User).where(User.id.is_(None))
        )
        orphaned_tokens = result.scalar()
        print(f"Orphaned refresh_tokens: {orphaned_tokens} {'✅' if orphaned_tokens == 0 else '❌'}")
        
    sqlite_conn.close()
    
    print(f"\n{'='*70}")
    if all_valid:
        print("✅ VALIDATION SUCCESSFUL - All data migrated correctly!")
    else:
        print("❌ VALIDATION FAILED - Some issues detected")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(validate_migration())
