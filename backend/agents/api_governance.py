"""
Agent: API Governance

Generates API catalog, OData versioning, and deprecation policy docs.
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


API_GOVERNANCE_SYSTEM_PROMPT = """You are an API governance and versioning expert for enterprise OData services.
Your task is to design API governance policies including versioning, deprecation, and breaking change management.

API GOVERNANCE PRINCIPLES:
1. Versioning Strategy: Path-based (/v1/, /v2/) or header-based
2. Deprecation Policy: Notice period before removing endpoints
3. Breaking Changes: Clear guidelines on what constitutes a breaking change
4. API Catalog: Comprehensive documentation of all endpoints
5. Backward Compatibility: Maintain compatibility across versions

OUTPUT FORMAT:
Return valid JSON:
{
  "api_version": "v1",
  "versioning_strategy": "path-based/header-based",
  "deprecation_policy": "string",
  "breaking_changes": [
    {
      "type": "string",
      "example": "string",
      "mitigation": "string"
    }
  ],
  "api_catalog_markdown": "string (full markdown content for API_CATALOG.md)"
}

Return ONLY valid JSON."""


API_GOVERNANCE_PROMPT = """Design an API governance strategy for this SAP CAP OData application.

Project: {project_name}
Description: {description}

Services:
{services_json}

Entities:
{entities_json}

Tasks:
1. Define versioning strategy (path-based recommended)
2. Set deprecation policy (e.g., 6 months notice)
3. Document breaking change guidelines
4. Generate comprehensive API catalog markdown

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)
async def api_governance_agent(state: BuilderState) -> dict[str, Any]:
    """
    API Governance Agent - API catalog, versioning, deprecation.
    
    Generates:
    - API catalog documentation
    - Versioning strategy
    - Deprecation policy
    - Breaking change guidelines
    """
    agent_name = "api_governance"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting API Governance Agent")
    log_progress(state, "Starting API governance phase...")
    
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
        services = state.get("services", [])
        entities = state.get("entities", [])
        
        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("api_governance", f"OData API versioning governance {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = API_GOVERNANCE_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            services_json=json.dumps(services[:5], indent=2) if services else "[]",
            entities_json=json.dumps(entities[:5], indent=2) if entities else "[]",
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, "Generating API governance policies...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=API_GOVERNANCE_SYSTEM_PROMPT,
            state=state,
            required_keys=["api_version", "versioning_strategy"],
            max_retries=3,
            agent_name=agent_name,
        )
        
        if result:
            api_governance_spec = result
            api_catalog_content = result.get("api_catalog_markdown", "# API Catalog\n\nNo services defined.")
            log_progress(state, f"✅ Defined versioning strategy: {result.get('versioning_strategy')}")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal API governance")
            api_governance_spec = {
                "api_version": "v1",
                "versioning_strategy": "path-based",
                "deprecation_policy": "6 months notice",
                "breaking_changes": []
            }
            api_catalog_content = f"""# API Catalog - {project_name}

        ## Version: v1

        ### Services
        {chr(10).join(f"- {s.get('name', 'Service')}: /odata/v4/{s.get('name', 'main').lower()}" for s in services[:5])}

        ### Versioning Strategy
        Path-based versioning (e.g., /v1/, /v2/)

        ### Deprecation Policy
        6 months notice before removing deprecated endpoints.
        """
        
        # Generate API catalog doc
        generated_files = [{
            "path": "docs/API_CATALOG.md",
            "content": api_catalog_content,
            "file_type": "md"
        }]
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "API governance complete.")
        
        return {
            "api_governance_spec": api_governance_spec,
            "artifacts_docs": generated_files,
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
