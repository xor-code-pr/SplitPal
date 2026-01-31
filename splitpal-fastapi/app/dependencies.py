"""
FastAPI Dependencies for Authentication and Authorization
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, GroupMember
from app.auth_utils import decode_access_token

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token
    """
    token = credentials.credentials
    
    try:
        payload = decode_access_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to require global admin privileges
    """
    if not current_user.global_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


async def verify_group_membership(
    group_id: int,
    user: User,
    db: AsyncSession
) -> bool:
    """
    Helper function to verify if a user is a member of a group
    """
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id
        )
    )
    return result.scalar_one_or_none() is not None


async def verify_group_admin(
    group_id: int,
    user: User,
    db: AsyncSession
) -> bool:
    """
    Helper function to verify if a user is an admin of a group
    """
    if user.global_admin:
        return True
    
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        return False
    
    role = (member.role or "").strip().lower()
    return role in ("admin", "owner")


class GroupMembershipChecker:
    """
    Dependency class to check group membership
    """
    def __init__(self, group_id: int):
        self.group_id = group_id
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        is_member = await verify_group_membership(self.group_id, current_user, db)
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this group"
            )
        return current_user


class GroupAdminChecker:
    """
    Dependency class to check group admin privileges
    """
    def __init__(self, group_id: int):
        self.group_id = group_id
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        is_admin = await verify_group_admin(self.group_id, current_user, db)
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required for this group"
            )
        return current_user
