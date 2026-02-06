"""
LangGraph Agent Orchestration Graph

Defines the multi-agent workflow for generating SAP CAP + Fiori applications.
Uses LangGraph StateGraph for stateful, deterministic execution.
"""

import logging
from datetime import datetime
from typing import Literal

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

def should_continue_after_requirements(state: BuilderState) -> Literal["data_modeling", "end"]:
    """Check if requirements agent succeeded and we should continue."""
    errors = state.get("validation_errors", [])
    has_critical_error = any(e.get("severity") == "error" for e in errors)
    
    if has_critical_error:
        logger.warning("Requirements validation failed, stopping workflow")
        return "end"
    
    return "data_modeling"


def should_continue_after_data_modeling(state: BuilderState) -> Literal["service_exposure", "end"]:
    """Check if data modeling succeeded."""
    errors = state.get("validation_errors", [])
    recent_errors = [e for e in errors if e.get("agent") == "data_modeling"]
    has_critical_error = any(e.get("severity") == "error" for e in recent_errors)
    
    if has_critical_error:
        logger.warning("Data modeling failed, stopping workflow")
        return "end"
    
    return "service_exposure"


# =============================================================================
# Graph Builder
# =============================================================================

def create_builder_graph() -> StateGraph:
    """
    Create the LangGraph workflow for the SAP App Builder.
    
    Flow:
    1. Requirements → validation check
    2. Data Modeling → validation check
    3. Service Exposure
    4. Business Logic
    5. Fiori UI       } These can run in parallel conceptually
    6. Security
    7. Extension
    8. Deployment
    9. Validation (final)
    
    Any failure halts the workflow and marks it as failed.
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
    graph.add_conditional_edges(
        "requirements",
        should_continue_after_requirements,
        {
            "data_modeling": "data_modeling",
            "end": END,
        }
    )
    
    graph.add_conditional_edges(
        "data_modeling",
        should_continue_after_data_modeling,
        {
            "service_exposure": "service_exposure",
            "end": END,
        }
    )
    
    # Linear flow for now (can be parallelized later)
    graph.add_edge("service_exposure", "business_logic")
    graph.add_edge("business_logic", "fiori_ui")
    graph.add_edge("fiori_ui", "security")
    graph.add_edge("security", "extension")
    graph.add_edge("extension", "deployment")
    graph.add_edge("deployment", "validation")
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
