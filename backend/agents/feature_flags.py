"""
Agent: Feature Flags

Generates BTP Feature Flags service config and toggle definitions.
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


FEATURE_FLAGS_SYSTEM_PROMPT = """You are a feature flag and A/B testing expert for enterprise applications.
Your task is to design feature flag strategies for gradual rollouts and experimentation.

FEATURE FLAG PRINCIPLES:
1. Toggle Types: Boolean, percentage rollout, user segment
2. Use Cases: New features, A/B testing, kill switches
3. Naming: Use descriptive names (enable_new_dashboard)
4. Default State: Usually false for new features

OUTPUT FORMAT:
Return valid JSON:
{
  "enabled": true/false,
  "flags": [
    {
      "name": "string",
      "description": "string",
      "default_value": true/false,
      "type": "boolean/percentage/segment"
    }
  ],
  "service_binding": "string or null"
}

Return ONLY valid JSON."""


FEATURE_FLAGS_PROMPT = """Design feature flags for this SAP CAP application.

Project: {project_name}
Description: {description}

Feature Flags Enabled: {feature_flags_enabled}

Tasks:
1. Identify features that benefit from gradual rollout
2. Define feature flag names and descriptions
3. Set default values (usually false for new features)
4. Configure BTP Feature Flags service binding if enabled

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=60)
async def feature_flags_agent(state: BuilderState) -> dict[str, Any]:
    """
    Feature Flags Agent - BTP Feature Flags, toggles, A/B config.
    
    Generates:
    - Feature flag definitions
    - Toggle configuration
    - A/B testing setup
    - Feature flag service binding
    """
    agent_name = "feature_flags"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Feature Flags Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "feature_flags"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting feature flags phase...")
    
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
        feature_flags_enabled = state.get("feature_flags_enabled", False)
    
        if not feature_flags_enabled:
            log_progress(state, "Feature flags not enabled, skipping...")
            feature_flags_config = {"enabled": False, "flags": []}
        else:
            # Retrieve RAG context
            rag_docs = await retrieve_for_agent("feature_flags", f"feature flags A/B testing {project_name}")
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            prompt = FEATURE_FLAGS_PROMPT.format(
                project_name=project_name,
                description=description or "No description provided",
                feature_flags_enabled=feature_flags_enabled,
            )
            
            if rag_context:
                prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
            
            log_progress(state, "Generating feature flag configuration...")
            
            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=FEATURE_FLAGS_SYSTEM_PROMPT,
                state=state,
                required_keys=["enabled", "flags"],
                max_retries=3,
                agent_name="feature_flags",
            )
            
            if result:
                feature_flags_config = result
                log_progress(state, f"✅ Defined {len(result.get('flags', []))} feature flags")
            else:
                log_progress(state, "⚠️ LLM generation failed - using minimal feature flags config")
                feature_flags_config = {
                    "enabled": True,
                    "flags": [],
                    "service_binding": None
                }
    
        state["feature_flags_config"] = feature_flags_config
        state["needs_correction"] = False
    
        # Record execution
        state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "feature_flags",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
        }]
    
        log_progress(state, "Feature flags complete.")
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