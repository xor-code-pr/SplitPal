"""
Pydantic Schemas for Request/Response Validation
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ==================== User Schemas ====================
class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_admin: bool = False

    class Config:
        from_attributes = True


class UserLookup(BaseModel):
    email: str


# ==================== Auth Schemas ====================
class TokenResponse(BaseModel):
    user: UserResponse
    token: str
    token_expires_in: int
    refresh_token: str
    refresh_expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ==================== Group Schemas ====================
class GroupMemberResponse(BaseModel):
    user_id: int
    user_name: str
    role: str
    is_admin: bool
    joined_at: Optional[datetime]

    class Config:
        from_attributes = True


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1)


class GroupJoin(BaseModel):
    invite_code: str


class GroupResponse(BaseModel):
    group_id: int
    group_name: str
    created_by_id: Optional[int]
    created_by_name: Optional[str]
    members: List[GroupMemberResponse] = []


# ==================== Transaction Schemas ====================
class SplitBase(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    share_amount: Optional[Decimal] = None
    share_percent: Optional[Decimal] = None

    @validator('share_amount', 'share_percent', pre=True)
    def validate_decimal(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class SplitCreate(SplitBase):
    pass


class SplitResponse(BaseModel):
    user_id: int
    user_name: str
    share_amount: Decimal
    share_percent: Optional[Decimal]
    settled: bool

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    group_id: int
    title: Optional[str] = None
    amount: Decimal
    currency: str = "INR"
    payer_user_id: Optional[int] = None
    payer_user_name: Optional[str] = None
    note: Optional[str] = ""
    splits: List[SplitCreate]

    @validator('amount', pre=True)
    def validate_amount(cls, v):
        return Decimal(str(v))


class TransactionUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payer_user_id: Optional[int] = None
    note: Optional[str] = None
    splits: Optional[List[SplitCreate]] = None

    @validator('amount', pre=True)
    def validate_amount(cls, v):
        if v is not None:
            return Decimal(str(v))
        return v


class TransactionResponse(BaseModel):
    transaction_id: int
    group_id: int
    title: Optional[str]
    amount: Decimal
    currency: str
    payer_user_id: int
    payer_user_name: str
    note: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    splits: List[SplitResponse]

    class Config:
        from_attributes = True


# ==================== Balance Schemas ====================
class BalanceResponse(BaseModel):
    user_id: int
    user_name: str
    balance: Decimal


class BalancesResponse(BaseModel):
    group_id: int
    balances: List[BalanceResponse]


# ==================== History Schemas ====================
class HistoryEntry(BaseModel):
    id: int
    transaction_id: int
    group_id: int
    action: str
    data: Optional[str]
    actor_user_id: Optional[int]
    actor_user_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Admin Schemas ====================
class AdminUserResponse(BaseModel):
    id: int
    name: str
    email: str
    global_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminGroupResponse(BaseModel):
    id: int
    name: str
    created_by: Optional[int]
    created_by_name: Optional[str]
    member_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Generic Schemas ====================
class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
