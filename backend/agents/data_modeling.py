"""
Agent 2: CAP Data Modeling Agent

Generates complete, SAP-compliant CDS data models including entities, types,
associations, compositions, aspects, and annotations.

Uses LLM to generate production-quality CDS schemas with fallback to templates.
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
    RelationshipDefinition,
    GeneratedFile,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

DATA_MODELING_SYSTEM_PROMPT = """You are an expert SAP CAP (Cloud Application Programming Model) data architect.
Your task is to generate complete, production-ready, enterprise-grade CDS (Core Data Services) schema files.

STRICT RULES:
1. ONLY use official SAP CDS syntax and patterns.
2. Naming: PascalCase for entities, camelCase for fields. Namespace must be consistent.
3. Standard Aspects: 
   - Use 'cuid' for all primary entities.
   - Use 'managed' for change tracking.
   - Use 'temporal' for data that needs versioning.
4. Types: String, Integer, Decimal, Date, DateTime, Boolean, UUID, LargeString.
5. Value Helps & Enums:
   - Use CDS Enums for fields with fixed values (e.g. type Status : String enum { New; InProcess; Closed; }).
   - Define 'CodeList' entities for more dynamic value helps.
6. Relationships:
   - Use 'Composition of many' for internal sub-entities (e.g. Order -> OrderItems).
   - Use 'Association to' for external references.
7. Annotations:
   - Mandatory: @title, @description.
   - Functional: @readonly, @mandatory, @assert.range, @assert.format.
   - UI Prep: @Common.Text, @Common.ValueList.
8. Semantics: Use @Semantics.amount.currencyCode: 'currency' and @Semantics.currencyCode: true.

OUTPUT FORMAT:
Return a JSON object:
{
  "schema_cds": "... CDS content ...",
  "sample_data": [
    {"filename": "db/data/namespace-Entity.csv", "content": "... CSV data (5-10 rows) ..."}
  ]
}
Return ONLY the JSON."""


SCHEMA_GENERATION_PROMPT = """Generate a complete db/schema.cds file and realistic sample CSV data for a high-quality SAP CAP project.

Project: {project_name} ({namespace})
Description: {description}

Entities: {entities_json}
Relationships: {relationships_json}
Rules: {business_rules_json}

Requirements:
1. Namespace: {namespace}
2. Include 'using { cuid, managed } from '@sap/cds/common';'
3. Use enums for status/priority fields.
4. Add @title and @description to EVERY field.
5. Use '@changelog' or 'managed' aspects for audit trails.
6. For associations, ensure the target entity exists in the model.
7. Generate 5-10 rows of high-quality sample data per entity.
8. Use semicolons for CSV separators.

