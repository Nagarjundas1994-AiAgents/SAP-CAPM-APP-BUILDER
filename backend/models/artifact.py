"""
Artifact and Agent Execution Models
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import String, DateTime, JSON, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.session import Session


class AgentStatus(str, Enum):
    """Agent execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentExecution(Base):
    """Record of individual agent execution within a session."""
    
    __tablename__ = "agent_executions"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Agent info
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(50),
        default=AgentStatus.PENDING.value,
    )
    
    # State snapshots
    input_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="agent_executions")
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact",
        back_populates="agent_execution",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<AgentExecution(agent={self.agent_name}, status={self.status})>"
    
    @property
    def is_complete(self) -> bool:
        return self.status == AgentStatus.COMPLETED.value


class FileType(str, Enum):
    """Generated file types."""
    CDS = "cds"
    JAVASCRIPT = "js"
    TYPESCRIPT = "ts"
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    MARKDOWN = "md"
    CSV = "csv"
    PROPERTIES = "properties"
    OTHER = "other"


class Artifact(Base):
    """Generated file artifact."""
    
    __tablename__ = "artifacts"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_execution_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # File info
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    
    # Content (for smaller files) or storage reference
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="artifacts")
    agent_execution: Mapped["AgentExecution | None"] = relationship(
        "AgentExecution",
        back_populates="artifacts",
    )
    
    def __repr__(self) -> str:
        return f"<Artifact(path={self.file_path}, type={self.file_type})>"
