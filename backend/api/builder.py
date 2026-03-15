"""
Builder API - Trigger and monitor generation workflows
"""

import logging
import zipfile
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Session
from backend.agents.state import create_initial_state, BuilderState
from backend.agents.graph import run_generation_workflow
from backend.agents.human_gate import get_active_gate, set_gate_decision, get_gate_event

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class GenerateRequest(BaseModel):
    """Request to start generation."""
    llm_provider: str | None = None  # Optional, uses default if not specified
    llm_model: str | None = None  # Optional, uses default if not specified


class GenerationStatus(BaseModel):
    """Generation status response."""
    session_id: str
    status: str
    current_agent: str | None
    agent_history: list[dict[str, Any]]
    validation_errors: list[dict[str, Any]]
    started_at: str | None
    completed_at: str | None
    workspace_path: str | None = None
    verification_summary: dict[str, Any] | None = None


class ArtifactPreview(BaseModel):
    """Preview of generated artifacts."""
    path: str
    content: str
    file_type: str


class GenerationResult(BaseModel):
    """Complete generation result."""
    session_id: str
    status: str
    artifacts_db: list[ArtifactPreview]
    artifacts_srv: list[ArtifactPreview]
    artifacts_app: list[ArtifactPreview]
    artifacts_deployment: list[ArtifactPreview]
    artifacts_docs: list[ArtifactPreview]
    validation_errors: list[dict[str, Any]]
    workspace_path: str | None = None
    verification_summary: dict[str, Any] | None = None
    generated_manifest: dict[str, Any] | None = None


class GateDecisionRequest(BaseModel):
    """Request to make a gate decision."""
    decision: str = Field(..., description="Decision: 'approved' or 'refine'")
    notes: str = Field(default="", description="Optional notes from reviewer")
    target_agent: str | None = Field(default=None, description="Agent to refine (if decision is 'refine')")


class GateDecisionResponse(BaseModel):
    """Response after gate decision."""
    status: str
    next_agent: str | None


class CurrentGateResponse(BaseModel):
    """Current gate status."""
    gate_id: str | None
    gate_name: str | None
    context: dict[str, Any] | None
    waiting_since: str | None


# =============================================================================
# Routes
# =============================================================================

