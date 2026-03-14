"""
Agent: Audit Logging

Generates @changelog annotations, history entities, and audit trail CDS.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


AUDIT_LOGGING_SYSTEM_PROMPT = """You are an audit trail and compliance logging expert for enterprise applications.
Your task is to design comprehensive audit logging with @changelog annotations and history tracking.

AUDIT LOGGING PRINCIPLES:
1. @changelog Annotation: Automatically track changes to entities
2. History Entities: Separate tables for audit trail
3. Change Tracking: Who, what, when for all modifications
4. Retention Policy: Define how long to keep audit logs
5. Compliance: Meet regulatory requirements (SOX, GDPR, etc.)

OUTPUT FORMAT:
Return valid JSON:
{
  "changelog_entities": [
    {
      "entity": "string",
      "fields_tracked": ["field1", "field2"],
      "retention_days": 365
    }
  ],
  "audit_trail_config": {
    "enabled": true,
    "track_user": true,
    "track_timestamp": true,
    "track_changes": true
  },
  "history_retention_days": 365
}

Return ONLY valid JSON."""


AUDIT_LOGGING_PROMPT = """Design an audit logging strategy for this SAP CAP application.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Tasks:
1. Identify entities that need @changelog annotations
2. Define which fields should be tracked
3. Set retention policies based on compliance requirements
4. Configure audit trail settings

Respond with ONLY valid JSON."""


async def audit_logging_agent(state: BuilderState) -> BuilderState:
    """
    Audit Logging Agent - @changelog, history entities.
    
    Generates:
    - @changelog annotations
    - History/audit trail entities
    - Change tracking configuration
    """
    logger.info("Starting Audit Logging Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "audit_logging"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting audit logging phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    entities = state.get("entities", [])
    
    if not entities:
        log_progress(state, "No entities found - using minimal audit config")
        audit_logging_spec = {
            "changelog_entities": [],
            "audit_trail_config": {},
            "history_retention_days": 365
        }
    else:
        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("audit_logging", f"SAP CAP @changelog audit trail {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = AUDIT_LOGGING_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            entities_json=json.dumps(entities[:10], indent=2) if entities else "[]",
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, f"Analyzing {len(entities)} entities for audit requirements...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=AUDIT_LOGGING_SYSTEM_PROMPT,
            state=state,
            required_keys=["changelog_entities", "audit_trail_config"],
            max_retries=3,
            agent_name="audit_logging",
        )
        
        if result:
            audit_logging_spec = result
            log_progress(state, f"✅ Configured @changelog for {len(result.get('changelog_entities', []))} entities")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal audit config")
            audit_logging_spec = {
                "changelog_entities": [],
                "audit_trail_config": {"enabled": True},
                "history_retention_days": 365
            }
    
    state["audit_logging_spec"] = audit_logging_spec
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "audit_logging",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Audit logging complete.")
    return state
