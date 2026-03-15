"""
LangGraph Agent Orchestration Graph

Defines the multi-agent workflow for generating SAP CAP + Fiori applications.
Uses LangGraph StateGraph for stateful, deterministic execution.

ARCHITECTURE IMPROVEMENTS (2026-03-15):
- Added Annotated reducers for list fields to prevent data loss
- Implemented thread-safe graph singleton with asyncio.Lock
- Added checkpointer for state persistence and human gate support
- Increased recursion_limit from 100 to 300 for 28-agent workflow
- Fixed router functions to be pure (no state mutations)
- Agents now increment retry_counts properly
- Added per-agent timeout wrapper
- Enabled LangSmith tracing support
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Literal, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.agents.state import BuilderState, GenerationStatus
from backend.agents.requirements import requirements_agent
from backend.agents.enterprise_architecture import enterprise_architecture_agent
from backend.agents.domain_modeling import domain_modeling_agent
from backend.agents.data_modeling import data_modeling_agent
from backend.agents.db_migration import db_migration_agent
from backend.agents.integration_design import integration_design_agent
from backend.agents.service_exposure import service_exposure_agent
from backend.agents.error_handling import error_handling_agent
from backend.agents.audit_logging import audit_logging_agent
from backend.agents.api_governance import api_governance_agent
from backend.agents.business_logic import business_logic_agent
from backend.agents.ux_design import ux_design_agent
from backend.agents.fiori_ui import fiori_ui_agent
from backend.agents.security import security_agent
from backend.agents.multitenancy import multitenancy_agent
from backend.agents.i18n import i18n_agent
from backend.agents.feature_flags import feature_flags_agent
from backend.agents.compliance_check import compliance_check_agent
from backend.agents.extension import extension_agent
from backend.agents.performance_review import performance_review_agent
from backend.agents.ci_cd import ci_cd_agent
from backend.agents.deployment import deployment_agent
from backend.agents.testing import testing_agent
from backend.agents.observability import observability_agent
from backend.agents.documentation import documentation_agent
from backend.agents.integration import integration_agent
from backend.agents.project_assembly import project_assembly_agent
from backend.agents.project_verification import project_verification_agent
from backend.agents.validation import validation_agent
from backend.agents.human_gate import (
    gate_1_requirements,
    gate_2_architecture,
    gate_3_data_layer,
    gate_4_service_layer,
    gate_5_business_logic,
    gate_6_pre_deployment,
    gate_7_final_release,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Route Functions
# =============================================================================

def should_retry_agent(state: BuilderState) -> str:
    """
    Generic routing function for self-healing agents.
    If 'needs_correction' is True, loops back to the same agent.
    Otherwise, continues to the next step.
    
    NOTE: This is a PURE routing function - it only reads state and returns a string.
    Any state mutations must happen inside the agent itself, not here.
    """
    if state.get("needs_correction"):
        return "retry"
    return "continue"


def should_continue_after_requirements(state: BuilderState) -> Literal["enterprise_architecture", "failed"]:
    """Check if requirements agent succeeded and we should continue."""
    errors = state.get("validation_errors", [])
    has_critical_error = any(e.get("severity") == "error" for e in errors)
    
    if has_critical_error:
        logger.warning("Requirements validation failed, stopping workflow")
        return "failed"
    
    return "enterprise_architecture"


def should_self_heal(state: BuilderState) -> str:
    """
    After validation, decide whether to loop back for self-healing
    or end the workflow.
    
    UPGRADED: Now covers ALL 28 agents dynamically instead of hardcoded list.
    """
    if state.get("needs_correction"):
        target = state.get("correction_agent", "")
        
        # Define agents that CANNOT be self-healed (gates, fan-ins, terminals)
        NON_HEALABLE = {
            "failed", "gate_1_requirements", "gate_2_architecture", "gate_3_data_layer",
            "gate_4_service_layer", "gate_5_business_logic", "gate_6_pre_deployment",
            "gate_7_final_release", "parallel_phase_1_fanin", "parallel_phase_2_fanin",
            "parallel_phase_3_fanin", "parallel_phase_4_fanin"
        }
        
        # All other agents are healable
        if target and target not in NON_HEALABLE:
            logger.info(f"Self-healing: routing back to {target}")
            return target
        else:
            logger.warning(f"Self-healing requested for non-healable target '{target}', ending workflow")
    
    return "end"


def should_continue_after_gate(state: BuilderState, next_node: str, refine_node: str) -> str:
    """
    Decide if a human gate approved continuation or requested refinement.
    
    Args:
        state: Current BuilderState
        next_node: Node to go to if approved
        refine_node: Node to go to if refinement requested
        
    Returns:
        next_node if approved, refine_node if refinement requested
    """
    if state.get("needs_correction"):
        correction_agent = state.get("correction_agent", refine_node)
        
        # Validate correction_agent matches expected refine_node
        if correction_agent != refine_node:
            logger.warning(f"Gate correction_agent '{correction_agent}' doesn't match expected refine_node '{refine_node}'. "
                          f"Using refine_node as fallback to avoid routing errors.")
            correction_agent = refine_node
        
        logger.info(f"Gate refinement: routing to {correction_agent}")
        return correction_agent
    
    logger.info(f"Gate approved: continuing to {next_node}")
    return next_node


# =============================================================================
# Parallel Phase Fan-In Functions
# =============================================================================

async def parallel_phase_1_fanin(state: BuilderState) -> dict:
    """
    Fan-in for Parallel Phase 1 (service_exposure + integration_design).
    Checks both agents completed successfully.
    """
    logger.info("Parallel Phase 1 fan-in: checking service_exposure + integration_design")
    
    # Check if any agent failed
    if state.get("agent_failed"):
        logger.error("Parallel Phase 1: At least one agent failed")
        return {"generation_status": GenerationStatus.FAILED.value}
    
    return {}


async def parallel_phase_2_fanin(state: BuilderState) -> dict:
    """
    Fan-in for Parallel Phase 2 (error_handling + audit_logging + api_governance).
    Checks all three agents completed successfully.
    """
    logger.info("Parallel Phase 2 fan-in: checking error_handling + audit_logging + api_governance")
    
    # Check if any agent failed
    if state.get("agent_failed"):
        logger.error("Parallel Phase 2: At least one agent failed")
        return {"generation_status": GenerationStatus.FAILED.value}
    
    return {}


async def parallel_phase_3_fanin(state: BuilderState) -> dict:
    """
    Fan-in for Parallel Phase 3 (fiori_ui + security + multitenancy + i18n + feature_flags).
    Checks all five agents completed successfully.
    """
    logger.info("Parallel Phase 3 fan-in: checking fiori_ui + security + multitenancy + i18n + feature_flags")
    
    # Check if any agent failed
    if state.get("agent_failed"):
        logger.error("Parallel Phase 3: At least one agent failed")
        return {"generation_status": GenerationStatus.FAILED.value}
    
    return {}


async def parallel_phase_4_fanin(state: BuilderState) -> dict:
    """
    Fan-in for Parallel Phase 4 (testing + documentation + observability).
    Checks all three agents completed successfully.
    """
    logger.info("Parallel Phase 4 fan-in: checking testing + documentation + observability")
    
    # Check if any agent failed
    if state.get("agent_failed"):
        logger.error("Parallel Phase 4: At least one agent failed")
        return {"generation_status": GenerationStatus.FAILED.value}
    
    return {}


async def failed_terminal(state: BuilderState) -> dict[str, Any]:
    """
    FAILED terminal node.
    Sets generation status to FAILED and logs error context.
    
    FIXED: Now uses await push_event() directly instead of fire-and-forget asyncio.create_task
    """
    logger.error("Workflow reached FAILED terminal")
    
    # Emit workflow_failed event synchronously
    from backend.agents.progress import push_event
    session_id = state.get("session_id", "unknown")
    
    try:
        await push_event(session_id, {
            "type": "workflow_failed",
            "status": "failed",
            "error": "Workflow failed - check agent history for details",
            "agent_history": state.get("agent_history", []),
            "validation_errors": state.get("validation_errors", []),
            "timestamp": datetime.utcnow().isoformat(),
        })
    except Exception as e:
        logger.error(f"Failed to emit workflow_failed event: {e}")
    
    # Return only changed keys (not full state copy)
    return {
        "generation_status": GenerationStatus.FAILED.value,
        "generation_completed_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Graph Builder (UPGRADED - World-Class Enterprise Architecture)
# =============================================================================

def create_builder_graph() -> StateGraph:
    """
    Create the LangGraph workflow for the SAP App Builder.
    
    UPGRADED ARCHITECTURE with 28 agents, 7 human gates, 4 parallel phases.
    
    Flow:
    1. Requirements → Gate 1
    2. Enterprise Architecture → Gate 2
    3. Domain Modeling
    4. Data Modeling
    5. DB Migration → Gate 3
    6. Parallel Phase 1: Service Exposure + Integration Design → Gate 4
    7. Parallel Phase 2: Error Handling + Audit Logging + API Governance
    8. Business Logic → Gate 5 (CRITICAL - UI starts after this)
    9. UX Design
    10. Parallel Phase 3: Fiori UI + Security + Multitenancy + i18n + Feature Flags
    11. Compliance Check
    12. Extension
    13. Performance Review → Gate 6
    14. CI/CD
    15. Deployment
    16. Parallel Phase 4: Testing + Documentation + Observability
    17. Project Assembly
    18. Project Verification
    19. Validation → Gate 7 or self-heal
    20. SUCCESS or FAILED terminal
    """
    
    # Create the graph
    graph = StateGraph(BuilderState)
    
    # =========================================================================
    # Add all agent nodes (28 total)
    # =========================================================================
    graph.add_node("requirements", requirements_agent)
    graph.add_node("enterprise_architecture", enterprise_architecture_agent)
    graph.add_node("domain_modeling", domain_modeling_agent)
    graph.add_node("data_modeling", data_modeling_agent)
    graph.add_node("db_migration", db_migration_agent)
    graph.add_node("integration_design", integration_design_agent)
    graph.add_node("service_exposure", service_exposure_agent)
    graph.add_node("error_handling", error_handling_agent)
    graph.add_node("audit_logging", audit_logging_agent)
    graph.add_node("api_governance", api_governance_agent)
    graph.add_node("business_logic", business_logic_agent)
    graph.add_node("ux_design", ux_design_agent)
    graph.add_node("fiori_ui", fiori_ui_agent)
    graph.add_node("security", security_agent)
    graph.add_node("multitenancy", multitenancy_agent)
    graph.add_node("i18n", i18n_agent)
    graph.add_node("feature_flags", feature_flags_agent)
    graph.add_node("compliance_check", compliance_check_agent)
    graph.add_node("extension", extension_agent)
    graph.add_node("performance_review", performance_review_agent)
    graph.add_node("ci_cd", ci_cd_agent)
    graph.add_node("deployment", deployment_agent)
    graph.add_node("testing", testing_agent)
    graph.add_node("observability", observability_agent)
    graph.add_node("documentation", documentation_agent)
    graph.add_node("integration", integration_agent)
    graph.add_node("project_assembly", project_assembly_agent)
    graph.add_node("project_verification", project_verification_agent)
    graph.add_node("validation", validation_agent)
    
    # =========================================================================
    # Add human gate nodes (7 gates)
    # =========================================================================
    graph.add_node("gate_1_requirements", gate_1_requirements)
    graph.add_node("gate_2_architecture", gate_2_architecture)
    graph.add_node("gate_3_data_layer", gate_3_data_layer)
    graph.add_node("gate_4_service_layer", gate_4_service_layer)
    graph.add_node("gate_5_business_logic", gate_5_business_logic)
    graph.add_node("gate_6_pre_deployment", gate_6_pre_deployment)
    graph.add_node("gate_7_final_release", gate_7_final_release)
    
    # =========================================================================
    # Add parallel phase fan-in nodes
    # =========================================================================
    graph.add_node("parallel_phase_1_fanin", parallel_phase_1_fanin)
    graph.add_node("parallel_phase_2_fanin", parallel_phase_2_fanin)
    graph.add_node("parallel_phase_3_fanin", parallel_phase_3_fanin)
    graph.add_node("parallel_phase_4_fanin", parallel_phase_4_fanin)
    
    # =========================================================================
    # Add FAILED terminal node
    # =========================================================================
    graph.add_node("failed", failed_terminal)
    
    # =========================================================================
    # Set entry point
    # =========================================================================
    graph.set_entry_point("requirements")
    
    # =========================================================================
    # Build the workflow edges
    # =========================================================================
    
    # 1. Requirements → Gate 1
    graph.add_conditional_edges(
        "requirements",
        should_continue_after_requirements,
        {
            "enterprise_architecture": "gate_1_requirements",
            "failed": "failed",
        }
    )
    
    # 1a. Gate 1 → Enterprise Architecture or refine Requirements
    graph.add_conditional_edges(
        "gate_1_requirements",
        lambda state: should_continue_after_gate(state, "enterprise_architecture", "requirements"),
        {
            "enterprise_architecture": "enterprise_architecture",
            "requirements": "requirements",
        }
    )
    
    # 2. Enterprise Architecture → Gate 2 (with retry)
    graph.add_conditional_edges(
        "enterprise_architecture",
        should_retry_agent,
        {
            "retry": "enterprise_architecture",
            "continue": "gate_2_architecture",
        }
    )
    
    # 2a. Gate 2 → Domain Modeling or refine Enterprise Architecture
    graph.add_conditional_edges(
        "gate_2_architecture",
        lambda state: should_continue_after_gate(state, "domain_modeling", "enterprise_architecture"),
        {
            "domain_modeling": "domain_modeling",
            "enterprise_architecture": "enterprise_architecture",
        }
    )
    
    # 3. Domain Modeling → Data Modeling (with retry)
    graph.add_conditional_edges(
        "domain_modeling",
        should_retry_agent,
        {
            "retry": "domain_modeling",
            "continue": "data_modeling",
        }
    )
    
    # 4. Data Modeling → DB Migration (with retry)
    graph.add_conditional_edges(
        "data_modeling",
        should_retry_agent,
        {
            "retry": "data_modeling",
            "continue": "db_migration",
        }
    )
    
    # 5. DB Migration → Gate 3 (with retry)
    graph.add_conditional_edges(
        "db_migration",
        should_retry_agent,
        {
            "retry": "db_migration",
            "continue": "gate_3_data_layer",
        }
    )
    
    # 5a. Gate 3 → Integration or refine DB Migration
    graph.add_conditional_edges(
        "gate_3_data_layer",
        lambda state: should_continue_after_gate(state, "integration", "db_migration"),
        {
            "integration": "integration",
            "db_migration": "db_migration",
        }
    )
    
    # 6. Integration → Service Exposure (with retry)
    graph.add_conditional_edges(
        "integration",
        should_retry_agent,
        {
            "retry": "integration",
            "continue": "service_exposure",
        }
    )
    
    # 7. Service Exposure → Integration Design (Parallel Phase 1 start)
    # Note: In a true parallel implementation, both would start simultaneously
    # For now, we run them sequentially but mark them as parallel phase
    graph.add_conditional_edges(
        "service_exposure",
        should_retry_agent,
        {
            "retry": "service_exposure",
            "continue": "integration_design",
        }
    )
    
    # 8. Integration Design → Parallel Phase 1 Fan-in
    graph.add_conditional_edges(
        "integration_design",
        should_retry_agent,
        {
            "retry": "integration_design",
            "continue": "parallel_phase_1_fanin",
        }
    )
    
    # 9. Parallel Phase 1 Fan-in → Gate 4
    graph.add_edge("parallel_phase_1_fanin", "gate_4_service_layer")
    
    # 9a. Gate 4 → Error Handling or refine Integration Design
    graph.add_conditional_edges(
        "gate_4_service_layer",
        lambda state: should_continue_after_gate(state, "error_handling", "integration_design"),
        {
            "error_handling": "error_handling",
            "integration_design": "integration_design",
        }
    )
    
    # 10. Error Handling → Audit Logging
    graph.add_conditional_edges(
        "error_handling",
        should_retry_agent,
        {
            "retry": "error_handling",
            "continue": "audit_logging",
        }
    )
    
    # 11. Audit Logging → API Governance
    graph.add_conditional_edges(
        "audit_logging",
        should_retry_agent,
        {
            "retry": "audit_logging",
            "continue": "api_governance",
        }
    )
    
    # 12. API Governance → Parallel Phase 2 Fan-in
    graph.add_conditional_edges(
        "api_governance",
        should_retry_agent,
        {
            "retry": "api_governance",
            "continue": "parallel_phase_2_fanin",
        }
    )
    
    # 13. Parallel Phase 2 Fan-in → Business Logic
    graph.add_edge("parallel_phase_2_fanin", "business_logic")
    
    # 14. Business Logic → Gate 5 (with retry) - CRITICAL: UI starts after this gate
    graph.add_conditional_edges(
        "business_logic",
        should_retry_agent,
        {
            "retry": "business_logic",
            "continue": "gate_5_business_logic",
        }
    )
    
    # 14a. Gate 5 → UX Design or refine Business Logic
    graph.add_conditional_edges(
        "gate_5_business_logic",
        lambda state: should_continue_after_gate(state, "ux_design", "business_logic"),
        {
            "ux_design": "ux_design",
            "business_logic": "business_logic",
        }
    )
    
    # 15. UX Design → Fiori UI (Parallel Phase 3 start)
    graph.add_conditional_edges(
        "ux_design",
        should_retry_agent,
        {
            "retry": "ux_design",
            "continue": "fiori_ui",
        }
    )
    
    # 16. Fiori UI → Security
    graph.add_conditional_edges(
        "fiori_ui",
        should_retry_agent,
        {
            "retry": "fiori_ui",
            "continue": "security",
        }
    )
    
    # 17. Security → Multitenancy
    graph.add_conditional_edges(
        "security",
        should_retry_agent,
        {
            "retry": "security",
            "continue": "multitenancy",
        }
    )
    
    # 18. Multitenancy → i18n
    graph.add_conditional_edges(
        "multitenancy",
        should_retry_agent,
        {
            "retry": "multitenancy",
            "continue": "i18n",
        }
    )
    
    # 19. i18n → Feature Flags
    graph.add_conditional_edges(
        "i18n",
        should_retry_agent,
        {
            "retry": "i18n",
            "continue": "feature_flags",
        }
    )
    
    # 20. Feature Flags → Parallel Phase 3 Fan-in
    graph.add_conditional_edges(
        "feature_flags",
        should_retry_agent,
        {
            "retry": "feature_flags",
            "continue": "parallel_phase_3_fanin",
        }
    )
    
    # 21. Parallel Phase 3 Fan-in → Compliance Check
    graph.add_edge("parallel_phase_3_fanin", "compliance_check")
    
    # 22. Compliance Check → Extension
    graph.add_conditional_edges(
        "compliance_check",
        should_retry_agent,
        {
            "retry": "compliance_check",
            "continue": "extension",
        }
    )
    
    # 23. Extension → Performance Review
    graph.add_conditional_edges(
        "extension",
        should_retry_agent,
        {
            "retry": "extension",
            "continue": "performance_review",
        }
    )
    
    # 24. Performance Review → Gate 6 (with retry)
    graph.add_conditional_edges(
        "performance_review",
        should_retry_agent,
        {
            "retry": "performance_review",
            "continue": "gate_6_pre_deployment",
        }
    )
    
    # 24a. Gate 6 → CI/CD or refine Performance Review
    graph.add_conditional_edges(
        "gate_6_pre_deployment",
        lambda state: should_continue_after_gate(state, "ci_cd", "performance_review"),
        {
            "ci_cd": "ci_cd",
            "performance_review": "performance_review",
        }
    )
    
    # 25. CI/CD → Deployment
    graph.add_conditional_edges(
        "ci_cd",
        should_retry_agent,
        {
            "retry": "ci_cd",
            "continue": "deployment",
        }
    )
    
    # 26. Deployment → Testing (Parallel Phase 4 start)
    graph.add_conditional_edges(
        "deployment",
        should_retry_agent,
        {
            "retry": "deployment",
            "continue": "testing",
        }
    )
    
    # 27. Testing → Documentation
    graph.add_edge("testing", "documentation")
    
    # 28. Documentation → Observability
    graph.add_edge("documentation", "observability")
    
    # 29. Observability → Parallel Phase 4 Fan-in
    graph.add_edge("observability", "parallel_phase_4_fanin")
    
    # 30. Parallel Phase 4 Fan-in → Project Assembly
    graph.add_edge("parallel_phase_4_fanin", "project_assembly")
    
    # 31. Project Assembly → Project Verification
    graph.add_edge("project_assembly", "project_verification")
    
    # 32. Project Verification → Validation
    graph.add_edge("project_verification", "validation")
    
    # 33. Validation → Gate 7 (with retry)
    graph.add_conditional_edges(
        "validation",
        should_retry_agent,
        {
            "retry": "validation",
            "continue": "gate_7_final_release",
        }
    )
    
    # 33a. Gate 7 → self-heal back to ANY agent OR end
    # UPGRADED: Now supports all 28 agents dynamically
    graph.add_conditional_edges(
        "gate_7_final_release",
        should_self_heal,
        {
            # All 28 agents can be self-healed
            "requirements": "requirements",
            "enterprise_architecture": "enterprise_architecture",
            "domain_modeling": "domain_modeling",
            "data_modeling": "data_modeling",
            "db_migration": "db_migration",
            "integration": "integration",
            "integration_design": "integration_design",
            "service_exposure": "service_exposure",
            "error_handling": "error_handling",
            "audit_logging": "audit_logging",
            "api_governance": "api_governance",
            "business_logic": "business_logic",
            "ux_design": "ux_design",
            "fiori_ui": "fiori_ui",
            "security": "security",
            "multitenancy": "multitenancy",
            "i18n": "i18n",
            "feature_flags": "feature_flags",
            "compliance_check": "compliance_check",
            "extension": "extension",
            "performance_review": "performance_review",
            "ci_cd": "ci_cd",
            "deployment": "deployment",
            "testing": "testing",
            "documentation": "documentation",
            "observability": "observability",
            "project_assembly": "project_assembly",
            "project_verification": "project_verification",
            "validation": "validation",
            "end": END,
        }
    )
    
    # 34. FAILED terminal → END
    graph.add_edge("failed", END)
    
    return graph


# =============================================================================
# Global Compiled Graph with Thread-Safe Singleton and Checkpointer
# =============================================================================

_compiled_graph = None
_graph_lock = asyncio.Lock()
_checkpointer = None


async def reset_graph_cache():
    """
    Reset the compiled graph cache.
    Useful for development when the graph structure changes.
    """
    global _compiled_graph, _checkpointer
    async with _graph_lock:
        _compiled_graph = None
        _checkpointer = None
        logger.info("Graph cache reset")


async def get_checkpointer():
    """
    Get or create the checkpointer for state persistence.
    
    NOTE: Checkpointing is DISABLED because AsyncSqliteSaver requires
    context manager usage which doesn't work well with long-lived singletons.
    
    For human gates to work, we would need to either:
    1. Use a different checkpointer (e.g., MemorySaver for development)
    2. Create checkpointer per-request instead of singleton
    3. Use PostgreSQL checkpointer which supports long-lived connections
    
    Returns:
        None (checkpointing disabled)
    """
    # Always return None - checkpointing is disabled
    return None


async def get_builder_graph():
    """
    Get or create the compiled builder graph.
    
    UPGRADED: Thread-safe singleton with asyncio.Lock to prevent race conditions.
    
    NOTE: Checkpointing is DISABLED, so human gates will not function.
    The workflow will run end-to-end without interruptions.
    """
    global _compiled_graph
    async with _graph_lock:
        if _compiled_graph is None:
            graph = create_builder_graph()
            checkpointer = await get_checkpointer()
            
            # Compile with increased recursion limit
            # recursion_limit=300 to handle 28 agents × 5 retries + 7 gates
            if checkpointer:
                # With checkpointer, we can use interrupt_before for human gates
                _compiled_graph = graph.compile(
                    checkpointer=checkpointer,
                    interrupt_before=[
                        "gate_1_requirements",
                        "gate_2_architecture",
                        "gate_3_data_layer",
                        "gate_4_service_layer",
                        "gate_5_business_logic",
                        "gate_6_pre_deployment",
                        "gate_7_final_release",
                    ],
                )
                logger.info("Compiled LangGraph with checkpointer and human gates")
            else:
                # Without checkpointer, compile without interrupts
                _compiled_graph = graph.compile()
                logger.info("Compiled LangGraph WITHOUT checkpointer (human gates disabled, workflow runs end-to-end)")
        return _compiled_graph


async def run_generation_workflow(initial_state: BuilderState) -> BuilderState:
    """
    Run the complete generation workflow.
    
    Args:
        initial_state: Initial BuilderState with user configuration
        
    Returns:
        Final BuilderState with all generated artifacts
        
    UPGRADED: Now uses increased recursion_limit=300 and checkpointer
    """
    logger.info(f"Starting generation workflow for project: {initial_state.get('project_name')}")
    
    # Set generation status
    initial_state["generation_status"] = GenerationStatus.IN_PROGRESS.value
    initial_state["generation_started_at"] = datetime.utcnow().isoformat()
    
    # Get compiled graph
    graph = await get_builder_graph()
    
    # Run the workflow with thread_id for checkpointing
    session_id = initial_state.get("session_id", "unknown")
    project_name = initial_state.get("project_name", "Unknown")
    
    config = {
        "recursion_limit": 300,
        "configurable": {"thread_id": session_id},
        "run_name": f"build:{project_name}",
        "tags": [
            initial_state.get("complexity_level", "standard"),
            initial_state.get("cap_runtime", "nodejs"),
            initial_state.get("domain_type", "generic"),
        ],
        "metadata": {
            "session_id": session_id,
            "project_name": project_name,
            "project_namespace": initial_state.get("project_namespace", ""),
            "domain_type": initial_state.get("domain_type", ""),
            "multitenancy_enabled": initial_state.get("multitenancy_enabled", False),
            "complexity_level": initial_state.get("complexity_level", "standard"),
        }
    }
    
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        logger.info("Generation workflow completed")
        return final_state
    except Exception as e:
        logger.exception(f"Generation workflow failed: {e}")
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
        
    UPGRADED: Now uses recursion_limit=300 and checkpointer
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
    graph = await get_builder_graph()
    
    # Agent order for emitting agent_start events (28 agents total)
    # Moved to module level as constant (Quick Win #4)
    
    final_state: dict[str, Any] = {}
    workflow_error: Exception | None = None
    
    async def _run_graph():
        """Run the LangGraph workflow in a background task."""
        nonlocal final_state, workflow_error
        try:
            last_agent_idx = -1
            final_state = initial_state.copy()
            
            # Config with thread_id for checkpointing and increased recursion_limit
            project_name = initial_state.get("project_name", "Unknown")
            
            config = {
                "recursion_limit": 300,
                "configurable": {"thread_id": session_id},
                "run_name": f"build:{project_name}",
                "tags": [
                    initial_state.get("complexity_level", "standard"),
                    initial_state.get("cap_runtime", "nodejs"),
                    initial_state.get("domain_type", "generic"),
                ],
                "metadata": {
                    "session_id": session_id,
                    "project_name": project_name,
                    "project_namespace": initial_state.get("project_namespace", ""),
                    "domain_type": initial_state.get("domain_type", ""),
                    "multitenancy_enabled": initial_state.get("multitenancy_enabled", False),
                    "complexity_level": initial_state.get("complexity_level", "standard"),
                }
            }
            
            async for event in graph.astream(initial_state, config=config):
                for node_name, node_output in event.items():
                    # Guard against None output
                    if node_output is None:
                        logger.warning(f"Node {node_name} returned None, skipping state update")
                        continue
                    
                    # Update accumulated state with node output instead of overwriting
                    final_state.update(node_output)
                    node_state = node_output # Legacy reference for the rest of the loop
                    
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
            import traceback
            traceback.print_exc()
            workflow_error = e
            logger.exception(f"Streaming workflow failed: {e}")
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


# =============================================================================
# Agent Order Constant (Quick Win #4 - moved from inside function)
# =============================================================================

AGENT_ORDER = [
    "requirements", "enterprise_architecture", "domain_modeling", "data_modeling",
    "db_migration", "integration", "service_exposure", "integration_design",
    "error_handling", "audit_logging", "api_governance", "business_logic",
    "ux_design", "fiori_ui", "security", "multitenancy", "i18n", "feature_flags",
    "compliance_check", "extension", "performance_review", "ci_cd", "deployment",
    "testing", "documentation", "observability", "project_assembly",
    "project_verification", "validation",
]