The output must be a valid SAP CAP project structure for the 'db' layer."""


# =============================================================================
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


# =============================================================================
# CDS Type Mappings
# =============================================================================

CDS_TYPE_MAP = {
    "String": "String",
    "Integer": "Integer",
    "Decimal": "Decimal",
    "Boolean": "Boolean",
    "Date": "Date",
    "DateTime": "DateTime",
    "Time": "Time",
    "UUID": "UUID",
    "LargeString": "LargeString",
    "LargeBinary": "LargeBinary",
    "Int16": "Int16",
    "Int32": "Int32",
    "Int64": "Int64",
    "Double": "Double",
}


# =============================================================================
# Template Functions
# =============================================================================

def generate_field_definition(field: dict[str, Any]) -> str:
    """Generate CDS field definition from field dict."""
    name = field.get("name", "")
    field_type = field.get("type", "String")
    
    # Map to CDS type
    cds_type = CDS_TYPE_MAP.get(field_type, "String")
    
    # Add length/precision
    if field_type == "String" and field.get("length"):
        cds_type = f"String({field['length']})"
    elif field_type == "Decimal":
        precision = field.get("precision", 10)
        scale = field.get("scale", 2)
        cds_type = f"Decimal({precision}, {scale})"
    
    # Build annotations
    annotations = []
    if field.get("key"):
        annotations.append("key")
    
    # Add other annotations
    field_annotations = field.get("annotations", {})
    if field_annotations.get("title"):
        annotations.append(f"@title: '{field_annotations['title']}'")
    if field_annotations.get("description"):
        annotations.append(f"@description: '{field_annotations['description']}'")
    if field_annotations.get("readonly"):
        annotations.append("@readonly")
    if field_annotations.get("mandatory"):
        annotations.append("@mandatory")
    
    # Add domain-specific annotations
    if name.lower() in ["price", "amount", "total", "netamount", "taxamount"]:
        annotations.append("@Semantics.amount.currencyCode: 'currency'")
    if name.lower() == "currency":
        annotations.append("@Semantics.currencyCode: true")
    
    # Build field line
    parts = []
    if "key" in annotations:
        parts.append("key")
        annotations.remove("key")
    
    parts.append(name)
    parts.append(":")
    parts.append(cds_type)
    
    # Add nullability
    if not field.get("nullable", True) and not field.get("key"):
        parts.append("not null")
    
    # Add default
    if field.get("default"):
        parts.append(f"default {field['default']}")
    
    # Build annotation prefix
    annotation_str = " ".join(annotations)
    if annotation_str:
        return f"    {annotation_str}\n    {' '.join(parts)};"
    
    return f"    {' '.join(parts)};"


def generate_entity_cds(entity: EntityDefinition, relationships: list[RelationshipDefinition]) -> str:
    """Generate CDS entity definition."""
    name = entity.get("name", "Entity")
    description = entity.get("description", "")
    fields = entity.get("fields", [])
    aspects = entity.get("aspects", [])
    
    lines = []
    
    # Entity description
    if description:
        lines.append(f"/**")
        lines.append(f" * {description}")
        lines.append(f" */")
    
    # Entity declaration with aspects
    if aspects:
        aspect_str = ", ".join(aspects)
        lines.append(f"entity {name} : {aspect_str} {{")
    else:
        lines.append(f"entity {name} {{")
    
    # Fields
    for field in fields:
        lines.append(generate_field_definition(field))
    
    # Add associations and compositions
    entity_relationships = [r for r in relationships if r.get("source_entity") == name]
    for rel in entity_relationships:
        rel_name = rel.get("name", "")
        target = rel.get("target_entity", "")
        rel_type = rel.get("type", "association")
        cardinality = rel.get("cardinality", "n:1")
        
        if rel_type == "composition":
            if cardinality in ["1:n", "n:m"]:
                lines.append(f"    {rel_name} : Composition of many {target};")
            else:
                lines.append(f"    {rel_name} : Composition of {target};")
        else:  # association
            if cardinality in ["1:n", "n:m"]:
                lines.append(f"    {rel_name} : Association to many {target};")
            else:
                lines.append(f"    {rel_name} : Association to {target};")
    
    lines.append("}")
    
    return "\n".join(lines)


def generate_schema_cds(
    state: BuilderState,
) -> str:
    """Generate the main db/schema.cds file."""
    namespace = state.get("project_namespace", "com.company.app")
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    
    lines = []
    
    # Namespace
    lines.append(f"namespace {namespace};")
    lines.append("")
    
    # Common imports based on aspects used
    all_aspects = set()
    for entity in entities:
        all_aspects.update(entity.get("aspects", []))
    
    if all_aspects:
        using_aspects = []
        if "cuid" in all_aspects:
            using_aspects.append("cuid")
        if "managed" in all_aspects:
            using_aspects.append("managed")
        if "temporal" in all_aspects:
            using_aspects.append("temporal")
        
        if using_aspects:
            lines.append(f"using {{ {', '.join(using_aspects)} }} from '@sap/cds/common';")
            lines.append("")
    
    # Generate each entity
    for entity in entities:
        lines.append(generate_entity_cds(entity, relationships))
        lines.append("")
    
    return "\n".join(lines)


def generate_sample_data_csv(entity: EntityDefinition) -> tuple[str, str]:
    """Generate sample CSV data for an entity."""
    name = entity.get("name", "Entity")
    fields = entity.get("fields", [])
    
    # CSV header
    header_fields = [f["name"] for f in fields if not f.get("name", "").lower().startswith("_")]
    header = ";".join(header_fields)
    
    # Generate sample rows
    rows = []
    for i in range(5):
        row_values = []
        for field in fields:
            field_name = field.get("name", "")
            field_type = field.get("type", "String")
            
            if field_name.lower().startswith("_"):
                continue  # Skip system fields
            
            if field.get("key") and field_type == "UUID":
                row_values.append(f"{{{{$guid}}}}")
            elif field_type in ["String", "LargeString"]:
                row_values.append(f"Sample {field_name} {i + 1}")
            elif field_type in ["Integer", "Int16", "Int32", "Int64"]:
                row_values.append(str((i + 1) * 10))
            elif field_type in ["Decimal", "Double"]:
                row_values.append(f"{(i + 1) * 10.99}")
            elif field_type == "Boolean":
                row_values.append("true" if i % 2 == 0 else "false")
            elif field_type == "Date":
                row_values.append(f"2024-0{i + 1}-15")
            elif field_type == "DateTime":
                row_values.append(f"2024-0{i + 1}-15T10:30:00Z")
            elif field_type == "UUID":
                row_values.append(f"{{{{$guid}}}}")
            else:
                row_values.append(f"Value{i + 1}")
        
        rows.append(";".join(row_values))
    
    csv_content = header + "\n" + "\n".join(rows)
    # Note: namespace_to_path used below should be defined or replaced.
    # In data_modeling_agent it uses namespace.replace('.', '-')
    return csv_content


def namespace_to_path(name: str) -> str:
    """Convert namespace.Entity to path format."""
    return name.replace(".", "-")


def generate_index_cds(entities: list[EntityDefinition]) -> str:
    """Generate db/index.cds that imports schema."""
    return """// Database Model Index