@router.post("/{session_id}/generate", response_model=GenerationStatus)
async def start_generation(
    session_id: str,
    request: GenerateRequest = Body(default_factory=GenerateRequest),
    db: AsyncSession = Depends(get_db),
):
    """
    Start the generation workflow for a session.
    
    This triggers the LangGraph multi-agent workflow:
    1. Requirements Agent
    2. Data Modeling Agent
    3. Service Exposure Agent
    4. Business Logic Agent
    5. Fiori UI Agent
    6. Security Agent
    7. Extension Agent
    8. Deployment Agent
    9. Validation Agent
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
    
    # Merge ALL saved configuration (not just keys that exist in initial_state)
    config = session.configuration or {}
    initial_state.update(config)
    
    # Ensure LLM provider and model are explicitly set from config (with defaults fallback)
    from backend.config import get_settings
    app_settings = get_settings()
    
    initial_state["llm_provider"] = config.get("llm_provider", app_settings.default_llm_provider)
    initial_state["llm_model"] = config.get("llm_model") or app_settings.default_llm_model
    
    # Override with request body if provided
    if request.llm_provider:
        initial_state["llm_provider"] = request.llm_provider
    if request.llm_model:
        initial_state["llm_model"] = request.llm_model
    
    logger.info(f"Starting generation with {len(initial_state.get('entities', []))} entities, provider={initial_state.get('llm_provider')}, model={initial_state.get('llm_model')}")
    
    # Update session status
    session.status = "in_progress"
    await db.commit()
    
    try:
        # Run the workflow
        final_state = await run_generation_workflow(initial_state)
        
        # Update session with results
        session.status = final_state.get("generation_status", "completed")
        session.configuration = {
            **config,
            "entities": final_state.get("entities", []),
            "relationships": final_state.get("relationships", []),
            "business_rules": final_state.get("business_rules", []),
            "artifacts_db": final_state.get("artifacts_db", []),
            "artifacts_srv": final_state.get("artifacts_srv", []),
            "artifacts_app": final_state.get("artifacts_app", []),
            "artifacts_deployment": final_state.get("artifacts_deployment", []),
            "artifacts_docs": final_state.get("artifacts_docs", []),
            "agent_history": final_state.get("agent_history", []),
            "validation_errors": final_state.get("validation_errors", []),
            "enterprise_blueprint": final_state.get("enterprise_blueprint", {}),
            "service_modules": final_state.get("service_modules", []),
            "ui_apps": final_state.get("ui_apps", []),
            "quality_gates": final_state.get("quality_gates", []),
            "generated_workspace_path": final_state.get("generated_workspace_path"),
            "generated_manifest": final_state.get("generated_manifest"),
            "verification_checks": final_state.get("verification_checks", []),
            "verification_summary": final_state.get("verification_summary"),
        }
        session.completed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Generation completed for session {session_id}")
        
        return GenerationStatus(
            session_id=session_id,
            status=final_state.get("generation_status", "completed"),
            current_agent=final_state.get("current_agent"),
            agent_history=final_state.get("agent_history", []),
            validation_errors=final_state.get("validation_errors", []),
            started_at=final_state.get("generation_started_at"),
            completed_at=final_state.get("generation_completed_at"),
            workspace_path=final_state.get("generated_workspace_path"),
            verification_summary=final_state.get("verification_summary"),
        )
        
    except Exception as e:
        logger.error(f"Generation failed for session {session_id}: {e}")
        session.status = "failed"
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {str(e)}",
        )


@router.get("/{session_id}/generate/stream")
async def stream_generation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Stream the generation progress for a session using SSE.
    """
    import json
    from backend.agents.graph import run_generation_workflow_streaming
    
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )

    # Initial state
    initial_state = create_initial_state(
        session_id=session.id,
        project_name=session.project_name,
        project_namespace=session.project_namespace or "",
        project_description=session.project_description or "",
    )
    config = session.configuration or {}
    initial_state.update(config)
    
    # Ensure LLM provider and model are explicitly set from config (with defaults fallback)
    from backend.config import get_settings
    app_settings = get_settings()
    
    initial_state["llm_provider"] = config.get("llm_provider", app_settings.default_llm_provider)
    initial_state["llm_model"] = config.get("llm_model") or app_settings.default_llm_model
    
    logger.info(f"Starting streaming generation, provider={initial_state.get('llm_provider')}, model={initial_state.get('llm_model')}")
    
    # If using gemini, it might encounter JSON parsing issues with streaming, 
    # but we should still respect the user's choice rather than forcing openai and failing.
    # We will rely on self-healing retries for any JSON structural issues.

    async def event_generator():
        yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"
        try:
            async for event in run_generation_workflow_streaming(initial_state):
                # Update session state in DB for each major update
                if event["type"] in ["agent_complete", "workflow_complete"]:
                    # Refetch session in this generator scope if needed, but for now we update via db session
                    # Note: We might need a separate db session for the generator if it lasts long
                    pass 
                
                yield f"data: {json.dumps(event)}\n\n"
                
                if event["type"] == "workflow_complete":
                    # Update final session state
                    res = await db.execute(select(Session).where(Session.id == session_id))
                    s = res.scalar_one()
                    
                    final_state = event.get("final_state", {})
                    config = s.configuration or {}
                    
                    # Merge logic: prioritize final_state but keep existing configuration keys if needed
                    updated_config = {**config}
                    
                    # Keys to sync from final_state
                    keys_to_sync = [
                        "entities", "relationships", "business_rules", "artifacts_db",
                        "artifacts_srv", "artifacts_app", "artifacts_deployment", "artifacts_docs",
                        "agent_history", "validation_errors", "enterprise_blueprint",
                        "service_modules", "ui_apps", "quality_gates", 
                        "generated_workspace_path", "generated_manifest",
                        "verification_checks", "verification_summary"
                    ]
                    
                    for key in keys_to_sync:
                        val = final_state.get(key)
                        # Only update if the value is truthy (not empty list/dict/None) 
                        # or if it's the first time we're writing it.
                        if val or key not in updated_config:
                            updated_config[key] = val
                    
                    s.status = final_state.get("generation_status", "completed")
                    s.configuration = updated_config
                    s.completed_at = datetime.utcnow()
                    await db.commit()
                    logger.info(f"Streaming generation completed and saved for session {session_id}")
                    break
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )


