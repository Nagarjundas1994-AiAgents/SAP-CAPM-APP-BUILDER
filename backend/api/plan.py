"""
Plan API - Generate and manage implementation plans before generation
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Session
from backend.agents.state import create_initial_state
from backend.agents.requirements import requirements_agent
from backend.agents.llm_providers import get_llm_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class FieldUpdate(BaseModel):
    """Field definition for plan update."""
    name: str
    type: str
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    key: bool = False
    nullable: bool = True
    default: str | None = None


class EntityUpdate(BaseModel):
    """Entity definition for plan update."""
    name: str
    description: str | None = None
    fields: list[FieldUpdate] = []
    aspects: list[str] = ["cuid", "managed"]


class RelationshipUpdate(BaseModel):
    """Relationship definition for plan update."""
    name: str
    source_entity: str
    target_entity: str
    type: str = "association"
    cardinality: str = "n:1"


class BusinessRuleUpdate(BaseModel):
    """Business rule for plan update."""
    name: str
    description: str
    entity: str
    rule_type: str = "validation"


class PlanUpdateRequest(BaseModel):
    """Request to update the implementation plan."""
    entities: list[EntityUpdate] | None = None
    relationships: list[RelationshipUpdate] | None = None
    business_rules: list[BusinessRuleUpdate] | None = None
    user_comments: str | None = None


class ImplementationPlan(BaseModel):
    """Implementation plan response."""
    session_id: str
    status: str
    entities: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    business_rules: list[dict[str, Any]]
    estimated_files: int
    estimated_time_seconds: int
    user_comments: str | None = None
    created_at: str
    approved: bool = False


# =============================================================================
# Routes
# =============================================================================

@router.post("/{session_id}/plan", response_model=ImplementationPlan)
async def generate_plan(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an implementation plan for review.
    
    Runs the Requirements Agent only to analyze entities and generate
    a detailed plan that users can review and modify before full generation.
    """
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    # Create initial state from session
    initial_state = create_initial_state(
        session_id=session.id,
        project_name=session.project_name,
        project_namespace=session.project_namespace or "",
        project_description=session.project_description or "",
    )
    
    # Merge saved configuration
    config = session.configuration or {}
    initial_state.update(config)
    
    logger.info(f"Generating plan for session {session_id} with {len(initial_state.get('entities', []))} initial entities")
    
    try:
        # Run only the requirements agent to generate the plan
        plan_state = await requirements_agent(initial_state)
        
        entities = plan_state.get("entities", [])
        relationships = plan_state.get("relationships", [])
        business_rules = plan_state.get("business_rules", [])
        
        # Estimate files and time
        entity_count = len(entities)
        estimated_files = (
            1 +  # schema.cds
            1 +  # service.cds
            1 +  # service.js
            entity_count +  # CSV data files
            2 +  # manifest.json, Component.js
            1 +  # xs-security.json
            1 +  # mta.yaml
            2    # README, package.json
        )
        estimated_time = 5 + (entity_count * 3) + (len(relationships) * 1)  # seconds
        
        # Save plan to session
        now = datetime.utcnow().isoformat()
        session.configuration = {
            **config,
            "entities": entities,
            "relationships": relationships,
            "business_rules": business_rules,
            "plan_created_at": now,
            "plan_approved": False,
        }
        session.status = "plan_ready"
        await db.commit()
        
        return ImplementationPlan(
            session_id=session_id,
            status="plan_ready",
            entities=entities,
            relationships=relationships,
            business_rules=business_rules,
            estimated_files=estimated_files,
            estimated_time_seconds=estimated_time,
            user_comments=config.get("user_comments"),
            created_at=now,
            approved=False,
        )
        
    except Exception as e:
        logger.error(f"Plan generation failed for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan generation failed: {str(e)}",
        )


