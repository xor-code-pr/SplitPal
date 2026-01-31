"""
Groups Router - Group management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func as sa_func
from typing import List
import logging

from app.database import get_db
from app.models import User, Group, GroupMember
from app.schemas import GroupCreate, GroupResponse, GroupMemberResponse, MessageResponse, UserLookup
from app.dependencies import get_current_user, verify_group_membership, verify_group_admin

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/groups", response_model=dict)
async def get_user_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all groups for the current user
    """
    # Get all groups where user is a member
    result = await db.execute(
        select(Group)
        .join(GroupMember, Group.id == GroupMember.group_id)
        .where(GroupMember.user_id == current_user.id)
    )
    groups = result.scalars().all()
    
    if not groups:
        return []
    
    group_ids = [g.id for g in groups]
    creator_ids = {g.created_by for g in groups if g.created_by is not None}
    
    # Get creator names
    name_map = {}
    if creator_ids:
        result = await db.execute(
            select(User).where(User.id.in_(creator_ids))
        )
        creators = result.scalars().all()
        name_map = {u.id: u.name for u in creators}
    
    # Get all members for these groups
    members_map = {}
    result = await db.execute(
        select(
            GroupMember.group_id,
            GroupMember.user_id,
            GroupMember.role,
            GroupMember.joined_at,
            User.name,
            User.global_admin
        )
        .join(User, GroupMember.user_id == User.id)
        .where(GroupMember.group_id.in_(group_ids))
    )
    
    for row in result.all():
        group_id, member_id, member_role, joined_at, member_name, is_global_admin = row
        normalized_role = (member_role or "").strip().lower()
        is_admin_flag = bool(is_global_admin or normalized_role in ("admin", "owner"))
        
        members_map.setdefault(group_id, []).append(
            GroupMemberResponse(
                user_id=member_id,
                user_name=member_name,
                role=member_role,
                is_admin=is_admin_flag,
                joined_at=joined_at
            )
        )
    
    # Build response
    groups_response = {
        "groups": [
            GroupResponse(
                group_id=g.id,
                group_name=g.name,
                created_by_id=g.created_by,
                created_by_name=name_map.get(g.created_by),
                members=members_map.get(g.id, [])
            )
            for g in groups
        ]
    }
    
    logger.info(f"User {current_user.id} fetched {len(groups)} groups")
    return groups_response


@router.post("/groups", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new group
    """
    # Create group
    new_group = Group(
        name=group_data.name,
        created_by=current_user.id
    )
    
    db.add(new_group)
    await db.commit()
    await db.refresh(new_group)
    
    # Add creator as admin member
    group_member = GroupMember(
        group_id=new_group.id,
        user_id=current_user.id,
        role='admin'
    )
    
    db.add(group_member)
    await db.commit()
    
    logger.info(f"User {current_user.id} created group {new_group.id}")
    
    return {
        "group": {
            "id": new_group.id,
            "name": new_group.name,
            "created_by_id": new_group.created_by
        }
    }


@router.post("/groups/join", response_model=dict)
async def join_group(
    member_data: UserLookup,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a member to a group (admin only)
    """
    group_id = member_data.group_id
    
    # Verify group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Verify current user is a member
    is_member = await verify_group_membership(group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Verify current user is admin
    is_admin = await verify_group_admin(group_id, current_user, db)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group admins can add members"
        )
    
    if not member_data or not member_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide the email of the member to add"
        )
    
    member_email = member_data.email.strip().lower()
    
    # Find target user
    result = await db.execute(
        select(User).where(sa_func.lower(User.email) == member_email)
    )
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if already a member
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == target_user.id
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member"
        )
    
    # Add new member
    new_member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        role='member'
    )
    
    db.add(new_member)
    await db.commit()
    
    logger.info(f"User {current_user.id} added user {target_user.id} to group {group_id}")
    
    return {
        "message": "Member added",
        "member": {
            "user_id": target_user.id,
            "user_name": target_user.name,
            "email": target_user.email
        }
    }


@router.delete("/groups/{group_id}/members/{user_id}", response_model=MessageResponse)
async def remove_group_member(
    group_id: int = Path(..., description="Group ID"),
    user_id: int = Path(..., description="User ID to remove"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a group (admin only or self-removal)
    """
    # Verify group exists
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Verify current user is a member
    is_member = await verify_group_membership(group_id, current_user, db)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this group"
        )
    
    # Check if removing self or if user is admin
    is_self_removal = (current_user.id == user_id)
    
    if not is_self_removal:
        is_admin = await verify_group_admin(group_id, current_user, db)
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only group admins can remove other members"
            )
    
    # Remove member
    result = await db.execute(
        delete(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in group"
        )
    
    await db.commit()
    
    logger.info(f"User {current_user.id} removed user {user_id} from group {group_id}")
    
    return MessageResponse(message="Member removed from group")