@router.get("/{session_id}/status", response_model=GenerationStatus)
async def get_generation_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the current generation status for a session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    config = session.configuration or {}
    
    return GenerationStatus(
        session_id=session_id,
        status=session.status,
        current_agent=config.get("current_agent"),
        agent_history=config.get("agent_history", []),
        validation_errors=config.get("validation_errors", []),
        started_at=config.get("generation_started_at"),
        completed_at=config.get("generation_completed_at"),
        workspace_path=config.get("generated_workspace_path"),
        verification_summary=config.get("verification_summary"),
    )


class UpdateArtifactRequest(BaseModel):
    """Request to update artifact content."""
    path: str
    content: str


@router.put("/{session_id}/artifacts", response_model=GenerationStatus)
async def update_artifacts(
    session_id: str,
    request: UpdateArtifactRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a generated artifact for a session.
    
    Allows users to modify generated code before downloading.
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
    updated = False
    
    # Search for artifact in all categories
    for category in ["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_deployment", "artifacts_docs"]:
        artifacts = config.get(category, [])
        for art in artifacts:
            if art["path"] == request.path:
                art["content"] = request.content
                updated = True
                break
        if updated:
            break
            
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {request.path} not found in session {session_id}",
        )
        
    session.configuration = config
    await db.commit()
    
    return GenerationStatus(
        session_id=session_id,
        status=session.status,
        current_agent=config.get("current_agent"),
        agent_history=config.get("agent_history", []),
        validation_errors=config.get("validation_errors", []),
        started_at=config.get("generation_started_at"),
        completed_at=config.get("generation_completed_at"),
    )


@router.get("/{session_id}/artifacts", response_model=GenerationResult)
async def get_artifacts(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all generated artifacts for a session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    config = session.configuration or {}
    
    return GenerationResult(
        session_id=session_id,
        status=session.status,
        artifacts_db=[ArtifactPreview(**a) for a in config.get("artifacts_db", [])],
        artifacts_srv=[ArtifactPreview(**a) for a in config.get("artifacts_srv", [])],
        artifacts_app=[ArtifactPreview(**a) for a in config.get("artifacts_app", [])],
        artifacts_deployment=[ArtifactPreview(**a) for a in config.get("artifacts_deployment", [])],
        artifacts_docs=[ArtifactPreview(**a) for a in config.get("artifacts_docs", [])],
        validation_errors=config.get("validation_errors", []),
        workspace_path=config.get("generated_workspace_path"),
        verification_summary=config.get("verification_summary"),
        generated_manifest=config.get("generated_manifest"),
    )


@router.get("/{session_id}/download")
async def download_project(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Download the generated project as a ZIP file."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    if session.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generation must be completed before download",
        )
    
    config = session.configuration or {}
    workspace_path = config.get("generated_workspace_path")

    if workspace_path:
        from pathlib import Path

        workspace = Path(workspace_path)
        if workspace.exists():
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in workspace.rglob("*"):
                    if file_path.is_file():
                        zip_file.write(file_path, file_path.relative_to(workspace).as_posix())
            zip_buffer.seek(0)

            filename = f"{session.project_name.lower().replace(' ', '-')}.zip"
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    # Collect all artifacts
    all_artifacts = []
    for category in ["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_deployment", "artifacts_docs"]:
        all_artifacts.extend(config.get(category, []))
    
    if not all_artifacts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No artifacts to download",
        )
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        generated_paths = set()
        for artifact in all_artifacts:
            zip_file.writestr(artifact["path"], artifact["content"])
            generated_paths.add(artifact["path"])
        
        # Add fallback package.json if not generated by agents
        if "package.json" not in generated_paths:
            package_json = f'''{{
  "name": "{session.project_name.lower().replace(" ", "-")}",
  "version": "1.0.0",
  "description": "{session.project_description or "Generated SAP CAP Application"}",
  "cds": {{
    "requires": {{
      "db": "sql"
    }}
  }},
  "scripts": {{
    "start": "cds-serve",
    "watch": "cds watch",
    "test": "cds bind --exec -- npm test --prefix test"
  }},
  "dependencies": {{
    "@sap/cds": "^7",
    "express": "^4"
  }},
  "devDependencies": {{
    "@sap/cds-dk": "^7",
    "sqlite3": "^5"
  }}
}}'''
            zip_file.writestr("package.json", package_json)
        
        # Add fallback README if not generated by agents
        if "README.md" not in generated_paths:
            readme = f'''# {session.project_name}

{session.project_description or "Generated SAP CAP Application"}

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the application:
   ```bash
   cds watch
   ```

3. Open http://localhost:4004 in your browser.

## Generated by SAP App Builder

This project was generated using the SAP CAPM + Fiori App Builder Platform.
'''
            zip_file.writestr("README.md", readme)
    
    zip_buffer.seek(0)
    
    filename = f"{session.project_name.lower().replace(' ', '-')}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# =============================================================================
