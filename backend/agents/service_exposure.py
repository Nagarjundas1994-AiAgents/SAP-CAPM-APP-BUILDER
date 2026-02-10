"""
Agent 3: CAP Service Exposure Agent

Generates OData service definitions, projections, actions, functions,
and security annotations for SAP CAP services.

Uses LLM to generate production-quality service definitions with fallback to templates.
"""

import logging
import json
import re
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
    ODataVersion,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

SERVICE_SYSTEM_PROMPT = """You are an expert SAP CAP (Cloud Application Programming Model) service architect.
Your task is to generate production-ready CDS service definitions and Fiori annotations.

STRICT RULES:
1. Use correct CDS service syntax: service <Name> @(path: '/endpoint') { ... }
2. Use proper "using" statements to reference db schema entities
3. Use projections: "entity X as projection on db.X"
4. Add @odata.draft.enabled for draft-capable entities
5. Define custom actions/functions bound to entities where business rules exist
6. Generate complete Fiori annotations: UI.SelectionFields, UI.LineItem, UI.HeaderInfo, UI.Facets, UI.FieldGroup
7. Use proper annotation syntax with @ prefixes
8. Follow SAP Fiori Elements best practices for List Report and Object Page patterns
9. Add @Capabilities annotations for restricting operations where appropriate
10. Only project entity fields that exist in the schema

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "service_cds": "... full content of srv/service.cds ...",
  "annotations_cds": "... full content of srv/annotations.cds ..."
}

Do NOT include markdown code fences in the JSON values. Return ONLY the JSON object."""


SERVICE_GENERATION_PROMPT = """Generate srv/service.cds and srv/annotations.cds for this SAP CAP project.

Project Name: {project_name}
Project Namespace: {namespace}
OData Version: {odata_version}
Draft Enabled: {draft_enabled}

Schema (db/schema.cds) that was already generated:
```
{schema_content}
```

Entities:
{entities_json}

Relationships:
{relationships_json}

Business Rules:
{business_rules_json}

Requirements for service.cds:
1. Import from '../db/schema' using the namespace '{namespace}'
2. Set OData protocol version annotation
3. Create a service named "{service_name}" at path '/{service_path}'
4. Create projections for ALL entities
5. Add @odata.draft.enabled where appropriate
6. Add custom actions/functions for business rules (e.g., "action confirmOrder() returns String;")

Requirements for annotations.cds:
1. Import from './service'
2. For EACH entity, add comprehensive Fiori annotations:
   - UI.SelectionFields: filterable String fields (max 4)
   - UI.LineItem: visible columns in list (max 8), with @UI.Importance
   - UI.HeaderInfo: TypeName, TypeNamePlural, Title, Description
   - UI.Facets: at least GeneralInfo and any child-entity sections
   - UI.FieldGroup#GeneralInfo: all non-key fields
   - @Common.Label for each field with a human-readable label

Respond with ONLY valid JSON."""


# =============================================================================
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


def _parse_llm_response(response_text: str) -> dict | None:
    """Parse LLM JSON response, handling markdown code fences."""
    try:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None


# =============================================================================
# Template Fallback Functions
# =============================================================================

def generate_service_cds(state: BuilderState) -> str:
    """Generate the main srv/service.cds file (template fallback)."""
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    odata_version = state.get("odata_version", ODataVersion.V4.value)
    draft_enabled = state.get("draft_enabled", True)
    
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_name = f"{service_name}Service"
    
    lines = []
    lines.append(f"using {{ {namespace} as db }} from '../db/schema';")
    lines.append("")
    
    if odata_version == ODataVersion.V2.value:
        lines.append("@protocol: 'odata-v2'")
    else:
        lines.append("@protocol: 'odata-v4'")
    
    lines.append(f"service {service_name} @(path: '/{project_name.lower().replace(' ', '-')}') {{")
    lines.append("")
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        if draft_enabled:
            lines.append(f"    @odata.draft.enabled")
        lines.append(f"    entity {entity_name} as projection on db.{entity_name};")
        lines.append("")
    
    lines.append("}")
    return "\n".join(lines)


