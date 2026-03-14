"""
Human-in-the-Loop Gates

Pauses workflow execution for human review and approval.
Uses asyncio.Event for non-blocking wait mechanism.

⚠️ KNOWN ISSUE - Multi-Process Deployment:
If running with multiple workers (Gunicorn, uvicorn --workers > 1), the in-memory
asyncio.Event will NOT work across processes. The API call to set_gate_decision()
may land on a different worker than the one waiting on event.wait().

SOLUTION for production: Replace in-memory events with Redis pub/sub:
- Store decisions in Redis with TTL
- Use Redis pub/sub channels to signal gate completion
- See Bug #2 fix in the issue tracker for implementation details
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
_active_human_gates: dict[str, dict] = {}


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
    import os
    key = f"{session_id}:{gate_id}"
    _gate_decisions[key] = decision
    
    # BUG FIX #2: Add diagnostic logging
    logger.info(f"[GATE DEBUG] set_gate_decision called for {gate_id} on pid={os.getpid()}, decision={decision.get('decision')}")
    
    # Set the event to unblock the waiting gate
    event = get_gate_event(session_id, gate_id)
    if event:
        event.set()
        logger.info(f"[GATE DEBUG] Event set successfully for {gate_id}")
    else:
        logger.error(f"[GATE DEBUG] No event found for {gate_id} - possible multi-process issue!")


def get_gate_decision(session_id: str, gate_id: str) -> dict | None:
    """Get a gate decision."""
    key = f"{session_id}:{gate_id}"
    return _gate_decisions.get(key)


def clear_gate(session_id: str, gate_id: str) -> None:
    """Clear gate event and decision."""
    key = f"{session_id}:{gate_id}"
    _gate_events.pop(key, None)
    _gate_decisions.pop(key, None)
    _active_human_gates.pop(session_id, None)


def get_active_gate(session_id: str) -> dict | None:
    """Get the currently active gate for a session from the global registry."""
    return _active_human_gates.get(session_id)


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
    
    # Create event for this gate BEFORE emitting pending event to avoid race conditions
    # if the user submits a decision via API immediately after seeing the log/event.
    event = create_gate_event(session_id, gate_id)
    
    # Register this gate globally for polling reliability
    _active_human_gates[session_id] = {
        "gate_id": gate_id,
        "gate_name": gate_name,
        "context": context,
        "waiting_since": now,
    }
    
    # Emit human_gate_pending event
    log_progress(state, f"⏸ {gate_name} - Waiting for human review...")
    logger.info(f"Gate {gate_id} event created and registered, sending pending notification to frontend.")
    
    await push_event(session_id, {
        "type": "human_gate_pending",
        "gate_id": gate_id,
        "gate_name": gate_name,
        "context": context,
        "timestamp": now,
    })
    
    # Wait for decision with timeout
    timeout_seconds = timeout_hours * 3600
    
    # BUG FIX #2: Add diagnostic logging for multi-process debugging
    import os
    logger.info(f"[GATE DEBUG] {gate_id} waiting. needs_correction={state.get('needs_correction')}, "
                f"correction_agent={state.get('correction_agent')}, worker_pid={os.getpid()}")
    
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
        logger.info(f"[GATE DEBUG] {gate_id} unblocked successfully on pid={os.getpid()}")
    except asyncio.TimeoutError:
        logger.error(f"[GATE DEBUG] {gate_id} TIMED OUT after {timeout_hours} hours. "
                    f"Was set_gate_decision ever called on pid={os.getpid()}?")
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
        state["needs_correction"] = False  # BUG FIX #1: Reset correction flag
        state["correction_agent"] = None  # BUG FIX #1: Clear correction agent
        state["correction_context"] = None  # BUG FIX #1: Clear correction context
        
        # BUG FIX #4: Reset generation_status to COMPLETED if Gate 7 is approved
        # Gate 7 is the final release gate - if approved, the workflow should complete successfully
        if gate_id == "gate_7_final_release":
            from backend.agents.state import GenerationStatus
            state["generation_status"] = GenerationStatus.COMPLETED.value
            logger.info(f"Gate 7 approved - setting generation_status to COMPLETED")
        
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
