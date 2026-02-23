"""
Agent 2: CAP Data Modeling Agent

Generates complete, SAP-compliant CDS data models including entities, types,
associations, compositions, aspects, and annotations.

Industry-level features:
- db/common.cds with reusable types (Currency, Country, Language, StatusCode)
- CDS Enums for status/priority/type fields
- @mandatory, @assert.range, @assert.format annotations
- localized keyword for text fields
- Realistic sample CSV data (names, emails, dates, numbers)
- Proper field-level SAP semantic annotations
"""

import logging
import json
import re
import uuid
import random
from datetime import datetime, timedelta
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

DATA_MODELING_SYSTEM_PROMPT = """You are a senior SAP CAP data architect with 10+ years of enterprise experience.
Generate complete, production-ready CDS (Core Data Services) schema files for the SAP Cloud Application Programming Model.

STRICT RULES:

1. STRUCTURE:
   - db/common.cds: Reusable types, enums and code-list entities
   - db/schema.cds: Main entity definitions
   - db/data/*.csv: Sample data per entity

2. NAMESPACE & IMPORTS:
   - Always declare `namespace {namespace};`
   - Import: `using { cuid, managed, Currency, Country, Language } from '@sap/cds/common';`
   - Import: `using { StatusValues, PriorityValues } from './common';`

3. NAMING CONVENTIONS:
   - Entities: PascalCase (e.g. PurchaseOrder, SalesOrderItem)
   - Fields: camelCase (e.g. orderNumber, totalAmount, createdAt)
   - Types: PascalCase (e.g. StatusCode, PriorityCode)

4. STANDARD ASPECTS — use for EVERY primary entity:
   - `cuid` — auto-generated UUID key
   - `managed` — createdBy, createdAt, modifiedBy, modifiedAt

5. CDS ENUMS — use for status/type/priority/category fields:
   ```cds
   type StatusCode : String enum {
       New        = 'N';
       InProcess  = 'I';
       Completed  = 'C';
       Cancelled  = 'X';
   }
   type PriorityCode : String enum {
       High   = 'H';
       Medium = 'M';
       Low    = 'L';
   }
   ```

6. FIELD ANNOTATIONS — MANDATORY on every field:
   - `@title: 'Human Readable Label'` on EVERY field
   - `@description: 'Detailed description'` on business-critical fields
   - `@mandatory` on required fields (not nullable, not key)
   - `@readonly` on computed/system fields
   - `@assert.range` on numeric fields with defined bounds
   - `@Semantics.amount.currencyCode: 'currency'` on money fields
   - `@Semantics.currencyCode` on currency code fields
   - `@Semantics.unitOfMeasure: 'unit'` on quantity fields
   - `@Semantics.email.address` on email fields
   - `@Semantics.telephone.type` on phone fields

7. RELATIONSHIPS:
   - `Composition of many` for owned sub-items (Order → Items)
   - `Association to` for references (Order → Customer)
   - Include `on` conditions for compositions: `items : Composition of many OrderItem on items.parent = $self;`
   - Add back-reference in child: `parent : Association to Order;`

8. LOCALIZATION:
   - Use `localized String` for descriptions and long text fields
   - Example: `description : localized String(1000);`

9. SAMPLE DATA (CSV):
   - Use semicolons as separators
   - Generate 5-8 realistic rows with real-world data (names, emails, dates)
   - Use {{{$guid}}} for UUID keys

OUTPUT FORMAT:
Return a JSON object:
{
    "common_cds": "... db/common.cds with reusable types ...",
    "schema_cds": "... db/schema.cds main schema ...",
    "sample_data": [
        {"filename": "db/data/namespace-Entity.csv", "content": "... CSV data ..."}
    ]
}
Return ONLY the JSON."""


