"""
Authentication Router - Login, Register, Logout, Refresh Token
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta
import logging

from app.database import get_db
from app.models import User, RefreshToken
from app.schemas import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, MessageResponse, UserResponse
from app.auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    JWT_EXP,
    JWT_REFRESH_EXP
)
from app.dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/users/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        logger.warning(f"Attempted to register duplicate email: {user_data.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        global_admin=False
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Generate tokens
    access_token = create_access_token(new_user.id, new_user.email)
    refresh_token = generate_refresh_token()
    expires_at = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_EXP)
    
    # Store refresh token
    refresh_token_obj = RefreshToken(
        user_id=new_user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        revoked=False
    )
    db.add(refresh_token_obj)
    await db.commit()
    
    logger.info(f"User registered: {new_user.id}")
    
    return TokenResponse(
        user=UserResponse(
            id=new_user.id,
            name=new_user.name,
            email=new_user.email,
            is_admin=bool(new_user.global_admin)
        ),
        token=access_token,
        token_expires_in=JWT_EXP,
        refresh_token=refresh_token,
        refresh_expires_in=JWT_REFRESH_EXP
    )


@router.post("/users/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login a user and return access token
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Login attempt with invalid email: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    verified, new_hash = verify_password(credentials.password, user.password_hash)
    
    if not verified:
        logger.warning(f"Login attempt with invalid password for: {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Update password hash if needed (migration from old bcrypt)
    if new_hash:
        user.password_hash = new_hash
        db.add(user)
    
    # Generate tokens
    access_token = create_access_token(user.id, user.email)
    refresh_token = generate_refresh_token()
    expires_at = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_EXP)
    
    # Delete old refresh tokens and create new one
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    
    refresh_token_obj = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=expires_at,
        revoked=False
    )
    db.add(refresh_token_obj)
    await db.commit()
    
    logger.info(f"User logged in: {user.id}")
    
    return TokenResponse(
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_admin=bool(user.global_admin)
        ),
        token=access_token,
        token_expires_in=JWT_EXP,
        refresh_token=refresh_token,
        refresh_expires_in=JWT_REFRESH_EXP
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout user by revoking all refresh tokens
    """
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))
    await db.commit()
    
    logger.info(f"User logged out: {current_user.id}")
    
    return MessageResponse(message="Logged out successfully")


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    token_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    """
    token_hash = hash_refresh_token(token_request.refresh_token)
    
    # Find refresh token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False
        )
    )
    refresh_token_obj = result.scalar_one_or_none()
    
    if not refresh_token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if expired
    if refresh_token_obj.expires_at < datetime.utcnow():
        await db.delete(refresh_token_obj)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == refresh_token_obj.user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # Generate new tokens
    access_token = create_access_token(user.id, user.email)
    new_refresh_token = generate_refresh_token()
    new_expires_at = datetime.utcnow() + timedelta(seconds=JWT_REFRESH_EXP)
    
    # Delete old refresh token
    await db.delete(refresh_token_obj)
    
    # Create new refresh token
    new_refresh_token_obj = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_refresh_token),
        expires_at=new_expires_at,
        revoked=False
    )
    db.add(new_refresh_token_obj)
    await db.commit()
    
    logger.info(f"Token refreshed for user: {user.id}")
    
    return TokenResponse(
        user=UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            is_admin=bool(user.global_admin)
        ),
        token=access_token,
        token_expires_in=JWT_EXP,
        refresh_token=new_refresh_token,
        refresh_expires_in=JWT_REFRESH_EXP
    )
