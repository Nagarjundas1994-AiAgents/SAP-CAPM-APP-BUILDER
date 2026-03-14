"""
Agent: Integration Design

Designs integrations with S/4HANA BAPIs, Event Mesh, remote services, and RFC.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
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


async def integration_design_agent(state: BuilderState) -> BuilderState:
    """
    Integration Design Agent - S/4HANA, Event Mesh, RFC mapping.
    
    Generates:
    - Remote service definitions
    - BAPI/RFC mappings
    - Event Mesh subscriptions
    - Integration patterns
    """
    logger.info("Starting Integration Design Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "integration_design"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting integration design phase...")
    
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
            agent_name="integration_design",
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
    
    state["integration_spec"] = integration_spec
    state["needs_correction"] = False
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "integration_design",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Integration design complete.")
    return state