# Human Gate Endpoints
# =============================================================================

@router.post("/{session_id}/gate/{gate_id}/decision", response_model=GateDecisionResponse)
async def submit_gate_decision(
    session_id: str,
    gate_id: str,
    request: GateDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a decision for a human gate.
    
    This unblocks the workflow that is waiting at the gate.
    """
    # Verify session exists
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    # Check if gate is waiting
    event = get_gate_event(session_id, gate_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gate {gate_id} is not currently waiting for a decision",
        )
    
    # Validate decision
    if request.decision not in ["approved", "refine"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be 'approved' or 'refine'",
        )
    
    # Set the decision
    decision = {
        "decision": request.decision,
        "notes": request.notes,
        "target_agent": request.target_agent,
    }
    set_gate_decision(session_id, gate_id, decision)
    
    logger.info(f"Gate {gate_id} decision submitted for session {session_id}: {request.decision}")
    
    next_agent = "continue" if request.decision == "approved" else request.target_agent
    
    return GateDecisionResponse(
        status="ok",
        next_agent=next_agent,
    )


@router.get("/{session_id}/gate/current", response_model=CurrentGateResponse)
async def get_current_gate(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the current gate that is waiting for a decision.
    """
    # Verify session exists
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    
    # First check the global active gate registry (real-time source)
    active_gate = get_active_gate(session_id)
    if active_gate:
        return CurrentGateResponse(
            gate_id=active_gate["gate_id"],
            gate_name=active_gate["gate_name"],
            context=active_gate["context"],
            waiting_since=active_gate["waiting_since"],
        )

    # Fallback to session configuration (persisted source)
    config = session.configuration or {}
    current_gate = config.get("current_gate")
    
    if not current_gate:
        return CurrentGateResponse(
            gate_id=None,
            gate_name=None,
            context=None,
            waiting_since=None,
        )
    
    # Get gate context from agent history
    agent_history = config.get("agent_history", [])
    gate_decisions = config.get("gate_decisions", {})
    
    # Map gate IDs to names
    gate_names = {
        "gate_1_requirements": "Gate 1: Requirements Sign-off",
        "gate_2_architecture": "Gate 2: Architecture Sign-off",
        "gate_3_data_layer": "Gate 3: Data Layer Sign-off",
        "gate_4_service_layer": "Gate 4: Service Layer Sign-off",
        "gate_5_business_logic": "Gate 5: Business Logic Sign-off",
        "gate_6_pre_deployment": "Gate 6: Pre-deployment Sign-off",
        "gate_7_final_release": "Gate 7: Final Release Sign-off",
    }
    
    return CurrentGateResponse(
        gate_id=current_gate,
        gate_name=gate_names.get(current_gate, current_gate),
        context={
            "agent_history": agent_history[-5:] if agent_history else [],  # Last 5 agents
            "validation_errors": config.get("validation_errors", []),
            "gate_decisions": gate_decisions,
        },
        waiting_since=config.get("updated_at"),
    )
