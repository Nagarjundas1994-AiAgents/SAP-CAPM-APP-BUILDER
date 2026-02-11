"""
LangGraph Agent Orchestration Graph

Defines the multi-agent workflow for generating SAP CAP + Fiori applications.
Uses LangGraph StateGraph for stateful, deterministic execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal, Any

from langgraph.graph import StateGraph, END

from backend.agents.state import BuilderState, GenerationStatus
from backend.agents.requirements import requirements_agent
from backend.agents.data_modeling import data_modeling_agent
from backend.agents.service_exposure import service_exposure_agent
from backend.agents.business_logic import business_logic_agent
from backend.agents.fiori_ui import fiori_ui_agent
from backend.agents.security import security_agent
from backend.agents.extension import extension_agent
from backend.agents.deployment import deployment_agent
from backend.agents.validation import validation_agent

logger = logging.getLogger(__name__)


# =============================================================================
# Route Functions
# =============================================================================

def should_retry_agent(state: BuilderState) -> str:
    """
    Generic routing function for self-healing agents.
    If 'needs_correction' is True, loops back to the same agent.
    Otherwise, continues to the next step.
    """
    if state.get("needs_correction"):
        return "retry"
    return "continue"


def should_continue_after_requirements(state: BuilderState) -> Literal["data_modeling", "end"]:
    """Check if requirements agent succeeded and we should continue."""
    errors = state.get("validation_errors", [])
    has_critical_error = any(e.get("severity") == "error" for e in errors)
    
    if has_critical_error:
        logger.warning("Requirements validation failed, stopping workflow")
        return "end"
    
    return "data_modeling"


# =============================================================================
# Graph Builder
# =============================================================================

def create_builder_graph() -> StateGraph:
    """
    Create the LangGraph workflow for the SAP App Builder.
    
    Flow:
    1. Requirements → validation check
    2. Data Modeling (Self-Healing)
    3. Service Exposure (Self-Healing)
    4. Business Logic (Self-Healing)
    5. Fiori UI
    6. Security
    7. Extension
    8. Deployment
    9. Validation (final)
    """
    
    # Create the graph
    graph = StateGraph(BuilderState)
    
    # Add nodes (agents)
    graph.add_node("requirements", requirements_agent)
    graph.add_node("data_modeling", data_modeling_agent)
    graph.add_node("service_exposure", service_exposure_agent)
    graph.add_node("business_logic", business_logic_agent)
    graph.add_node("fiori_ui", fiori_ui_agent)
    graph.add_node("security", security_agent)
    graph.add_node("extension", extension_agent)
    graph.add_node("deployment", deployment_agent)
    graph.add_node("validation", validation_agent)
    
    # Set entry point
    graph.set_entry_point("requirements")
    
    # Add conditional edges
    
    # 1. Requirements -> Data Modeling
    graph.add_conditional_edges(
        "requirements",
        should_continue_after_requirements,
        {
            "data_modeling": "data_modeling",
            "end": END,
        }
    )
    
    # 2. Data Modeling (with retry loop)
    graph.add_conditional_edges(
        "data_modeling",
        should_retry_agent,
        {
            "retry": "data_modeling",
            "continue": "service_exposure",
        }
    )
    
    # 3. Service Exposure (with retry loop)
    graph.add_conditional_edges(
        "service_exposure",
        should_retry_agent,
        {
            "retry": "service_exposure",
            "continue": "business_logic",
        }
    )
    
    # 4. Business Logic (with retry loop)
    graph.add_conditional_edges(
        "business_logic",
        should_retry_agent,
        {
            "retry": "business_logic",
            "continue": "fiori_ui",
        }
    )
    
    # Linear flow for now (can be parallelized later)
    graph.add_edge("service_exposure", "business_logic")
    # 4. Business Logic (with retry loop)
    graph.add_conditional_edges(
        "business_logic",
        should_retry_agent,
        {
            "retry": "business_logic",
            "continue": "fiori_ui",
        }
    )
    
    # 5. Fiori UI (with retry loop)
    graph.add_conditional_edges(
        "fiori_ui",
        should_retry_agent,
        {
            "retry": "fiori_ui",
            "continue": "security",
        }
    )
    
    # 6. Security (with retry loop)
    graph.add_conditional_edges(
        "security",
        should_retry_agent,
        {
            "retry": "security",
            "continue": "extension",
        }
    )
    
    # 7. Extension (with retry loop)
    graph.add_conditional_edges(
        "extension",
        should_retry_agent,
        {
            "retry": "extension",
            "continue": "deployment",
        }
    )
    
    # 8. Deployment (with retry loop)
    graph.add_conditional_edges(
        "deployment",
        should_retry_agent,
        {
            "retry": "deployment",
            "continue": "validation",
        }
    )
    
    # 9. Validation (final)
    graph.add_edge("validation", END)
    
    return graph


# Global compiled graph instance
_compiled_graph = None


def get_builder_graph():
    """Get or create the compiled builder graph."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = create_builder_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