SCHEMA_GENERATION_PROMPT = """Generate a complete, industry-grade CDS data model for this SAP CAP project.

Project: {project_name}
Namespace: {namespace}
Description: {description}

=== Entities ===
{entities_json}

=== Relationships ===
{relationships_json}

=== Business Rules ===
{business_rules_json}

REQUIREMENTS:
1. Create db/common.cds with:
   - StatusCode enum (New, InProcess, Completed, Cancelled, etc.)
   - PriorityCode enum (High, Medium, Low)
   - Any domain-specific enums based on the entities

2. Create db/schema.cds with:
   - namespace {namespace}
   - Import cuid, managed, Currency, Country, Language from @sap/cds/common
   - Import custom types from ./common
   - Every entity extends cuid, managed aspects
   - Every field has @title annotation
   - Status fields use StatusCode enum type
   - Priority fields use PriorityCode enum type
   - Money fields have @Semantics.amount.currencyCode
   - Email fields have @Semantics.email.address
   - Phone fields have @Semantics.telephone.type
   - Text fields use `localized String` where appropriate
   - Compositions use `on child.parent = $self` pattern
   - Include criticality virtual field for status coloring

3. Generate sample CSV data with:
   - 5-8 rows per entity
   - Realistic values (real names, real emails, proper dates)
   - Semicolons as separators
   - UUID values as {{$guid}}

Respond with ONLY valid JSON."""


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
# Realistic sample data generators
# =============================================================================

