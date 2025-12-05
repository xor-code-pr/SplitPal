import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User
from auth_utils import hash_password

DB_PATH = os.environ.get("SQLITE_DB_PATH", "./data/app.db")
RESET_FLAG = os.environ.get("FORCE_RESET", "0").lower() in ("1", "true", "yes")

dirpath = os.path.dirname(DB_PATH)
if dirpath and not os.path.exists(dirpath):
    os.makedirs(dirpath, exist_ok=True)

# Optional full reset: delete existing SQLite file when FORCE_RESET is truthy
if RESET_FLAG and os.path.exists(DB_PATH):
    try:
        os.remove(DB_PATH)
        print(f"Existing DB {DB_PATH} removed due to FORCE_RESET")
    except Exception as e:
        print(f"FORCE_RESET enabled but failed to remove DB: {e}")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
s = Session()

# Lightweight migration: ensure 'global_admin' column exists (covers non-reset scenario)
try:
    cols = [row[1] for row in s.execute("PRAGMA table_info(users)").fetchall()]
    if "global_admin" not in cols:
        s.execute("ALTER TABLE users ADD COLUMN global_admin INTEGER DEFAULT 0")
        s.commit()
except Exception:
    pass

# Migration: ensure transactions.created_by exists and backfill with payer_user_id when missing
try:
    tx_cols = [row[1] for row in s.execute("PRAGMA table_info(transactions)").fetchall()]
    if "created_by" not in tx_cols:
        s.execute("ALTER TABLE transactions ADD COLUMN created_by INTEGER")
        s.execute("UPDATE transactions SET created_by = payer_user_id WHERE created_by IS NULL")
        s.commit()
except Exception:
    pass

# Minimal seed: only ensure global admin user exists
admin_email = "puru.2008@gmail.com"
admin = s.query(User).filter(User.email == admin_email).first()
if not admin:
    initial_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "adminpwd")
    admin = User(name="Purnendu", email=admin_email, password_hash=hash_password(initial_password), global_admin=True)
    s.add(admin)
    s.commit()
    print("Seeded global admin user 'Purnendu'")
else:
    # Ensure flag remains set (handles pre-existing record without flag)
    if not admin.global_admin:
        admin.global_admin = True
        s.commit()
        print("Updated existing admin user to have global_admin=True")

print("DB initialized at", DB_PATH)