async def run_generation_workflow(initial_state: BuilderState) -> BuilderState:
    """
    Run the complete generation workflow.
    
    Args:
        initial_state: Initial BuilderState with user configuration
        
    Returns:
        Final BuilderState with all generated artifacts
    """
    logger.info(f"Starting generation workflow for project: {initial_state.get('project_name')}")
    
    # Set generation status
    initial_state["generation_status"] = GenerationStatus.IN_PROGRESS.value
    initial_state["generation_started_at"] = datetime.utcnow().isoformat()
    
    # Get compiled graph
    graph = get_builder_graph()
    
    # Run the workflow
    try:
        final_state = await graph.ainvoke(initial_state)
        logger.info("Generation workflow completed")
        return final_state
    except Exception as e:
        logger.error(f"Generation workflow failed: {e}")
        initial_state["generation_status"] = GenerationStatus.FAILED.value
        initial_state["validation_errors"] = initial_state.get("validation_errors", []) + [{
            "agent": "workflow",
            "code": "WORKFLOW_ERROR",
            "message": str(e),
            "field": None,
            "severity": "error",
        }]
        raise


async def run_generation_workflow_streaming(initial_state: BuilderState):
    """
    Run the generation workflow with REAL-TIME streaming updates.
    
    Uses an asyncio.Queue so that log_progress() calls inside agents
    are pushed to the SSE endpoint immediately — not batched until
    the agent finishes.
    
    Yields:
        Dict events: agent_start, agent_log, agent_complete, workflow_complete
    """
    from backend.agents.progress import (
        create_progress_queue,
        remove_progress_queue,
        push_event,
    )

    session_id = initial_state.get("session_id", "unknown")
    logger.info(f"Starting streaming workflow for project: {initial_state.get('project_name')}")
    
    # Set generation status
    initial_state["generation_status"] = GenerationStatus.IN_PROGRESS.value
    initial_state["generation_started_at"] = datetime.utcnow().isoformat()
    
    # Create the real-time progress queue
    queue = create_progress_queue(session_id)
    
    # Get compiled graph
    graph = get_builder_graph()
    
    # Agent order for emitting agent_start events
    AGENT_ORDER = [
        "requirements", "data_modeling", "service_exposure",
        "business_logic", "fiori_ui", "security",
        "extension", "deployment", "validation",
    ]
    
    final_state: dict[str, Any] = {}
    workflow_error: Exception | None = None
    
    async def _run_graph():
        """Run the LangGraph workflow in a background task."""
        nonlocal final_state, workflow_error
        try:
            last_agent_idx = -1
            async for event in graph.astream(initial_state):
                for node_name, node_state in event.items():
                    final_state = node_state
                    
                    # Emit agent_start for the NEXT agent if applicable
                    agent_history = node_state.get("agent_history", [])
                    latest = agent_history[-1] if agent_history else None
                    
                    if latest and latest.get("status") in ["completed", "failed"]:
                        # Emit agent_complete
                        await push_event(session_id, {
                            "type": "agent_complete",
                            "agent": node_name,
                            "status": latest.get("status"),
                            "agent_history": agent_history,
                            "validation_errors": node_state.get("validation_errors", []),
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        
                        # Emit agent_start for next agent
                        try:
                            current_idx = AGENT_ORDER.index(node_name)
                            if current_idx + 1 < len(AGENT_ORDER):
                                next_agent = AGENT_ORDER[current_idx + 1]
                                await push_event(session_id, {
                                    "type": "agent_start",
                                    "agent": next_agent,
                                    "timestamp": datetime.utcnow().isoformat(),
                                })
                        except ValueError:
                            pass
            
            # Workflow completed successfully
            await push_event(session_id, {
                "type": "workflow_complete",
                "status": "completed",
                "generation_status": final_state.get("generation_status", "completed"),
                "agent_history": final_state.get("agent_history", []),
                "validation_errors": final_state.get("validation_errors", []),
                "final_state": final_state,
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            workflow_error = e
            logger.error(f"Streaming workflow failed: {e}")
            await push_event(session_id, {
                "type": "workflow_error",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })
        finally:
            # Sentinel to signal the generator to stop
            await push_event(session_id, {"type": "_done"})
    
    # Emit agent_start for the first agent
    await push_event(session_id, {
        "type": "agent_start",
        "agent": AGENT_ORDER[0],
        "timestamp": datetime.utcnow().isoformat(),
    })
    
    # Start graph execution in the background
    task = asyncio.create_task(_run_graph())
    
    try:
        # Yield events from the queue in real-time
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                # Keep-alive: prevent SSE connection from timing out
                yield {
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                continue
            
            if event.get("type") == "_done":
                break
            
            yield event
    finally:
        remove_progress_queue(session_id)
        if not task.done():
            task.cancel()

