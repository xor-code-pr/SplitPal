"""
Transactions Router - Transaction management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func as sa_func
from typing import List, Optional
from decimal import Decimal
import logging
import json

from app.database import get_db
from app.models import User, Group, GroupMember, Transaction, Split, TransactionHistory
from app.schemas import TransactionCreate, TransactionUpdate, TransactionResponse, SplitResponse, MessageResponse
from app.dependencies import get_current_user, verify_group_membership

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


async def get_member_name_mapping(db: AsyncSession, group_id: int):
    """Helper to get user name mapping for a group"""
    result = await db.execute(
        select(GroupMember.user_id, User.name)
        .join(User, GroupMember.user_id == User.id)
        .where(GroupMember.group_id == group_id)
    )
    rows = result.all()
    name_to_id = {name.strip().lower(): uid for uid, name in rows}
    id_to_name = {uid: name for uid, name in rows}
    group_member_ids = {uid for uid, _ in rows}
    return name_to_id, id_to_name, group_member_ids


@router.get("/groups/{group_id}/transactions", response_model=dict)
async def get_transactions(
    group_id: int = Path(..., description="Group ID"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get transactions for a group
    """
    # Verify group membership
    is_member = await verify_group_membership(group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Get total count
    count_result = await db.execute(
        select(sa_func.count(Transaction.id)).where(Transaction.group_id == group_id)
    )
    total_count = count_result.scalar() or 0
    
    # Get transactions
    result = await db.execute(
        select(Transaction)
        .where(Transaction.group_id == group_id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    transactions = result.scalars().all()
    
    if not transactions:
        return {
            "transactions": [],
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    
    # Get user name mappings
    _, id_to_name, _ = await get_member_name_mapping(db, group_id)
    
    # Get all splits for these transactions
    txn_ids = [t.id for t in transactions]
    result = await db.execute(
        select(Split).where(Split.transaction_id.in_(txn_ids))
    )
    all_splits = result.scalars().all()
    
    splits_by_txn = {}
    for split in all_splits:
        splits_by_txn.setdefault(split.transaction_id, []).append(
            SplitResponse(
                user_id=split.user_id,
                user_name=id_to_name.get(split.user_id, "Unknown"),
                share_amount=split.share_amount,
                share_percent=split.share_percent,
                settled=split.settled
            )
        )
    
    # Build response
    transactions_response = [
        TransactionResponse(
            transaction_id=t.id,
            group_id=t.group_id,
            title=t.title,
            amount=t.amount,
            currency=t.currency,
            payer_user_id=t.payer_user_id,
            payer_user_name=id_to_name.get(t.payer_user_id, "Unknown"),
            note=t.note,
            created_by=t.created_by,
            created_at=t.created_at,
            updated_at=t.updated_at,
            splits=splits_by_txn.get(t.id, [])
        )
        for t in transactions
    ]
    
    logger.info(f"User {current_user.id} fetched {len(transactions)} transactions for group {group_id}")
    
    return {
        "transactions": transactions_response,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }


@router.post("/groups/{group_id}/transactions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    group_id: int = Path(..., description="Group ID"),
    transaction_data: TransactionCreate = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new transaction
    """
    # Override group_id from path
    transaction_data.group_id = group_id
    
    # Verify group membership
    is_member = await verify_group_membership(group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Get member mappings
    name_to_id, id_to_name, group_member_ids = await get_member_name_mapping(db, group_id)
    
    # Determine payer
    payer_user_id = transaction_data.payer_user_id
    if payer_user_id is None:
        if not transaction_data.payer_user_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing payer information"
            )
        payer_user_id = name_to_id.get(transaction_data.payer_user_name.strip().lower())
        if not payer_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payer not found in group"
            )
    elif payer_user_id not in group_member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Payer not a member of this group"
        )
    
    # Validate splits
    cent = Decimal('0.01')
    tolerance = Decimal('0.01')
    amt = Decimal(str(transaction_data.amount)).quantize(cent)
    computed = Decimal('0.00')
    split_objs = []
    
    for s in transaction_data.splits:
        target_user_id = s.user_id
        if target_user_id is None:
            if not s.user_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each split must include user_id or user_name"
                )
            target_user_id = name_to_id.get(s.user_name.strip().lower())
            if not target_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Member {s.user_name} not found in group"
                )
        
        if s.share_amount is not None:
            sa = Decimal(str(s.share_amount)).quantize(cent)
            sp_decimal = Decimal(str(s.share_percent)).quantize(Decimal('0.01')) if s.share_percent is not None else None
        elif s.share_percent is not None:
            sp_decimal = Decimal(str(s.share_percent)).quantize(Decimal('0.01'))
            sa = (sp_decimal * amt / Decimal('100')).quantize(cent)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each split must have share_amount or share_percent"
            )
        
        if target_user_id not in group_member_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Split member not in group"
            )
        
        computed += sa
        split_objs.append((target_user_id, sa, sp_decimal))
    
    # Adjust for rounding differences
    diff = (amt - computed).quantize(cent)
    if diff != Decimal('0.00'):
        if abs(diff) > tolerance or not split_objs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Splits do not sum to amount (difference: {diff})"
            )
        # Adjust last split
        uid, sa, sp = split_objs[-1]
        adjusted = (sa + diff).quantize(cent)
        if adjusted < Decimal('0.00'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid split totals"
            )
        split_objs[-1] = (uid, adjusted, sp)
        computed = (computed + diff).quantize(cent)
    
    if computed != amt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Splits do not sum to amount"
        )
    
    # Create transaction
    new_transaction = Transaction(
        group_id=group_id,
        title=transaction_data.title,
        amount=amt,
        currency=transaction_data.currency,
        payer_user_id=payer_user_id,
        note=transaction_data.note,
        created_by=current_user.id
    )
    
    db.add(new_transaction)
    await db.flush()
    
    # Create splits
    for uid, sa, sp in split_objs:
        split = Split(
            transaction_id=new_transaction.id,
            user_id=uid,
            share_amount=sa,
            share_percent=sp,
            settled=False
        )
        db.add(split)
    
    # Create history entry
    history = TransactionHistory(
        transaction_id=new_transaction.id,
        group_id=group_id,
        action='created',
        data=json.dumps({"title": transaction_data.title, "amount": str(amt)}),
        actor_user_id=current_user.id
    )
    db.add(history)
    
    await db.commit()
    
    logger.info(f"User {current_user.id} created transaction {new_transaction.id} in group {group_id}")
    
    return {
        "ok": True,
        "transaction_id": new_transaction.id
    }


@router.put("/transactions/{transaction_id}", response_model=dict)
async def update_transaction(
    transaction_id: int = Path(..., description="Transaction ID"),
    transaction_data: TransactionUpdate = ...,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a transaction (PUT endpoint to match Azure Functions)
    """
    # Get existing transaction
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Verify group membership
    is_member = await verify_group_membership(transaction.group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Get member mapping
    name_to_id, id_to_name, group_member_ids = await get_member_name_mapping(db, transaction.group_id)
    
    # Get old splits for history
    result = await db.execute(
        select(Split).where(Split.transaction_id == transaction_id)
    )
    old_splits = result.scalars().all()
    old_snapshot = {
        "transaction": {
            "id": transaction.id,
            "title": transaction.title,
            "amount": str(transaction.amount),
            "payer": transaction.payer_user_id
        },
        "splits": [{"user_id": s.user_id, "share": str(s.share_amount)} for s in old_splits]
    }
    
    # Update transaction fields
    if transaction_data.title is not None:
        transaction.title = transaction_data.title
    if transaction_data.amount is not None:
        transaction.amount = transaction_data.amount
    if transaction_data.payer_user_id is not None:
        if transaction_data.payer_user_id not in group_member_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payer not a member of this group"
            )
        transaction.payer_user_id = transaction_data.payer_user_id
    elif transaction_data.payer_user_name:
        payer_id = name_to_id.get(transaction_data.payer_user_name.strip().lower())
        if not payer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payer not found in group"
            )
        transaction.payer_user_id = payer_id
    
    if transaction_data.note is not None:
        transaction.note = transaction_data.note
    
    # Update splits if provided
    if transaction_data.splits:
        # Delete old splits
        await db.execute(
            delete(Split).where(Split.transaction_id == transaction_id)
        )
        
        # Create new splits
        total_split = Decimal('0')
        for split_data in transaction_data.splits:
            user_id = split_data.user_id
            if split_data.user_name:
                user_id = name_to_id.get(split_data.user_name.strip().lower())
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"User {split_data.user_name} not found in group"
                    )
            
            if user_id not in group_member_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Split user not a member of this group"
                )
            
            share_amount = split_data.share if split_data.share else (
                transaction.amount * split_data.percent / 100 if split_data.percent else Decimal('0')
            )
            
            new_split = Split(
                transaction_id=transaction_id,
                user_id=user_id,
                share_amount=share_amount,
                share_percent=split_data.percent
            )
            db.add(new_split)
            total_split += share_amount
        
        # Verify splits total matches transaction amount
        if abs(total_split - transaction.amount) > Decimal('0.01'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Splits must sum to transaction amount"
            )
    
    # Create new snapshot for history
    result = await db.execute(
        select(Split).where(Split.transaction_id == transaction_id)
    )
    new_splits = result.scalars().all()
    new_snapshot = {
        "transaction": {
            "id": transaction.id,
            "title": transaction.title,
            "amount": str(transaction.amount),
            "payer": transaction.payer_user_id
        },
        "splits": [{"user_id": s.user_id, "share": str(s.share_amount)} for s in new_splits]
    }
    
    # Create history entry
    history = TransactionHistory(
        transaction_id=transaction_id,
        group_id=transaction.group_id,
        action='updated',
        data=json.dumps({"old": old_snapshot, "new": new_snapshot}),
        actor_user_id=current_user.id
    )
    db.add(history)
    
    await db.commit()
    await db.refresh(transaction)
    
    logger.info(f"User {current_user.id} updated transaction {transaction_id}")
    
    return {"ok": True, "transaction_id": transaction_id}


@router.get("/transactions/{transaction_id}/history", response_model=dict)
async def get_transaction_history(
    transaction_id: int = Path(..., description="Transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get history for a transaction
    """
    # Get transaction
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Verify group membership
    is_member = await verify_group_membership(transaction.group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Get history entries
    result = await db.execute(
        select(TransactionHistory)
        .where(TransactionHistory.transaction_id == transaction_id)
        .order_by(TransactionHistory.created_at.desc())
    )
    entries = result.scalars().all()
    
    # Get actor names
    actor_ids = {e.actor_user_id for e in entries if e.actor_user_id is not None}
    name_map = {}
    if actor_ids:
        result = await db.execute(
            select(User).where(User.id.in_(actor_ids))
        )
        actors = result.scalars().all()
        name_map = {u.id: u.name for u in actors}
    
    # Format history
    history = [
        {
            "history_id": e.id,
            "action": e.action,
            "data": e.data,
            "actor_user_name": name_map.get(e.actor_user_id),
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in entries
    ]
    
    logger.info(f"User {current_user.id} fetched history for transaction {transaction_id}")
    
    return {"history": history}


@router.delete("/transactions/{transaction_id}", response_model=MessageResponse)
async def delete_transaction(
    transaction_id: int = Path(..., description="Transaction ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a transaction
    """
    # Get transaction
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Verify group membership
    is_member = await verify_group_membership(transaction.group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Delete splits first
    await db.execute(
        delete(Split).where(Split.transaction_id == transaction_id)
    )
    
    # Create history entry
    history = TransactionHistory(
        transaction_id=transaction_id,
        group_id=transaction.group_id,
        action='deleted',
        data=json.dumps({"title": transaction.title, "amount": str(transaction.amount)}),
        actor_user_id=current_user.id
    )
    db.add(history)
    
    # Delete transaction
    await db.delete(transaction)
    await db.commit()
    
    logger.info(f"User {current_user.id} deleted transaction {transaction_id}")
    
    return MessageResponse(message="Transaction deleted")