FIRST_NAMES = ["James", "Sarah", "Michael", "Emma", "Robert", "Lisa", "David", "Anna"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson"]
COMPANIES = ["Acme Corp", "TechVision GmbH", "Global Trade Inc", "SmartSolutions AG", "NovaTech Ltd", "Pinnacle Systems", "CoreDynamics", "Atlas Industries"]
CITIES = ["New York", "Berlin", "London", "Tokyo", "Mumbai", "Sydney", "Toronto", "Singapore"]
COUNTRIES = ["US", "DE", "GB", "JP", "IN", "AU", "CA", "SG"]
STATUSES = ["New", "InProcess", "Completed", "Cancelled"]
PRIORITIES = ["High", "Medium", "Low"]
CURRENCIES = ["USD", "EUR", "GBP", "JPY"]


def _gen_value(field: dict, row_idx: int, entity_name: str) -> str:
    """Generate a realistic sample value for a field."""
    name = field.get("name", "").lower()
    ftype = field.get("type", "String")

    # UUID keys
    if field.get("key") and ftype == "UUID":
        return str(uuid.uuid4())
    if ftype == "UUID":
        return str(uuid.uuid4())

    # Contextual string values
    if "email" in name:
        return f"{FIRST_NAMES[row_idx % len(FIRST_NAMES)].lower()}.{LAST_NAMES[row_idx % len(LAST_NAMES)].lower()}@example.com"
    if "phone" in name or "mobile" in name or "telephone" in name:
        return f"+1-555-{100 + row_idx:03d}-{1000 + row_idx * 111:04d}"
    if name in ("firstname", "first_name", "givenname"):
        return FIRST_NAMES[row_idx % len(FIRST_NAMES)]
    if name in ("lastname", "last_name", "surname", "familyname"):
        return LAST_NAMES[row_idx % len(LAST_NAMES)]
    if name == "name" or "name" in name and "company" not in name and "project" not in name:
        if "customer" in entity_name.lower() or "employee" in entity_name.lower() or "person" in entity_name.lower():
            return f"{FIRST_NAMES[row_idx % len(FIRST_NAMES)]} {LAST_NAMES[row_idx % len(LAST_NAMES)]}"
        return f"{entity_name} {row_idx + 1}"
    if "company" in name or "organization" in name or "supplier" in name:
        return COMPANIES[row_idx % len(COMPANIES)]
    if "city" in name:
        return CITIES[row_idx % len(CITIES)]
    if "country" in name:
        return COUNTRIES[row_idx % len(COUNTRIES)]
    if "currency" in name:
        return CURRENCIES[row_idx % len(CURRENCIES)]
    if "status" in name or "state" in name:
        return STATUSES[row_idx % len(STATUSES)]
    if "priority" in name:
        return PRIORITIES[row_idx % len(PRIORITIES)]
    if "description" in name or "comment" in name or "note" in name:
        return f"Sample {name} for {entity_name} record {row_idx + 1}"
    if "address" in name:
        return f"{100 + row_idx * 11} Main Street, {CITIES[row_idx % len(CITIES)]}"
    if "url" in name or "website" in name:
        return f"https://example.com/{entity_name.lower()}/{row_idx + 1}"
    if "number" in name or "no" == name or "code" in name or "ref" in name:
        prefix = entity_name[:3].upper()
        return f"{prefix}-2024-{(row_idx + 1):05d}"

    # Type-based fallback
    if ftype in ("String", "LargeString"):
        return f"{entity_name} {name.replace('_', ' ').title()} {row_idx + 1}"
    if ftype in ("Integer", "Int16", "Int32", "Int64"):
        if "quantity" in name or "count" in name or "qty" in name:
            return str(random.randint(1, 100))
        if "age" in name:
            return str(25 + row_idx * 5)
        return str((row_idx + 1) * 10)
    if ftype in ("Decimal", "Double"):
        if "price" in name or "amount" in name or "cost" in name or "total" in name:
            return f"{random.uniform(10, 5000):.2f}"
        if "rate" in name or "percentage" in name or "discount" in name:
            return f"{random.uniform(0, 25):.2f}"
        return f"{(row_idx + 1) * 99.99:.2f}"
    if ftype == "Boolean":
        return "true" if row_idx % 3 != 0 else "false"
    if ftype == "Date":
        base = datetime(2024, 1, 15)
        d = base + timedelta(days=row_idx * 30)
        return d.strftime("%Y-%m-%d")
    if ftype == "DateTime":
        base = datetime(2024, 1, 15, 9, 0, 0)
        d = base + timedelta(days=row_idx * 15, hours=row_idx * 2)
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"Value{row_idx + 1}"


# =============================================================================
# Template Functions
# =============================================================================

def generate_common_cds(state: BuilderState) -> str:
    """Generate db/common.cds with reusable types and enums."""
    namespace = state.get("project_namespace", "com.company.app")
    entities = state.get("entities", [])

    lines = []
    lines.append(f"namespace {namespace};")
    lines.append("")
    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("// Reusable Types & Enums")
    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("")

    # Detect which enums we need
    has_status = any(
        any(f.get("name", "").lower() in ("status", "state", "lifecycle") for f in e.get("fields", []))
        for e in entities
    )
    has_priority = any(
        any(f.get("name", "").lower() in ("priority", "urgency", "importance") for f in e.get("fields", []))
        for e in entities
    )
    has_category = any(
        any(f.get("name", "").lower() in ("category", "type", "kind", "classification") for f in e.get("fields", []))
        for e in entities
    )

    if has_status:
        lines.append("/**")
        lines.append(" * Standard status codes for workflow-driven entities")
        lines.append(" */")
        lines.append("type StatusCode : String(1) enum {")
        lines.append("    New        = 'N';")
        lines.append("    InProcess  = 'I';")
        lines.append("    Completed  = 'C';")
        lines.append("    Cancelled  = 'X';")
        lines.append("    Approved   = 'A';")
        lines.append("    Rejected   = 'R';")
        lines.append("    OnHold     = 'H';")
        lines.append("    Draft      = 'D';")
        lines.append("}")
        lines.append("")

    if has_priority:
        lines.append("/**")
        lines.append(" * Priority codes for work items")
        lines.append(" */")
        lines.append("type PriorityCode : String(1) enum {")
        lines.append("    High   = 'H';")
        lines.append("    Medium = 'M';")
        lines.append("    Low    = 'L';")
        lines.append("}")
        lines.append("")

    if has_category:
        lines.append("/**")
        lines.append(" * Generic category type")
        lines.append(" */")
        lines.append("type CategoryCode : String(20);")
        lines.append("")

    # Common reusable types
    lines.append("/**")
    lines.append(" * Common reusable field types")
    lines.append(" */")
    lines.append("type EmailAddress : String(255);")
    lines.append("type PhoneNumber  : String(30);")
    lines.append("type URL          : String(2048);")
    lines.append("type Amount       : Decimal(15, 2);")
    lines.append("type Quantity     : Integer;")
    lines.append("type Percentage   : Decimal(5, 2);")
    lines.append("")

    return "\n".join(lines)


def generate_field_definition(field: dict[str, Any]) -> str:
    """Generate CDS field definition from field dict with rich annotations."""
    name = field.get("name", "")
    field_type = field.get("type", "String")
    name_lower = name.lower()

    # Map to CDS type
    cds_type = CDS_TYPE_MAP.get(field_type, "String")

    # Add length/precision
    if field_type == "String" and field.get("length"):
        cds_type = f"String({field['length']})"
    elif field_type == "Decimal":
        precision = field.get("precision", 15)
        scale = field.get("scale", 2)
        cds_type = f"Decimal({precision}, {scale})"

    # Build annotations list
    annotations = []

    # @title — generate human-readable label from camelCase name
    field_annots = field.get("annotations", {})
    title = field_annots.get("title")
    if not title:
        # Convert camelCase to Title Case
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
        title = " ".join(w.capitalize() for w in words) if words else name
    annotations.append(f"@title: '{title}'")

    # @description
    if field_annots.get("description"):
        annotations.append(f"@description: '{field_annots['description']}'")

    # @mandatory
    if not field.get("nullable", True) and not field.get("key"):
        annotations.append("@mandatory")

    # @readonly
    if field_annots.get("readonly") or name_lower in ("createdat", "createdby", "modifiedat", "modifiedby"):
        annotations.append("@readonly")

    # Semantic annotations
    if name_lower in ("price", "amount", "total", "netamount", "totalamount", "taxamount", "grossamount", "cost", "unitprice"):
        annotations.append("@Semantics.amount.currencyCode: 'currency'")
    if name_lower == "currency" or name_lower == "currencycode":
        annotations.append("@Semantics.currencyCode")
    if name_lower in ("email", "emailaddress", "mail"):
        annotations.append("@Semantics.email.address")
    if name_lower in ("phone", "phonenumber", "telephone", "mobile"):
        annotations.append("@Semantics.telephone.type: #work")
    if name_lower in ("quantity", "qty", "count"):
        annotations.append("@Semantics.quantity.unitOfMeasure: 'unit'")

    # @assert.range for certain numeric fields
    if field_type in ("Decimal", "Double", "Integer") and any(k in name_lower for k in ("rating", "score", "percentage", "discount")):
        if "rating" in name_lower or "score" in name_lower:
            annotations.append("@assert.range: [0, 5]")
        elif "percentage" in name_lower or "discount" in name_lower:
            annotations.append("@assert.range: [0, 100]")

    # Build the field lines
    key_prefix = "key " if field.get("key") else "    "
    type_suffix = ""
    if not field.get("nullable", True) and not field.get("key"):
        type_suffix = " not null"
    if field.get("default"):
        type_suffix += f" default {field['default']}"

    # Format: annotations on line above, field definition below
    annotation_lines = "\n".join(f"    {a}" for a in annotations)
    field_line = f"    {key_prefix.strip()} {name} : {cds_type}{type_suffix};" if field.get("key") else f"    {name} : {cds_type}{type_suffix};"

    if annotations:
        return f"{annotation_lines}\n{field_line}"
    return field_line


def generate_entity_cds(entity: EntityDefinition, relationships: list[RelationshipDefinition]) -> str:
    """Generate CDS entity definition with relationships."""
    name = entity.get("name", "Entity")
    description = entity.get("description", "")
    fields = entity.get("fields", [])
    aspects = entity.get("aspects", [])

    lines = []

    # Entity JSDoc
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
        # Skip key fields if entity uses cuid (cuid provides ID already)
        if field.get("key") and field.get("type") == "UUID" and "cuid" in aspects:
            continue
        lines.append(generate_field_definition(field))

    # Criticality virtual field for status entities
    has_status = any(f.get("name", "").lower() in ("status", "state") for f in fields)
    if has_status:
        lines.append("    // Virtual field for Fiori status coloring")
        lines.append("    @title: 'Criticality'")
        lines.append("    criticality : Integer @Core.Computed;")

    # Add compositions and associations from relationships
    entity_rels = [r for r in relationships if r.get("source_entity") == name]
    if entity_rels:
        lines.append("")
        lines.append("    // Relationships")

    for rel in entity_rels:
        rel_name = rel.get("name", "")
        target = rel.get("target_entity", "")
        rel_type = rel.get("type", "association")
        cardinality = rel.get("cardinality", "n:1")

        if rel_type == "composition":
            if cardinality in ("1:n", "n:m"):
                lines.append(f"    {rel_name} : Composition of many {target} on {rel_name}.parent = $self;")
            else:
                lines.append(f"    {rel_name} : Composition of {target};")
        else:  # association
            if cardinality in ("1:n", "n:m"):
                lines.append(f"    {rel_name} : Association to many {target};")
            else:
                lines.append(f"    {rel_name} : Association to {target};")

    # Back-references for composition children
    child_rels = [r for r in relationships if r.get("target_entity") == name and r.get("type") == "composition"]
    for rel in child_rels:
        parent = rel.get("source_entity", "")
        lines.append(f"    parent : Association to {parent};")

    lines.append("}")

    return "\n".join(lines)


def generate_schema_cds(state: BuilderState) -> str:
    """Generate the main db/schema.cds file."""
    namespace = state.get("project_namespace", "com.company.app")
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])

    lines = []
    lines.append(f"namespace {namespace};")
    lines.append("")

    # Common imports based on aspects and field types used
    all_aspects = set()
    has_currency = False
    has_country = False
    for entity in entities:
        all_aspects.update(entity.get("aspects", []))
        for field in entity.get("fields", []):
            fn = field.get("name", "").lower()
            if "currency" in fn:
                has_currency = True
            if "country" in fn:
                has_country = True

    using_items = []
    if "cuid" in all_aspects:
        using_items.append("cuid")
    if "managed" in all_aspects:
        using_items.append("managed")
    if "temporal" in all_aspects:
        using_items.append("temporal")
    if has_currency:
        using_items.append("Currency")
    if has_country:
        using_items.append("Country")

    if using_items:
        lines.append(f"using {{ {', '.join(using_items)} }} from '@sap/cds/common';")

    # Import common types
    lines.append("using from './common';")
    lines.append("")

    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("// Entity Definitions")
    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("")

    # Generate each entity
    for entity in entities:
        lines.append(generate_entity_cds(entity, relationships))
        lines.append("")

    return "\n".join(lines)


