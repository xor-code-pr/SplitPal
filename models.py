from sqlalchemy import Column, Integer, Text, Boolean, TIMESTAMP, ForeignKey, func
from sqlalchemy.types import TypeDecorator
import decimal


class SqliteDecimal(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, decimal.Decimal):
            value = decimal.Decimal(str(value))
        return format(value, "f")

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decimal.Decimal(value)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False, unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    global_admin = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(Text, nullable=False, default="member")
    joined_at = Column(TIMESTAMP, server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    title = Column(Text)
    amount = Column(SqliteDecimal, nullable=False)
    currency = Column(Text, nullable=False, default="INR")
    payer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    note = Column(Text)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Split(Base):
    __tablename__ = "splits"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_amount = Column(SqliteDecimal, nullable=False)
    share_percent = Column(SqliteDecimal)
    settled = Column(Boolean, default=False)

class TransactionHistory(Base):
    __tablename__ = "transaction_history"
    id = Column(Integer, primary_key=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    action = Column(Text, nullable=False)
    data = Column(Text)
    actor_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP, server_default=func.now())

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(Text, nullable=False, unique=True)
    expires_at = Column(TIMESTAMP, nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