def generate_annotations_cds(state: BuilderState) -> str:
    """Generate Fiori annotations for the service (template fallback)."""
    entities = state.get("entities", [])
    
    lines = ["// Fiori Elements Annotations", "", "using from './service';", ""]
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        
        key_field = None
        label_fields = []
        for field in fields:
            if field.get("key"):
                key_field = field.get("name", "")
            elif field.get("type") in ["String", "LargeString"]:
                label_fields.append(field.get("name", ""))
        
        lines.append(f"annotate {entity_name} with @(")
        
        if label_fields:
            lines.append("    UI.SelectionFields: [")
            for i, field in enumerate(label_fields[:3]):
                comma = "," if i < min(len(label_fields), 3) - 1 else ""
                lines.append(f"        {field}{comma}")
            lines.append("    ],")
        
        lines.append("    UI.LineItem: [")
        for i, field in enumerate(fields[:6]):
            fname = field.get("name", "")
            comma = "," if i < min(len(fields), 6) - 1 else ""
            lines.append(f"        {{ Value: {fname} }}{comma}")
        lines.append("    ],")
        
        if key_field and label_fields:
            lines.append("    UI.HeaderInfo: {")
            lines.append(f"        TypeName: '{entity_name}',")
            lines.append(f"        TypeNamePlural: '{entity_name}s',")
            lines.append(f"        Title: {{ Value: {label_fields[0]} }},")
            desc = label_fields[1] if len(label_fields) > 1 else key_field
            lines.append(f"        Description: {{ Value: {desc} }}")
            lines.append("    },")
        
        lines.append("    UI.Facets: [")
        lines.append("        {")
        lines.append("            $Type: 'UI.ReferenceFacet',")
        lines.append(f"            Label: 'General Information',")
        lines.append("            Target: '@UI.FieldGroup#GeneralInfo'")
        lines.append("        }")
        lines.append("    ],")
        
        lines.append("    UI.FieldGroup#GeneralInfo: {")
        lines.append("        Data: [")
        for i, field in enumerate(fields):
            fname = field.get("name", "")
            comma = "," if i < len(fields) - 1 else ""
            lines.append(f"            {{ Value: {fname} }}{comma}")
        lines.append("        ]")
        lines.append("    }")
        lines.append(");")
        lines.append("")
    
    return "\n".join(lines)


# =============================================================================
# Main Agent Function
# =============================================================================

async def service_exposure_agent(state: BuilderState) -> BuilderState:
    """
    CAP Service Exposure Agent (LLM-Driven)
    
    Uses LLM to generate production-quality service definitions and annotations.
    Falls back to template-based generation if LLM fails.
    
    Generates:
    1. srv/service.cds - Main service definition
    2. srv/annotations.cds - Fiori UI annotations
    3. srv/index.cds - Service index
    
    Returns updated state with generated service files.
    """
    logger.info("Starting Service Exposure Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "service_exposure"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting service exposure phase...")
    
    entities = state.get("entities", [])
    if not entities:
        log_progress(state, "Error: No entities found for service exposure.")
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    odata_version = state.get("odata_version", ODataVersion.V4.value)
    draft_enabled = state.get("draft_enabled", True)
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])
    provider = state.get("llm_provider")
    
    # Get schema content from previously generated artifacts
    schema_content = ""
    for artifact in state.get("artifacts_db", []):
        if artifact.get("path") == "db/schema.cds":
            schema_content = artifact.get("content", "")
            break
    
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_name = f"{service_name}Service"
    service_path = project_name.lower().replace(" ", "-")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven generation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        prompt = SERVICE_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            odata_version=odata_version,
            draft_enabled=draft_enabled,
            schema_content=schema_content or "(schema not yet available)",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
            service_name=service_name,
            service_path=service_path,
        )
        
        log_progress(state, "Calling LLM for service definition generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=SERVICE_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("service_cds"):
            service_content = parsed["service_cds"]
            
            if "service" in service_content.lower() and "projection" in service_content.lower():
                generated_files.append({
                    "path": "srv/service.cds",
                    "content": service_content,
                    "file_type": "cds",
                })
                log_progress(state, "LLM-generated service definition accepted.")
                
                if parsed.get("annotations_cds"):
                    generated_files.append({
                        "path": "srv/annotations.cds",
                        "content": parsed["annotations_cds"],
                        "file_type": "cds",
                    })
                    log_progress(state, "LLM-generated annotations accepted.")
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required service elements. Falling back.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for service exposure: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        try:
            log_progress(state, "Generating srv/service.cds via template fallback...")
            service_content = generate_service_cds(state)
            generated_files.append({
                "path": "srv/service.cds",
                "content": service_content,
                "file_type": "cds",
            })
        except Exception as e:
            logger.error(f"Failed to generate service.cds: {e}")
            errors.append({
                "agent": "service_exposure",
                "code": "SERVICE_GENERATION_ERROR",
                "message": f"Failed to generate service: {str(e)}",
                "field": None,
                "severity": "error",
            })
        
        try:
            annotations_content = generate_annotations_cds(state)
            generated_files.append({
                "path": "srv/annotations.cds",
                "content": annotations_content,
                "file_type": "cds",
            })
        except Exception as e:
            logger.error(f"Failed to generate annotations.cds: {e}")
    
    # ==========================================================================
    # Generate index.cds (always template - trivial file)
    # ==========================================================================
    index_content = """// Service Layer Index
using from './service';
using from './annotations';
"""
    generated_files.append({
        "path": "srv/index.cds",
        "content": index_content,
        "file_type": "cds",
    })
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_srv"] = state.get("artifacts_srv", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "service_exposure",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Service exposure phase complete ({generation_method}).")
    logger.info(f"Service Exposure Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state


