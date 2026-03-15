"""
Chat API - Conversational app modification after first build

Endpoints:
  POST /api/builder/{session_id}/chat         - Send a prompt to modify the app
  GET  /api/builder/{session_id}/chat/history  - Get chat history
  POST /api/builder/{session_id}/regenerate    - Regenerate with updated config
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.session import Session
from backend.agents.chat_modifier import process_chat_prompt

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class ChatRequest(BaseModel):
    """User chat message to modify the app."""
    message: str = Field(..., min_length=1, max_length=5000)


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" | "assistant" | "system"
    message: str
    config_changes: dict[str, Any] | None = None
    entities_preview: list[dict[str, Any]] | None = None
    suggested_followups: list[str] | None = None
    timestamp: str


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    role: str = "assistant"
    message: str
    config_changes: dict[str, Any] | None = None
    updated_config: dict[str, Any]
    entities_preview: list[dict[str, Any]] | None = None
    suggested_followups: list[str] | None = None
    change_type: str = "all"
    agents_to_rerun: list[str] = []
    timestamp: str


class ChatHistoryResponse(BaseModel):
    """Full chat history for a session."""
    session_id: str
    messages: list[ChatMessage]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

async def _get_session(session_id: str, db: AsyncSession) -> Session:
    """Get session or raise 404."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return session


# =============================================================================
# Routes
# =============================================================================

@router.post("/{session_id}/chat", response_model=ChatResponse)
async def send_chat_message(
    session_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send a chat message to modify the application.
    
    The LLM interprets the user's natural language request and
    updates the session configuration accordingly. The updated
    entity list is returned for the live preview to refresh.
    """
    session = await _get_session(session_id, db)
    
    # Get current config and chat history
    current_config = session.configuration or {}
    chat_history = current_config.get("chat_history", [])
    
    # Add user message to history
    user_msg = {
        "role": "user",
        "message": request.message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    chat_history.append(user_msg)
    
    # Process through LLM
    llm_provider = current_config.get("llm_provider")
    llm_model = current_config.get("llm_model")
    result = await process_chat_prompt(
        user_message=request.message,
        current_config=current_config,
        chat_history=chat_history,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )
    
    # Extract the updated config
    updated_config = result.get("updated_config", current_config)
    explanation = result.get("explanation", "Configuration updated.")
    suggested_followups = result.get("suggested_followups", [])
    
    # Build entities preview for the FioriPreview component
    entities_preview = updated_config.get("entities", [])
    
    # Build assistant message
    assistant_msg = {
        "role": "assistant",
        "message": explanation,
        "entities_preview": entities_preview,
        "suggested_followups": suggested_followups,
        "timestamp": datetime.utcnow().isoformat(),
    }
    chat_history.append(assistant_msg)
    
    # Update session config with new values + chat history
    updated_config["chat_history"] = chat_history
    
    # Preserve LLM provider settings
    if "llm_provider" not in updated_config and "llm_provider" in current_config:
        updated_config["llm_provider"] = current_config["llm_provider"]
    if "llm_model" not in updated_config and "llm_model" in current_config:
        updated_config["llm_model"] = current_config["llm_model"]
    
    session.configuration = updated_config
    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(session)
    
    logger.info(f"Chat message processed for session {session_id}: {explanation}")
    
    return ChatResponse(
        role="assistant",
        message=explanation,
        config_changes=result.get("updated_config"),
        updated_config=updated_config,
        entities_preview=entities_preview,
        suggested_followups=suggested_followups,
        change_type=result.get("change_type", "all"),
        agents_to_rerun=result.get("agents_to_rerun", []),
        timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/{session_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get the full chat history for a session."""
    session = await _get_session(session_id, db)
    
    chat_history = (session.configuration or {}).get("chat_history", [])
    
    messages = [
        ChatMessage(
            role=msg.get("role", "user"),
            message=msg.get("message", ""),
            config_changes=msg.get("config_changes"),
            entities_preview=msg.get("entities_preview"),
            suggested_followups=msg.get("suggested_followups"),
            timestamp=msg.get("timestamp", ""),
        )
        for msg in chat_history
    ]
    
    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages,
        total=len(messages),
    )


@router.post("/{session_id}/regenerate")
async def regenerate_app(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Regenerate the app with the updated configuration.
    
    This re-runs the full LangGraph agent pipeline using the
    modified configuration from chat interactions. Returns a
    streaming SSE response just like the original generation.
    """
    session = await _get_session(session_id, db)
    
    config = session.configuration or {}
    
    if not config.get("entities"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No entities configured. Use the chat to add entities first.",
        )
    
    # Reset session status for regeneration
    session.status = "in_progress"
    session.completed_at = None
    session.updated_at = datetime.utcnow()
    await db.commit()
    
    # Import here to avoid circular imports
    from backend.agents.graph import run_generation_workflow_streaming
    from backend.agents.state import create_initial_state

    entities = config.get("entities", [])

    initial_state = create_initial_state(
        session_id=session_id,
        project_name=config.get("project_name", session.project_name),
        project_namespace=config.get("project_namespace", session.project_namespace or "com.company"),
        project_description=config.get("project_description", session.project_description or ""),
    )
    initial_state.update(config)
    if not initial_state.get("fiori_main_entity") and entities:
        initial_state["fiori_main_entity"] = entities[0]["name"]
    
    # Ensure LLM provider and model are explicitly set from config (with defaults fallback)
    from backend.config import get_settings
    app_settings = get_settings()
    initial_state["llm_provider"] = config.get("llm_provider", app_settings.default_llm_provider)
    initial_state["llm_model"] = config.get("llm_model") or app_settings.default_llm_model
    
    # Stream the generation using SSE
    import json as json_module
    
    async def event_generator():
        """Generate SSE events during regeneration."""
        try:
            yield f"data: {json_module.dumps({'type': 'connected', 'session_id': session_id, 'regeneration': True})}\n\n"
            
            async for event in run_generation_workflow_streaming(initial_state):
                if event.get("type") == "workflow_complete":
                    final_state = event.get("final_state", {})
                    session_refresh = await db.get(Session, session_id)
                    if session_refresh:
                        session_refresh.status = final_state.get("generation_status", "completed")
                        session_refresh.configuration = {
                            **(session_refresh.configuration or {}),
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
                        session_refresh.completed_at = datetime.utcnow()
                        await db.commit()
                yield f"data: {json_module.dumps(event, default=str)}\n\n"
                    
        except Exception as e:
            logger.error(f"Regeneration error for session {session_id}: {e}")
            yield f"data: {json_module.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
