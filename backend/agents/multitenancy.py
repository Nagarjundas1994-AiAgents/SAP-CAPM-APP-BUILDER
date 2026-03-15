"""
Agent: Multitenancy

Generates cds-mtxs config, tenant onboarding API, HANA isolation.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent
from backend.agents.resilience import with_timeout

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


@with_timeout(timeout_seconds=120)
async def multitenancy_agent(state: BuilderState) -> dict[str, Any]:
    """
    Multitenancy Agent - cds-mtxs, tenant onboarding, HANA isolation.
    
    Generates:
    - cds-mtxs configuration
    - Tenant onboarding API
    - HANA schema isolation
    - Tenant upgrade scripts
    """
    agent_name = "multitenancy"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Multitenancy Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "multitenancy"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting multitenancy phase...")
    
    # Check retry count
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exhausted")
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        return {
            "agent_failed": True,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": f"Max retries ({max_retries}) exhausted",
                "logs": None,
            }],
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }
    
    try:
    
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
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
    
        return {
        "agent_history": [{
            "agent_name": agent_name,
            "status": "completed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": None,
            "logs": state.get("current_logs", []),
        }],
        "retry_counts": new_retry_counts,
        "needs_correction": False,
        "current_agent": agent_name,
        "updated_at": completed_at,
        }


    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with error: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "error": str(e),
            "logs": None,
        }],
        "retry_counts": new_retry_counts,
        "needs_correction": True,
        "validation_errors": [{
            "agent": agent_name,
            "code": "AGENT_ERROR",
            "message": str(e),
            "field": None,
            "severity": "error",
        }],
        "current_agent": agent_name,
        "updated_at": completed_at,
    }