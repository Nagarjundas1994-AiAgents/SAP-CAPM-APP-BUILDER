"""
Session Model - Builder session state
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.artifact import Artifact, AgentExecution
    from backend.models.audit import AuditLog


class SessionStatus(str, Enum):
    """Session lifecycle states."""
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Session(Base):
    """Builder session containing project configuration and state."""
    
    __tablename__ = "sessions"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Project info
    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    project_namespace: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=SessionStatus.DRAFT.value,
    )
    
    # Full configuration state (matches GlobalState schema)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    agent_executions: Mapped[list["AgentExecution"]] = relationship(
        "AgentExecution",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentExecution.started_at",
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Session(id={self.id}, project={self.project_name}, status={self.status})>"
    
    @property
    def is_complete(self) -> bool:
        return self.status == SessionStatus.COMPLETED.value
    
    @property
    def is_failed(self) -> bool:
        return self.status == SessionStatus.FAILED.value
