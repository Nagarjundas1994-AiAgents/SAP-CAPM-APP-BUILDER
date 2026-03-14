"""
Agent: Feature Flags

Generates BTP Feature Flags service config and toggle definitions.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

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


async def feature_flags_agent(state: BuilderState) -> BuilderState:
    """
    Feature Flags Agent - BTP Feature Flags, toggles, A/B config.
    
    Generates:
    - Feature flag definitions
    - Toggle configuration
    - A/B testing setup
    - Feature flag service binding
    """
    logger.info("Starting Feature Flags Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "feature_flags"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting feature flags phase...")
    
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
    return state
