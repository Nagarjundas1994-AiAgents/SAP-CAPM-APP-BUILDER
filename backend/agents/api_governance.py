"""
Agent: API Governance

Generates API catalog, OData versioning, and deprecation policy docs.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
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


async def api_governance_agent(state: BuilderState) -> BuilderState:
    """
    API Governance Agent - API catalog, versioning, deprecation.
    
    Generates:
    - API catalog documentation
    - Versioning strategy
    - Deprecation policy
    - Breaking change guidelines
    """
    logger.info("Starting API Governance Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "api_governance"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting API governance phase...")
    
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
        agent_name="api_governance",
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
    
    state["api_governance_spec"] = api_governance_spec
    state["artifacts_docs"] = state.get("artifacts_docs", []) + generated_files
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "api_governance",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "API governance complete.")
    return state
