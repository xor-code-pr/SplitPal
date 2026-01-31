"""
Admin Router - Administrative endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func as sa_func
from typing import List
import logging

from app.database import get_db
from app.models import User, Group, GroupMember
from app.schemas import AdminUserResponse, AdminGroupResponse, MessageResponse
from app.dependencies import require_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users", response_model=dict)
async def get_all_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all users (admin only)
    """
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    
    logger.info(f"Admin {current_user.id} fetched all users")
    
    return {
        "users": [
            AdminUserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                global_admin=bool(user.global_admin),
                created_at=user.created_at
            )
            for user in users
        ]
    }


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int = Path(..., description="User ID"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user (admin only)
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    await db.delete(user)
    await db.commit()
    
    logger.info(f"Admin {current_user.id} deleted user {user_id}")
    
    return MessageResponse(message="User deleted")


@router.get("/groups", response_model=dict)
async def get_all_groups(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all groups (admin only)
    """
    result = await db.execute(
        select(Group).order_by(Group.created_at.desc())
    )
    groups = result.scalars().all()
    
    # Get creator names
    creator_ids = {g.created_by for g in groups if g.created_by is not None}
    name_map = {}
    if creator_ids:
        result = await db.execute(
            select(User).where(User.id.in_(creator_ids))
        )
        creators = result.scalars().all()
        name_map = {u.id: u.name for u in creators}
    
    # Get member counts
    result = await db.execute(
        select(GroupMember.group_id, sa_func.count(GroupMember.user_id))
        .group_by(GroupMember.group_id)
    )
    member_counts = {row[0]: row[1] for row in result.all()}
    
    logger.info(f"Admin {current_user.id} fetched all groups")
    
    return {
        "groups": [
            AdminGroupResponse(
                id=group.id,
                name=group.name,
                created_by=group.created_by,
                created_by_name=name_map.get(group.created_by),
                member_count=member_counts.get(group.id, 0),
                created_at=group.created_at
            )
            for group in groups
        ]
    }


@router.delete("/groups/{group_id}", response_model=MessageResponse)
async def delete_group(
    group_id: int = Path(..., description="Group ID"),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a group (admin only)
    """
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Delete all group members
    await db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    
    # Delete group
    await db.delete(group)
    await db.commit()
    
    logger.info(f"Admin {current_user.id} deleted group {group_id}")
    
    return MessageResponse(message="Group deleted")
