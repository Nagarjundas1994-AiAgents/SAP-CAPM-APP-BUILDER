import json
import logging
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.llm_providers import get_llm_manager
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry

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

async def integration_agent(state: BuilderState) -> BuilderState:
    """
    Integration Agent
    Generates external service definitions, mashups, and destination logic.
    """
    log_progress(state, "🔌 Starting Integration Agent...")
    
    integrations = state.get("integrations", [])
    if not integrations:
        log_progress(state, "⏩ No external integrations requested. Skipping.")
        return state

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
        required_keys=["external_cds", "mashup_cds", "package_json_requires"]
    )
    
    if not result:
        log_progress(state, "⚠️ Integration Agent failed to generate output. Continuing without integrations.")
        return state

    generated_files = state.get("artifacts_srv", [])
    
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
        
    # We need to save the package.json requires block so the deployment config agent can merge it
    state["integrations_cd_requires"] = result.get("package_json_requires", {})

    state["artifacts_srv"] = generated_files
    
    log_progress(state, f"✅ Generated {len(result.get('external_cds', []))} external services and mashup projection.")
    return state