@router.put("/{session_id}/plan", response_model=ImplementationPlan)
async def update_plan(
    session_id: str,
    request: PlanUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the implementation plan with user modifications.
    
    Users can:
    - Add/remove/modify entities and their fields
    - Add/remove relationships
    - Add/remove business rules
    - Add comments
    """
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    config = session.configuration or {}
    
    # Update entities if provided
    if request.entities is not None:
        config["entities"] = [e.model_dump() for e in request.entities]
    
    # Update relationships if provided
    if request.relationships is not None:
        config["relationships"] = [r.model_dump() for r in request.relationships]
    
    # Update business rules if provided
    if request.business_rules is not None:
        config["business_rules"] = [b.model_dump() for b in request.business_rules]
    
    # Update comments if provided
    if request.user_comments is not None:
        config["user_comments"] = request.user_comments
    
    # Mark plan as modified
    config["plan_modified_at"] = datetime.utcnow().isoformat()
    config["plan_approved"] = False
    
    session.configuration = config
    await db.commit()
    
    # Recalculate estimates
    entities = config.get("entities", [])
    relationships = config.get("relationships", [])
    entity_count = len(entities)
    estimated_files = (
        1 + 1 + 1 + entity_count + 2 + 1 + 1 + 2
    )
    estimated_time = 5 + (entity_count * 3) + (len(relationships) * 1)
    
    return ImplementationPlan(
        session_id=session_id,
        status="plan_ready",
        entities=entities,
        relationships=relationships,
        business_rules=config.get("business_rules", []),
        estimated_files=estimated_files,
        estimated_time_seconds=estimated_time,
        user_comments=config.get("user_comments"),
        created_at=config.get("plan_created_at", datetime.utcnow().isoformat()),
        approved=False,
    )


@router.post("/{session_id}/plan/approve", response_model=ImplementationPlan)
async def approve_plan(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve the implementation plan.
    
    After approval, the user can proceed to generation.
    """
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    config = session.configuration or {}
    
    # Check if plan exists
    if not config.get("entities"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No plan to approve. Generate a plan first.",
        )
    
    # Mark as approved
    config["plan_approved"] = True
    config["plan_approved_at"] = datetime.utcnow().isoformat()
    session.configuration = config
    session.status = "plan_approved"
    await db.commit()
    
    entities = config.get("entities", [])
    relationships = config.get("relationships", [])
    entity_count = len(entities)
    estimated_files = (
        1 + 1 + 1 + entity_count + 2 + 1 + 1 + 2
    )
    estimated_time = 5 + (entity_count * 3) + (len(relationships) * 1)
    
    return ImplementationPlan(
        session_id=session_id,
        status="plan_approved",
        entities=entities,
        relationships=relationships,
        business_rules=config.get("business_rules", []),
        estimated_files=estimated_files,
        estimated_time_seconds=estimated_time,
        user_comments=config.get("user_comments"),
        created_at=config.get("plan_created_at", datetime.utcnow().isoformat()),
        approved=True,
    )


@router.get("/{session_id}/plan", response_model=ImplementationPlan)
async def get_plan(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current implementation plan for a session.
    """
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    config = session.configuration or {}
    
    entities = config.get("entities", [])
    relationships = config.get("relationships", [])
    
    if not entities:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No plan found. Generate a plan first.",
        )
    
    entity_count = len(entities)
    estimated_files = (
        1 + 1 + 1 + entity_count + 2 + 1 + 1 + 2
    )
    estimated_time = 5 + (entity_count * 3) + (len(relationships) * 1)
    
    return ImplementationPlan(
        session_id=session_id,
        status=session.status,
        entities=entities,
        relationships=relationships,
        business_rules=config.get("business_rules", []),
        estimated_files=estimated_files,
        estimated_time_seconds=estimated_time,
        user_comments=config.get("user_comments"),
        created_at=config.get("plan_created_at", datetime.utcnow().isoformat()),
        approved=config.get("plan_approved", False),
    )