using from './schema';
"""


# =============================================================================
# LLM Response Parsing
# =============================================================================

def _parse_llm_response(response_text: str) -> dict | None:
    """Parse LLM JSON response, handling markdown code fences."""
    try:
        text = response_text.strip()
        # Strip markdown code fences
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None


# =============================================================================
# Main Agent Function
# =============================================================================

async def data_modeling_agent(state: BuilderState) -> BuilderState:
    """
    CAP Data Modeling Agent (LLM-Driven)
    
    Uses LLM to generate production-quality CDS schemas and sample data.
    Falls back to template-based generation if LLM fails.
    
    Generates:
    1. db/schema.cds - Main entity definitions
    2. db/index.cds - Import file
    3. db/data/*.csv - Sample data files
    
    Returns updated state with generated CDS files.
    """
    logger.info("Starting Data Modeling Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "data_modeling"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting data modeling phase...")
    
    # Check prerequisites
    entities = state.get("entities", [])
    if not entities:
        log_progress(state, "Error: No entities found to process.")
        errors.append({
            "agent": "data_modeling",
            "code": "NO_ENTITIES",
            "message": "No entities to process. Requirements agent must run first.",
            "field": "entities",
            "severity": "error",
        })
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])
    provider = state.get("llm_provider")
    
    log_progress(state, f"Processing {len(entities)} entities for CDS schema generation via LLM...")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven generation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        prompt = SCHEMA_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            description=description or "No description provided",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
        )
        
        log_progress(state, "Calling LLM for CDS schema generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=DATA_MODELING_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("schema_cds"):
            schema_content = parsed["schema_cds"]
            
            # Basic validation: must contain namespace and entity keyword
            if "namespace" in schema_content and "entity" in schema_content.lower():
                generated_files.append({
                    "path": "db/schema.cds",
                    "content": schema_content,
                    "file_type": "cds",
                })
                log_progress(state, "LLM-generated CDS schema accepted.")
                
                # Process LLM-generated sample data
                sample_data = parsed.get("sample_data", [])
                for sd in sample_data:
                    if sd.get("filename") and sd.get("content"):
                        generated_files.append({
                            "path": sd["filename"],
                            "content": sd["content"],
                            "file_type": "csv",
                        })
                
                if sample_data:
                    log_progress(state, f"LLM generated {len(sample_data)} sample data files.")
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required CDS elements. Falling back to template.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed, falling back to template: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template generation.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        try:
            log_progress(state, "Generating db/schema.cds via template fallback...")
            schema_content = generate_schema_cds(state)
            generated_files.append({
                "path": "db/schema.cds",
                "content": schema_content,
                "file_type": "cds",
            })
            log_progress(state, "Template CDS schema generated successfully.")
        except Exception as e:
            logger.error(f"Failed to generate schema.cds: {e}")
            log_progress(state, f"Error generating schema: {str(e)}")
            errors.append({
                "agent": "data_modeling",
                "code": "SCHEMA_GENERATION_ERROR",
                "message": f"Failed to generate schema: {str(e)}",
                "field": None,
                "severity": "error",
            })
        
        # Generate sample data via template fallback
        if state.get("generate_sample_data", True):
            log_progress(state, "Generating sample data CSVs via template fallback...")
            for entity in entities:
                try:
                    entity_name = entity.get("name", "Entity")
                    fields = entity.get("fields", [])
                    
                    header_fields = [f["name"] for f in fields]
                    header = ";".join(header_fields)
                    
                    rows = []
                    for i in range(3):
                        row_values = []
                        for field in fields:
                            field_name = field.get("name", "")
                            field_type = field.get("type", "String")
                            
                            if field.get("key") and field_type == "UUID":
                                import uuid
                                row_values.append(str(uuid.uuid4()))
                            elif field_type in ["String", "LargeString"]:
                                row_values.append(f"Sample {field_name} {i + 1}")
                            elif field_type in ["Integer", "Int16", "Int32", "Int64"]:
                                row_values.append(str((i + 1) * 10))
                            elif field_type in ["Decimal", "Double"]:
                                row_values.append(f"{(i + 1) * 100.99}")
                            elif field_type == "Boolean":
                                row_values.append("true" if i % 2 == 0 else "false")
                            elif field_type == "Date":
                                row_values.append(f"2024-0{i + 1}-15")
                            elif field_type == "DateTime":
                                row_values.append(f"2024-0{i + 1}-15T10:30:00Z")
                            elif field_type == "UUID":
                                import uuid
                                row_values.append(str(uuid.uuid4()))
                            else:
                                row_values.append(f"Value{i + 1}")
                        
                        rows.append(";".join(row_values))
                    
                    csv_content = header + "\n" + "\n".join(rows)
                    filename = f"db/data/{namespace.replace('.', '-')}-{entity_name}.csv"
                    
                    generated_files.append({
                        "path": filename,
                        "content": csv_content,
                        "file_type": "csv",
                    })
                except Exception as e:
                    logger.warning(f"Failed to generate sample data for {entity.get('name')}: {e}")
    
    # ==========================================================================
    # Generate index.cds (always template - trivial file)
    # ==========================================================================
    try:
        index_content = generate_index_cds(entities)
        generated_files.append({
            "path": "db/index.cds",
            "content": index_content,
            "file_type": "cds",
        })
    except Exception as e:
        logger.error(f"Failed to generate index.cds: {e}")
    
    # ==========================================================================
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    # Get retry configuration
    max_retries = 3  # Could be from config
    retry_count = state.get("retry_counts", {}).get("data_modeling", 0)
    
    # Validate the generated schema.cds only
    schema_artifact = next((f for f in generated_files if f["path"] == "db/schema.cds"), None)
    if schema_artifact and llm_success:  # Only validate LLM-generated content
        validation_results = validate_artifact(schema_artifact["path"], schema_artifact["content"])
        
        if any(result.has_errors for result in validation_results):
            # Validation failed
            if should_retry_agent(validation_results, retry_count, max_retries):
                # Need to retry
                log_progress(state, f"Validation found errors. Attempting correction (retry {retry_count + 1}/{max_retries})...")
                
                # Update retry count
                if "retry_counts" not in state:
                    state["retry_counts"] = {}
                state["retry_counts"]["data_modeling"] = retry_count + 1
                
                # Mark state for retry
                state["needs_correction"] = True
                
                # Record correction attempt
                if "correction_history" not in state:
                    state["correction_history"] = []
                state["correction_history"].append({
                    "agent": "data_modeling",
                    "retry": retry_count + 1,
                    "errors_found": sum(r.error_count for r in validation_results),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Log the specific errors
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            log_progress(state, f"  - {issue.message}")
                
                # Prepare for re-run by keeping the state but clearing generated_files
                # The workflow will loop back and re-run this agent
                state["artifacts_db"] = []  # Clear for retry
                
                # Return early - workflow will loop back
                log_progress(state, "Preparing to retry with corrections...")
                return state
            else:
                # Max retries reached - log and continue with what we have
                log_progress(state, f"⚠️ Max retries reached. Some validation errors remain.")
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            errors.append({
                                "agent": "data_modeling",
                                "code": issue.code or "VALIDATION_ERROR",
                                "message": issue.message,
                                "field": None,
                                "severity": "warning"  # Downgrade to warning since we tried
                            })
        else:
            # Validation passed
            if retry_count > 0:
                # We auto-fixed errors!
                log_progress(state, f"✅ Validation passed after {retry_count} correction(s)")
                summary = format_correction_summary("data_modeling", retry_count, retry_count, retry_count)
                if "auto_fixed_errors" not in state:
                    state["auto_fixed_errors"] = []
                state["auto_fixed_errors"].append({
                    "agent": "data_modeling",
                    "summary": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                log_progress(state, "✅ Validation passed on first attempt")
    
    # Clear retry flag
    state["needs_correction"] = False
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_db"] = generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "data_modeling",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None if not errors else str(errors[0]["message"]),
        "retry_count": retry_count,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Data modeling phase complete ({generation_method}). Generated {len(generated_files)} files.")
    logger.info(f"Data Modeling Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
