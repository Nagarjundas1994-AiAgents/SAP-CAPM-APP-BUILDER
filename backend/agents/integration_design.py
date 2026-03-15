"""
Agent: Integration Design

Designs integrations with S/4HANA BAPIs, Event Mesh, remote services, and RFC.

ARCHITECTURE IMPROVEMENTS (2026-03-15):
- Added timeout wrapper
- Proper retry counter increment
- Returns partial state
- Records agent_history
- Handles exceptions properly
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.agents.resilience import with_timeout
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


INTEGRATION_DESIGN_SYSTEM_PROMPT = """You are an SAP integration architect with expertise in S/4HANA, Event Mesh, and RFC.
Design robust integration patterns for SAP CAP applications.

INTEGRATION PATTERNS:
1. S/4HANA BAPIs: Remote function calls for business operations
2. Event Mesh: Asynchronous event-driven integration
3. OData Services: REST-based service consumption
4. RFC: Direct remote function calls
5. Webhooks: HTTP callbacks for external systems

OUTPUT FORMAT:
Return valid JSON:
{
  "remote_services": [
    {
      "name": "string",
      "type": "S4HANA|EventMesh|OData|RFC|Webhook",
      "endpoint": "string",
      "auth_type": "Basic|OAuth2|PrincipalPropagation",
      "operations": ["operation_name"]
    }
  ],
  "bapi_mappings": [
    {
      "bapi_name": "string",
      "local_entity": "string",
      "mapping": {"local_field": "bapi_field"}
    }
  ],
  "event_subscriptions": [
    {
      "event_type": "string",
      "source_system": "string",
      "handler": "string"
    }
  ],
  "integration_patterns": ["pattern_name"]
}

Return ONLY valid JSON."""


INTEGRATION_DESIGN_PROMPT = """Design integration architecture for the following SAP CAP application.

Project: {project_name}
Description: {description}

Entities: {entities_json}
Integrations Required: {integrations_json}

Tasks:
1. Design remote service definitions
2. Map BAPIs to local entities
3. Define event subscriptions
4. Select integration patterns
5. Specify authentication methods

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)  # 2 minutes for integration design
async def integration_design_agent(state: BuilderState) -> dict[str, Any]:
    """
    Integration Design Agent - S/4HANA, Event Mesh, RFC mapping.
    
    Generates:
    - Remote service definitions
    - BAPI/RFC mappings
    - Event Mesh subscriptions
    - Integration patterns
    
    Returns partial state dict with only changed keys.
    """
    agent_name = "integration_design"
    logger.info(f"Starting {agent_name} Agent")
    
    started_at = datetime.utcnow().isoformat()
    
    # =========================================================================
    # Check retry count and fail if max retries exhausted
    # =========================================================================
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
    
    log_progress(state, "Starting integration design phase...")
    
    try:
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        entities = state.get("entities", [])
        integrations = state.get("integrations", [])
        
        if not integrations:
            log_progress(state, "No integrations required - using minimal spec")
            integration_spec = {
                "remote_services": [],
                "bapi_mappings": [],
                "event_subscriptions": [],
                "integration_patterns": []
            }
        else:
            rag_docs = await retrieve_for_agent("integration_design", f"S/4HANA BAPI Event Mesh {project_name}")
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            prompt = INTEGRATION_DESIGN_PROMPT.format(
                project_name=project_name,
                description=description or "No description",
                entities_json=json.dumps(entities, indent=2),
                integrations_json=json.dumps(integrations, indent=2),
            )
            
            if rag_context:
                prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
            
            log_progress(state, f"Designing {len(integrations)} integrations...")
            
            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=INTEGRATION_DESIGN_SYSTEM_PROMPT,
                state=state,
                required_keys=["remote_services"],
                max_retries=3,
                agent_name=agent_name,
            )
            
            if result:
                integration_spec = result
                log_progress(state, f"✅ Designed {len(result.get('remote_services', []))} remote services")
            else:
                log_progress(state, "⚠️ LLM generation failed - using minimal spec")
                integration_spec = {
                    "remote_services": [],
                    "bapi_mappings": [],
                    "event_subscriptions": [],
                    "integration_patterns": []
                }
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "Integration design complete.")
        
        return {
            # Agent outputs
            "integration_spec": integration_spec,
            
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with exception: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": str(e),
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": True,
            
            # Validation errors
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
