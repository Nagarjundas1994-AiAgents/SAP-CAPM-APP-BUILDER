"""
Agent: Multitenancy

Generates cds-mtxs config, tenant onboarding API, HANA isolation.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


MULTITENANCY_SYSTEM_PROMPT = """You are an SAP BTP multitenancy and cds-mtxs expert.
Your task is to design a comprehensive multitenancy strategy with tenant isolation, onboarding, and upgrade management.

MULTITENANCY PRINCIPLES:
1. Tenant Isolation: Schema-based (HANA) or database-based
2. cds-mtxs: SAP's multitenancy extension service
3. Tenant Onboarding: Automated provisioning API
4. Tenant Upgrade: Zero-downtime schema upgrades
5. Tenant Management: Subscription lifecycle

OUTPUT FORMAT:
Return valid JSON:
{
  "enabled": true/false,
  "mtxs_enabled": true/false,
  "tenant_isolation": "schema/database",
  "onboarding_api": "string",
  "tenant_upgrade_strategy": "string",
  "mtxs_config": {
    "provisioning": {},
    "extensibility": {}
  }
}

Return ONLY valid JSON."""


MULTITENANCY_PROMPT = """Design a multitenancy strategy for this SAP CAP application.

Project: {project_name}
Description: {description}

Multitenancy Enabled: {multitenancy_enabled}

Tasks:
1. Configure cds-mtxs if multitenancy is enabled
2. Define tenant isolation strategy (schema-based recommended for HANA)
3. Design tenant onboarding API
4. Plan tenant upgrade strategy
5. Configure tenant management

Respond with ONLY valid JSON."""


async def multitenancy_agent(state: BuilderState) -> BuilderState:
    """
    Multitenancy Agent - cds-mtxs, tenant onboarding, HANA isolation.
    
    Generates:
    - cds-mtxs configuration
    - Tenant onboarding API
    - HANA schema isolation
    - Tenant upgrade scripts
    """
    logger.info("Starting Multitenancy Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "multitenancy"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting multitenancy phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    multitenancy_enabled = state.get("multitenancy_enabled", False)
    
    if not multitenancy_enabled:
        log_progress(state, "Multitenancy not enabled, skipping...")
        multitenancy_config = {"enabled": False}
    else:
        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("multitenancy", f"SAP CAP cds-mtxs multitenancy {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = MULTITENANCY_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            multitenancy_enabled=multitenancy_enabled,
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, "Generating multitenancy configuration...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=MULTITENANCY_SYSTEM_PROMPT,
            state=state,
            required_keys=["enabled", "tenant_isolation"],
            max_retries=3,
            agent_name="multitenancy",
        )
        
        if result:
            multitenancy_config = result
            log_progress(state, f"✅ Configured {result.get('tenant_isolation')} tenant isolation")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal multitenancy config")
            multitenancy_config = {
                "enabled": True,
                "mtxs_enabled": True,
                "tenant_isolation": "schema",
                "onboarding_api": "/mtx/v1/provisioning/tenant"
            }
    
    state["multitenancy_config"] = multitenancy_config
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "multitenancy",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Multitenancy complete.")
    return state
