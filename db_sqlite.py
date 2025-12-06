import os
import sqlite3
import decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

DB_PATH = os.environ.get("SQLITE_DB_PATH", "./data/app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

sqlite3.register_adapter(decimal.Decimal, lambda d: format(d, "f"))

engine = create_engine(
	DATABASE_URL,
	connect_args={
		"check_same_thread": False,
	},
	pool_pre_ping=True,
)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
