"""
Template Model - Pre-built domain templates
"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, JSON, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Template(Base):
    """Pre-built domain templates for quick starts."""
    
    __tablename__ = "templates"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    
    # Template info
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Template configuration (entities, relationships, etc.)
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Metadata
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Template preview
    preview_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Template(name={self.name}, domain={self.domain_type})>"
