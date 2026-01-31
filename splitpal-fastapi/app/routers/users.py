"""
Users Router - User lookup endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
import logging

from app.database import get_db
from app.models import User
from app.schemas import UserResponse
from app.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/users/lookup", response_model=UserResponse)
async def lookup_user(
    email: str = Query(..., description="Email address to lookup"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Lookup a user by email address
    """
    result = await db.execute(
        select(User).where(sa_func.lower(User.email) == email.strip().lower())
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"User {current_user.id} looked up user {user.id}")
    
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        is_admin=bool(user.global_admin)
    )
