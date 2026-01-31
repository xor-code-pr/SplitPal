"""
Balances Router - Balance calculation endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from decimal import Decimal
import logging

from app.database import get_db
from app.models import User, GroupMember, Transaction, Split
from app.schemas import BalancesResponse, BalanceResponse
from app.dependencies import get_current_user, verify_group_membership

router = APIRouter()
logger = logging.getLogger(__name__)

CENT = Decimal("0.01")


async def compute_group_balances(db: AsyncSession, group_id: int):
    """Compute balances for all members in a group"""
    # Get all members
    result = await db.execute(
        select(GroupMember.user_id, User.name)
        .join(User, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    members = result.all()
    member_ids = {row[0] for row in members}
    id_to_name = {row[0]: row[1] for row in members}
    
    balances = {uid: Decimal("0.00") for uid in member_ids}
    
    # Get all transactions for this group
    result = await db.execute(
        select(Transaction).where(Transaction.group_id == group_id)
    )
    transactions = result.scalars().all()
    
    # Add amounts paid
    for txn in transactions:
        if txn.payer_user_id is not None:
            amount = Decimal(str(txn.amount)).quantize(CENT)
            balances.setdefault(txn.payer_user_id, Decimal("0.00"))
            balances[txn.payer_user_id] += amount
    
    # Subtract amounts owed (splits)
    result = await db.execute(
        select(Split)
        .join(Transaction, Split.transaction_id == Transaction.id)
        .where(Transaction.group_id == group_id)
    )
    splits = result.scalars().all()
    
    for split in splits:
        share = Decimal(str(split.share_amount)).quantize(CENT)
        balances.setdefault(split.user_id, Decimal("0.00"))
        balances[split.user_id] -= share
    
    # Balance adjustment for rounding errors
    total_balance = sum(balances.values())
    if total_balance != Decimal("0.00") and abs(total_balance) <= CENT and balances:
        first_key = next(iter(balances))
        balances[first_key] = (balances[first_key] - total_balance).quantize(CENT)
    
    return balances, id_to_name


@router.get("/groups/{group_id}/balances", response_model=BalancesResponse)
async def get_group_balances(
    group_id: int = Path(..., description="Group ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get balances for all members in a group
    """
    # Verify group membership
    is_member = await verify_group_membership(group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    balances, id_to_name = await compute_group_balances(db, group_id)
    
    balance_list = [
        BalanceResponse(
            user_id=uid,
            user_name=id_to_name.get(uid, "Unknown"),
            balance=balance
        )
        for uid, balance in balances.items()
    ]
    
    logger.info(f"User {current_user.id} fetched balances for group {group_id}")
    
    return BalancesResponse(
        group_id=group_id,
        balances=balance_list
    )
