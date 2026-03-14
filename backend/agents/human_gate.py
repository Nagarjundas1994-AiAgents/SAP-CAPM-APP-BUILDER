"""
Human-in-the-Loop Gates

Pauses workflow execution for human review and approval.
Uses asyncio.Event for non-blocking wait mechanism.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Literal

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress, push_event

logger = logging.getLogger(__name__)

# Global registry of gate events
_gate_events: dict[str, asyncio.Event] = {}
_gate_decisions: dict[str, dict] = {}


def create_gate_event(session_id: str, gate_id: str) -> asyncio.Event:
    """Create an asyncio.Event for a gate."""
    key = f"{session_id}:{gate_id}"
    event = asyncio.Event()
    _gate_events[key] = event
    return event


def get_gate_event(session_id: str, gate_id: str) -> asyncio.Event | None:
    """Get the asyncio.Event for a gate."""
    key = f"{session_id}:{gate_id}"
    return _gate_events.get(key)


def set_gate_decision(session_id: str, gate_id: str, decision: dict) -> None:
    """Store a gate decision."""
    key = f"{session_id}:{gate_id}"
    _gate_decisions[key] = decision
    
    # Set the event to unblock the waiting gate
    event = get_gate_event(session_id, gate_id)
    if event:
        event.set()


def get_gate_decision(session_id: str, gate_id: str) -> dict | None:
    """Get a gate decision."""
    key = f"{session_id}:{gate_id}"
    return _gate_decisions.get(key)


def clear_gate(session_id: str, gate_id: str) -> None:
    """Clear gate event and decision."""
    key = f"{session_id}:{gate_id}"
    _gate_events.pop(key, None)
    _gate_decisions.pop(key, None)


async def human_gate(
    state: BuilderState,
    gate_id: str,
    gate_name: str,
    context_summary: str,
    reviewing_agent: str,
    timeout_hours: int = 24
) -> BuilderState:
    """
    Human gate - pauses workflow for human review.
    
    Args:
        state: Current BuilderState
        gate_id: Unique gate identifier (e.g., "gate_1_requirements")
        gate_name: Human-readable gate name (e.g., "Gate 1: Requirements Sign-off")
        context_summary: Summary of what is being reviewed
        reviewing_agent: The agent whose output is being reviewed
        timeout_hours: Hours to wait before timeout (default 24)
        
    Returns:
        Updated BuilderState with gate decision applied
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"Human gate {gate_id} activated for session {session_id}")
    
    now = datetime.utcnow().isoformat()
    state["current_gate"] = gate_id
    state["updated_at"] = now
    
    # Get context for review
    agent_history = state.get("agent_history", [])
    latest_agent = next((a for a in reversed(agent_history) if a["agent_name"] == reviewing_agent), None)
    
    context = {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "summary": context_summary,
        "reviewing_agent": reviewing_agent,
        "agent_output": latest_agent,
        "validation_errors": state.get("validation_errors", []),
        "waiting_since": now,
    }
    
    # Emit human_gate_pending event
    log_progress(state, f"⏸ {gate_name} - Waiting for human review...")
    await push_event(session_id, {
        "type": "human_gate_pending",
        "gate_id": gate_id,
        "gate_name": gate_name,
        "context": context,
        "timestamp": now,
    })
    
    # Create event for this gate
    event = create_gate_event(session_id, gate_id)
    
    # Wait for decision with timeout
    timeout_seconds = timeout_hours * 3600
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.warning(f"Gate {gate_id} timed out after {timeout_hours} hours")
        log_progress(state, f"⚠️ {gate_name} timed out - workflow paused")
        
        # Don't fail - just pause the session
        state["current_gate"] = gate_id
        state["generation_status"] = "paused"
        return state
    
    # Get the decision
    decision = get_gate_decision(session_id, gate_id)
    if not decision:
        logger.error(f"Gate {gate_id} event set but no decision found")
        return state
    
    # Process decision
    decision_type = decision.get("decision", "approved")
    notes = decision.get("notes", "")
    target_agent = decision.get("target_agent")
    
    # Record gate decision
    if "gate_decisions" not in state:
        state["gate_decisions"] = {}
    state["gate_decisions"][gate_id] = {
        "decision": decision_type,
        "notes": notes,
        "target_agent": target_agent,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if decision_type == "approved":
        log_progress(state, f"✅ {gate_name} approved - continuing workflow")
        state["current_gate"] = None
        state["human_feedback"] = None
        
        # Emit gate approved event
        await push_event(session_id, {
            "type": "human_gate_approved",
            "gate_id": gate_id,
            "next_agent": "continue",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
    elif decision_type == "refine":
        log_progress(state, f"🔄 {gate_name} - refinement requested for {target_agent or reviewing_agent}")
        state["needs_correction"] = True
        state["correction_agent"] = target_agent or reviewing_agent
        state["human_feedback"] = notes
        state["correction_context"] = {
            "issues": [notes],
            "correction_prompt": f"Human reviewer feedback: {notes}",
        }
        
        # Emit gate refinement event
        await push_event(session_id, {
            "type": "human_gate_refine",
            "gate_id": gate_id,
            "target_agent": target_agent or reviewing_agent,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    # Clear gate
    clear_gate(session_id, gate_id)
    
    return state


# =============================================================================
# Gate Agent Functions (7 gates)
# =============================================================================

async def gate_1_requirements(state: BuilderState) -> BuilderState:
    """Gate 1: Requirements Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_1_requirements",
        gate_name="Gate 1: Requirements Sign-off",
        context_summary="Review parsed requirements and domain entities",
        reviewing_agent="requirements",
    )


async def gate_2_architecture(state: BuilderState) -> BuilderState:
    """Gate 2: Architecture Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_2_architecture",
        gate_name="Gate 2: Architecture Sign-off",
        context_summary="Review enterprise architecture blueprint and service modules",
        reviewing_agent="enterprise_architecture",
    )


async def gate_3_data_layer(state: BuilderState) -> BuilderState:
    """Gate 3: Data Layer Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_3_data_layer",
        gate_name="Gate 3: Data Layer Sign-off",
        context_summary="Review CDS schema, entities, and database migration",
        reviewing_agent="db_migration",
    )


async def gate_4_service_layer(state: BuilderState) -> BuilderState:
    """Gate 4: Service Layer Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_4_service_layer",
        gate_name="Gate 4: Service Layer Sign-off",
        context_summary="Review OData service exposure and integration design",
        reviewing_agent="integration_design",
    )


async def gate_5_business_logic(state: BuilderState) -> BuilderState:
    """Gate 5: Business Logic Sign-off (CRITICAL - UI starts after this)"""
    return await human_gate(
        state=state,
        gate_id="gate_5_business_logic",
        gate_name="Gate 5: Business Logic Sign-off ⚠️ UI starts after this gate",
        context_summary="Review business logic handlers, validations, and workflows",
        reviewing_agent="business_logic",
    )


async def gate_6_pre_deployment(state: BuilderState) -> BuilderState:
    """Gate 6: Pre-deployment Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_6_pre_deployment",
        gate_name="Gate 6: Pre-deployment Sign-off",
        context_summary="Review performance optimizations and deployment readiness",
        reviewing_agent="performance_review",
    )


async def gate_7_final_release(state: BuilderState) -> BuilderState:
    """Gate 7: Final Release Sign-off"""
    return await human_gate(
        state=state,
        gate_id="gate_7_final_release",
        gate_name="Gate 7: Final Release Sign-off",
        context_summary="Final validation - approve for production release",
        reviewing_agent="validation",
    )
