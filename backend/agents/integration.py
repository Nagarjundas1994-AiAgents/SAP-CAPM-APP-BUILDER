"""
Agent: Integration

Generates external service definitions, mashups, and destination logic.

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
from backend.agents.llm_providers import get_llm_manager
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.agents.resilience import with_timeout

logger = logging.getLogger(__name__)

INTEGRATION_SYSTEM_PROMPT = """You are a senior SAP CAP integrations architect.
Generate enterprise-grade integrations for external systems like SAP S/4HANA, SuccessFactors, or custom APIs.

STRICT RULES:
1. Generate specific `.cds` models for the external services (e.g., `srv/external/{name}.cds`).
2. Generate a `srv/mashup.cds` file that projects/extends your main OData service to expose entities from the external service using `@cds.external`.
3. Generate sample handler logic in `srv/lib/destination.js` showing how to connect to the external service using `cds.connect.to()`.
4. Return ONLY valid JSON matching the format below.
5. NO markdown formatting block around the JSON.

OUTPUT FORMAT:
{
  "external_cds": [
    {
      "path": "srv/external/API_BUSINESS_PARTNER.cds",
      "content": "... external API definition ..."
    }
  ],
  "mashup_cds": {
    "path": "srv/mashup.cds",
    "content": "... extending main service ..."
  },
  "destination_js": {
    "path": "srv/lib/destination.js",
    "content": "... cds.connect.to() example ..."
  },
  "package_json_requires": {
    "API_BUSINESS_PARTNER": {
      "kind": "odata-v2",
      "model": "srv/external/API_BUSINESS_PARTNER",
      "[production]": {
        "credentials": {
          "destination": "S4HANA_BP",
          "path": "/sap/opu/odata/sap/API_BUSINESS_PARTNER"
        }
      }
    }
  }
}
"""

INTEGRATION_GENERATION_PROMPT = """Generate SAP CAP external integrations.

Project: {project_name} ({app_id})
Main Entities:
{entities_json}

Requested Integrations:
{integrations_json}

Generate the necessary CAP M files to integrate these external systems.

Respond with ONLY valid JSON."""

@with_timeout(timeout_seconds=120)  # 2 minutes for integration generation
async def integration_agent(state: BuilderState) -> dict[str, Any]:
    """
    Integration Agent
    Generates external service definitions, mashups, and destination logic.
    
    Returns partial state dict with only changed keys.
    """
    agent_name = "integration"
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

    log_progress(state, "🔌 Starting Integration Agent...")
    
    try:
        integrations = state.get("integrations", [])
        if not integrations:
            log_progress(state, "⏩ No external integrations requested. Skipping.")
            
            completed_at = datetime.utcnow().isoformat()
            duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
            
            new_retry_counts = state.get("retry_counts", {}).copy()
            new_retry_counts[agent_name] = retry_count + 1
            
            return {
                "agent_history": [{
                    "agent_name": agent_name,
                    "status": "skipped",
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

        entities = state.get("entities", [])
        
        prompt = INTEGRATION_GENERATION_PROMPT.format(
            project_name=state.get("project_name", "App"),
            app_id=state.get("project_namespace", "com.app"),
            entities_json=json.dumps(entities, indent=2),
            integrations_json=json.dumps(integrations, indent=2)
        )

        log_progress(state, "Brainstorming integration architecture with LLM...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=INTEGRATION_SYSTEM_PROMPT,
            state=state,
            required_keys=["external_cds", "mashup_cds", "package_json_requires"],
            agent_name=agent_name,
        )
        
        if not result:
            log_progress(state, "⚠️ Integration Agent failed to generate output. Continuing without integrations.")
            
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

        generated_files = []
        
        # Process external CDS files
        for ext_cds in result.get("external_cds", []):
            path = ext_cds.get("path")
            content = ext_cds.get("content")
            if path and content:
                generated_files.append({
                    "path": path,
                    "content": content,
                    "file_type": "cds"
                })
                
        # Process mashup CDS
        mashup = result.get("mashup_cds", {})
        if mashup.get("path") and mashup.get("content"):
            generated_files.append({
                "path": mashup["path"],
                "content": mashup["content"],
                "file_type": "cds"
            })
            
        # Process destination JS
        dest_js = result.get("destination_js", {})
        if dest_js.get("path") and dest_js.get("content"):
            generated_files.append({
                "path": dest_js["path"],
                "content": dest_js["content"],
                "file_type": "javascript"
            })
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, f"✅ Generated {len(result.get('external_cds', []))} external services and mashup projection.")
        
        return {
            # Agent outputs
            "artifacts_srv": generated_files,
            "integrations_cd_requires": result.get("package_json_requires", {}),
            
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
