"""
Agent 2: CAP Data Modeling Agent

Generates complete, SAP-compliant CDS data models including entities, types,
associations, compositions, aspects, and annotations.
"""

import logging
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    RelationshipDefinition,
    GeneratedFile,
    ValidationError,
)

logger = logging.getLogger(__name__)


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
    for i in range(3):
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
    filename = f"db/data/{namespace_to_path(name)}-{name}.csv"
    
    return filename, csv_content


def namespace_to_path(name: str) -> str:
    """Convert namespace.Entity to path format."""
    return name.replace(".", "-")


def generate_index_cds(entities: list[EntityDefinition]) -> str:
    """Generate db/index.cds that imports schema."""
    return """// Database Model Index
using from './schema';
"""


# =============================================================================
# Main Agent Function
# =============================================================================

async def data_modeling_agent(state: BuilderState) -> BuilderState:
    """
    CAP Data Modeling Agent
    
    Generates:
    1. db/schema.cds - Main entity definitions
    2. db/index.cds - Import file
    3. db/data/*.csv - Sample data files
    
    Returns updated state with generated CDS files.
    """
    logger.info("Starting Data Modeling Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "data_modeling"
    state["updated_at"] = now
    
    # Check prerequisites
    entities = state.get("entities", [])
    if not entities:
        errors.append({
            "agent": "data_modeling",
            "code": "NO_ENTITIES",
            "message": "No entities to process. Requirements agent must run first.",
            "field": "entities",
            "severity": "error",
        })
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    # ==========================================================================
    # Generate schema.cds
    # ==========================================================================
    try:
        schema_content = generate_schema_cds(state)
        generated_files.append({
            "path": "db/schema.cds",
            "content": schema_content,
            "file_type": "cds",
        })
        logger.info("Generated db/schema.cds")
    except Exception as e:
        logger.error(f"Failed to generate schema.cds: {e}")
        errors.append({
            "agent": "data_modeling",
            "code": "SCHEMA_GENERATION_ERROR",
            "message": f"Failed to generate schema: {str(e)}",
            "field": None,
            "severity": "error",
        })
    
    # ==========================================================================
    # Generate index.cds
    # ==========================================================================
    try:
        index_content = generate_index_cds(entities)
        generated_files.append({
            "path": "db/index.cds",
            "content": index_content,
            "file_type": "cds",
        })
        logger.info("Generated db/index.cds")
    except Exception as e:
        logger.error(f"Failed to generate index.cds: {e}")
    
    # ==========================================================================
    # Generate sample data CSVs (if enabled)
    # ==========================================================================
    if state.get("generate_sample_data", True):
        namespace = state.get("project_namespace", "com.company.app")
        
        for entity in entities:
            try:
                entity_name = entity.get("name", "Entity")
                fields = entity.get("fields", [])
                
                # Generate header
                header_fields = [f["name"] for f in fields]
                header = ";".join(header_fields)
                
                # Generate sample rows
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
                            length = field.get("length", 50)
                            sample = f"Sample {field_name} {i + 1}"[:length]
                            row_values.append(sample)
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
                logger.info(f"Generated {filename}")
                
            except Exception as e:
                logger.warning(f"Failed to generate sample data for {entity.get('name')}: {e}")
    
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
        "error": None if not errors else str(errors[0]["message"]) if errors else None,
    }]
    
    logger.info(f"Data Modeling Agent completed. Generated {len(generated_files)} files.")
    
    return state