def generate_sample_data_csv(entity: EntityDefinition, namespace: str) -> tuple[str, str]:
    """Generate realistic sample CSV data for an entity."""
    name = entity.get("name", "Entity")
    fields = entity.get("fields", [])

    # Filter out system fields
    visible_fields = [f for f in fields if not f.get("name", "").startswith("_")]
    header_names = [f["name"] for f in visible_fields]
    header = ";".join(header_names)

    rows = []
    for i in range(6):  # 6 rows of realistic data
        values = [_gen_value(f, i, name) for f in visible_fields]
        rows.append(";".join(values))

    csv_content = header + "\n" + "\n".join(rows)
    filename = f"db/data/{namespace.replace('.', '-')}-{name}.csv"

    return filename, csv_content


def namespace_to_path(name: str) -> str:
    """Convert namespace.Entity to path format."""
    return name.replace(".", "-")


def generate_index_cds(entities: list[EntityDefinition]) -> str:
    """Generate db/index.cds that imports schema and common types."""
    return """// Database Model Index
using from './common';
using from './schema';
"""


# =============================================================================
# LLM Response Parsing
# =============================================================================

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
# Main Agent Function
# =============================================================================

async def data_modeling_agent(state: BuilderState) -> BuilderState:
    """
    CAP Data Modeling Agent (LLM-Driven)
    
    Uses LLM to generate production-quality CDS schemas and sample data.
    Falls back to template-based generation if LLM fails.
    
    Generates:
    1. db/common.cds - Reusable types, enums, code-list entities
    2. db/schema.cds - Main entity definitions with rich annotations
    3. db/index.cds - Import file
    4. db/data/*.csv - Realistic sample data files
    
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
    
    log_progress(state, f"Processing {len(entities)} entities for CDS schema generation...")
    
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
                # Add common.cds if provided
                if parsed.get("common_cds"):
                    generated_files.append({
                        "path": "db/common.cds",
                        "content": parsed["common_cds"],
                        "file_type": "cds",
                    })
                    log_progress(state, "✅ LLM-generated common.cds accepted.")
                
                generated_files.append({
                    "path": "db/schema.cds",
                    "content": schema_content,
                    "file_type": "cds",
                })
                log_progress(state, "✅ LLM-generated CDS schema accepted.")
                
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
                    log_progress(state, f"✅ LLM generated {len(sample_data)} sample data files.")
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required CDS elements. Falling back to template.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed, falling back to template: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template generation.")
    
    # ==========================================================================
    # Fallback: Template-based generation (industry-grade)
    # ==========================================================================
    if not llm_success:
        # 1. Generate db/common.cds
        try:
            log_progress(state, "Generating db/common.cds with reusable types...")
            common_content = generate_common_cds(state)
            generated_files.append({
                "path": "db/common.cds",
                "content": common_content,
                "file_type": "cds",
            })
        except Exception as e:
            logger.error(f"Failed to generate common.cds: {e}")
        
        # 2. Generate db/schema.cds
        try:
            log_progress(state, "Generating db/schema.cds with rich annotations...")
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
        
        # 3. Generate realistic sample data CSVs
        if state.get("generate_sample_data", True):
            log_progress(state, "Generating realistic sample data CSVs...")
            for entity in entities:
                try:
                    filename, csv_content = generate_sample_data_csv(entity, namespace)
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
    
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("data_modeling", 0)
    
    schema_artifact = next((f for f in generated_files if f["path"] == "db/schema.cds"), None)
    if schema_artifact and llm_success:
        validation_results = validate_artifact(schema_artifact["path"], schema_artifact["content"])
        
        if any(result.has_errors for result in validation_results):
            if should_retry_agent(validation_results, retry_count, max_retries):
                log_progress(state, f"Validation found errors. Attempting correction (retry {retry_count + 1}/{max_retries})...")
                
                if "retry_counts" not in state:
                    state["retry_counts"] = {}
                state["retry_counts"]["data_modeling"] = retry_count + 1
                state["needs_correction"] = True
                
                if "correction_history" not in state:
                    state["correction_history"] = []
                state["correction_history"].append({
                    "agent": "data_modeling",
                    "retry": retry_count + 1,
                    "errors_found": sum(r.error_count for r in validation_results),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            log_progress(state, f"  - {issue.message}")
                
                state["artifacts_db"] = []
                log_progress(state, "Preparing to retry with corrections...")
                return state
            else:
                log_progress(state, "⚠️ Max retries reached. Some validation errors remain.")
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            errors.append({
                                "agent": "data_modeling",
                                "code": issue.code or "VALIDATION_ERROR",
                                "message": issue.message,
                                "field": None,
                                "severity": "warning"
                            })
        else:
            if retry_count > 0:
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
    
    state["needs_correction"] = False
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_db"] = generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
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
    log_progress(state, f"Data modeling complete ({generation_method}). Generated {len(generated_files)} files.")
    logger.info(f"Data Modeling Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
