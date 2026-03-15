"""
Agent: Audit Logging

Generates @changelog annotations, history entities, and audit trail CDS.
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


@with_timeout(timeout_seconds=120)
async def audit_logging_agent(state: BuilderState) -> dict[str, Any]:
    """
    Audit Logging Agent - @changelog, history entities.
    
    Generates:
    - @changelog annotations
    - History/audit trail entities
    - Change tracking configuration
    """
    agent_name = "audit_logging"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Audit Logging Agent")
    log_progress(state, "Starting audit logging phase...")
    
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
                agent_name=agent_name,
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
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "Audit logging complete.")
        
        return {
            "audit_logging_spec": audit_logging_spec,
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
