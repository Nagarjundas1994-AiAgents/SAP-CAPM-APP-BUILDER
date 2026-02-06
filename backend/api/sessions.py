"""
Sessions API - Manage builder sessions
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Session, User
from backend.agents.state import create_initial_state, BuilderState

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class SessionCreate(BaseModel):
    """Request to create a new builder session."""
    project_name: str = Field(..., min_length=3, max_length=50)
    project_namespace: str | None = None
    project_description: str | None = None
    user_email: str = Field(default="demo@example.com")


class SessionUpdate(BaseModel):
    """Request to update session configuration."""
    configuration: dict[str, Any]


class SessionResponse(BaseModel):
    """Session response."""
    id: str
    project_name: str
    project_namespace: str | None
    project_description: str | None
    status: str
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """List of sessions response."""
    sessions: list[SessionResponse]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

async def get_or_create_user(db: AsyncSession, email: str) -> User:
    """Get existing user or create a new one."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(email=email, name=email.split("@")[0])
        db.add(user)
        await db.flush()
    
    return user


# =============================================================================
# Routes
# =============================================================================

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new builder session."""
    # Get or create user
    user = await get_or_create_user(db, request.user_email)
    
    # Create session
    session = Session(
        user_id=user.id,
        project_name=request.project_name,
        project_namespace=request.project_namespace,
        project_description=request.project_description,
        status="draft",
        configuration={},
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    logger.info(f"Created session {session.id} for project {request.project_name}")
    
    return SessionResponse(
        id=session.id,
        project_name=session.project_name,
        project_namespace=session.project_namespace,
        project_description=session.project_description,
        status=session.status,
        configuration=session.configuration,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    user_email: str = "demo@example.com",
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List all sessions for a user."""
    # Get user
    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()
    
    if not user:
        return SessionListResponse(sessions=[], total=0)
    
    # Query sessions
    query = (
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                project_name=s.project_name,
                project_namespace=s.project_namespace,
                project_description=s.project_description,
                status=s.status,
                configuration=s.configuration,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ],
        total=len(sessions),
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    return SessionResponse(
        id=session.id,
        project_name=session.project_name,
        project_namespace=session.project_namespace,
        project_description=session.project_description,
        status=session.status,
        configuration=session.configuration,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.put("/{session_id}/config", response_model=SessionResponse)
async def update_session_config(
    session_id: str,
    request: SessionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update session configuration."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    # Merge configuration
    current_config = session.configuration or {}
    current_config.update(request.configuration)
    session.configuration = current_config
    session.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(session)
    
    logger.info(f"Updated configuration for session {session_id}")
    
    return SessionResponse(
        id=session.id,
        project_name=session.project_name,
        project_namespace=session.project_namespace,
        project_description=session.project_description,
        status=session.status,
        configuration=session.configuration,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    await db.delete(session)
    await db.commit()
    
    logger.info(f"Deleted session {session_id}")
