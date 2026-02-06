"""
Agent 3: CAP Service Exposure Agent

Generates OData service definitions, projections, actions, functions,
and security annotations for SAP CAP services.
"""

import logging
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
    ODataVersion,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Service Generation Templates
# =============================================================================

def generate_service_cds(state: BuilderState) -> str:
    """Generate the main srv/service.cds file."""
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    odata_version = state.get("odata_version", ODataVersion.V4.value)
    draft_enabled = state.get("draft_enabled", True)
    
    # Service name from project name
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_name = f"{service_name}Service"
    
    lines = []
    
    # Using statements
    lines.append(f"using {{ {namespace} as db }} from '../db/schema';")
    lines.append("")
    
    # OData version annotation
    if odata_version == ODataVersion.V2.value:
        lines.append("@protocol: 'odata-v2'")
    else:
        lines.append("@protocol: 'odata-v4'")
    
    # Service declaration
    lines.append(f"service {service_name} @(path: '/{project_name.lower().replace(' ', '-')}') {{")
    lines.append("")
    
    # Entity projections
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        
        # Add draft annotation if enabled
        if draft_enabled:
            lines.append(f"    @odata.draft.enabled")
        
        # Add readonly for entities without key fields that allow modification
        lines.append(f"    entity {entity_name} as projection on db.{entity_name};")
        lines.append("")
    
    # Close service
    lines.append("}")
    
    return "\n".join(lines)


def generate_actions_cds(state: BuilderState) -> str | None:
    """Generate custom actions and functions if business rules require them."""
    business_rules = state.get("business_rules", [])
    
    if not business_rules:
        return None
    
    lines = []
    lines.append("// Custom Actions and Functions")
    lines.append("")
    
    for rule in business_rules:
        rule_name = rule.get("name", "customAction")
        rule_type = rule.get("rule_type", "")
        entity = rule.get("entity", "")
        description = rule.get("description", "")
        
        if rule_type in ["validation", "calculation"]:
            # Generate action for entity-bound operations
            lines.append(f"    // {description}")
            lines.append(f"    action {rule_name}() returns String;")
            lines.append("")
    
    return "\n".join(lines) if len(lines) > 2 else None


def generate_annotations_cds(state: BuilderState) -> str:
    """Generate Fiori annotations for the service."""
    entities = state.get("entities", [])
    fiori_main_entity = state.get("fiori_main_entity", "")
    
    lines = []
    lines.append("// Fiori Elements Annotations")
    lines.append("")
    lines.append("using from './service';")
    lines.append("")
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        
        # Determine key field and label fields
        key_field = None
        label_fields = []
        
        for field in fields:
            field_name = field.get("name", "")
            if field.get("key"):
                key_field = field_name
            elif field.get("type") in ["String", "LargeString"]:
                label_fields.append(field_name)
        
        # UI annotations
        lines.append(f"annotate {entity_name} with @(")
        
        # Selection Fields (for filters)
        if label_fields:
            lines.append("    UI.SelectionFields: [")
            for i, field in enumerate(label_fields[:3]):
                comma = "," if i < min(len(label_fields), 3) - 1 else ""
                lines.append(f"        {field}{comma}")
            lines.append("    ],")
        
        # Line Item (table columns)
        lines.append("    UI.LineItem: [")
        for i, field in enumerate(fields[:6]):  # Show first 6 fields
            field_name = field.get("name", "")
            comma = "," if i < min(len(fields), 6) - 1 else ""
            lines.append(f"        {{ Value: {field_name} }}{comma}")
        lines.append("    ],")
        
        # Header Info
        if key_field and label_fields:
            lines.append("    UI.HeaderInfo: {")
            lines.append(f"        TypeName: '{entity_name}',")
            lines.append(f"        TypeNamePlural: '{entity_name}s',")
            if label_fields:
                lines.append(f"        Title: {{ Value: {label_fields[0]} }},")
            if len(label_fields) > 1:
                lines.append(f"        Description: {{ Value: {label_fields[1]} }}")
            else:
                lines.append(f"        Description: {{ Value: {key_field} }}")
            lines.append("    },")
        
        # Facets for Object Page
        lines.append("    UI.Facets: [")
        lines.append("        {")
        lines.append("            $Type: 'UI.ReferenceFacet',")
        lines.append(f"            Label: 'General Information',")
        lines.append("            Target: '@UI.FieldGroup#GeneralInfo'")
        lines.append("        }")
        lines.append("    ],")
        
        # Field Group
        lines.append("    UI.FieldGroup#GeneralInfo: {")
        lines.append("        Data: [")
        for i, field in enumerate(fields):
            field_name = field.get("name", "")
            comma = "," if i < len(fields) - 1 else ""
            lines.append(f"            {{ Value: {field_name} }}{comma}")
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
    CAP Service Exposure Agent
    
    Generates:
    1. srv/service.cds - Main service definition
    2. srv/annotations.cds - Fiori UI annotations
    3. srv/index.cds - Service index
    
    Returns updated state with generated service files.
    """
    logger.info("Starting Service Exposure Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "service_exposure"
    state["updated_at"] = now
    
    # Check prerequisites
    entities = state.get("entities", [])
    if not entities:
        errors.append({
            "agent": "service_exposure",
            "code": "NO_ENTITIES",
            "message": "No entities to expose as services",
            "field": "entities",
            "severity": "error",
        })
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    # ==========================================================================
    # Generate service.cds
    # ==========================================================================
    try:
        service_content = generate_service_cds(state)
        generated_files.append({
            "path": "srv/service.cds",
            "content": service_content,
            "file_type": "cds",
        })
        logger.info("Generated srv/service.cds")
    except Exception as e:
        logger.error(f"Failed to generate service.cds: {e}")
        errors.append({
            "agent": "service_exposure",
            "code": "SERVICE_GENERATION_ERROR",
            "message": f"Failed to generate service: {str(e)}",
            "field": None,
            "severity": "error",
        })
    
    # ==========================================================================
    # Generate annotations.cds
    # ==========================================================================
    try:
        annotations_content = generate_annotations_cds(state)
        generated_files.append({
            "path": "srv/annotations.cds",
            "content": annotations_content,
            "file_type": "cds",
        })
        logger.info("Generated srv/annotations.cds")
    except Exception as e:
        logger.error(f"Failed to generate annotations.cds: {e}")
    
    # ==========================================================================
    # Generate index.cds
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
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "service_exposure",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Service Exposure Agent completed. Generated {len(generated_files)} files.")
    
    return state
