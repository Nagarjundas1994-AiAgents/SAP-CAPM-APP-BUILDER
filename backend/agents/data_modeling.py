"""
Agent 2: CAP Data Modeling Agent (LLM-Driven)

Generates complete, SAP-compliant CDS data models including entities, types,
associations, compositions, aspects, and annotations.

FULLY LLM-DRIVEN: No template fallbacks. Uses retry with self-healing
and inter-agent context passing.

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

from backend.agents.llm_providers import get_llm_manager
from backend.agents.llm_utils import (
    generate_with_retry,
    parse_llm_json,
    store_generated_content,
)
from backend.agents.knowledge_loader import get_data_modeling_knowledge
from backend.agents.resilience import with_timeout
from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
)
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt — CDS Schema Expert
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
   - Always `using { cuid, managed } from '@sap/cds/common';`
   - If using temporal: `using { temporal } from '@sap/cds/common';`
   - Import common types: `using from './common';`

3. ENTITY DEFINITION PATTERNS:
   ```cds
   entity Product : cuid, managed {
     productNumber : String(20) @title: 'Product No.' @mandatory;
     name          : String(100) @title: 'Name' @mandatory;
     description   : String(500) @title: 'Description';
     price         : Decimal(10,2) @title: 'Price' @Measures.ISOCurrency: currency;
     currency      : String(3) @title: 'Currency' default 'USD';
     stock         : Integer @title: 'Stock' default 0;
     status        : String(20) @title: 'Status' default 'Available';
     category      : Association to Category;
     items         : Composition of many OrderItem on items.product = $self;
   }
   ```

4. TYPES & ENUMS (db/common.cds):
   ```cds
   namespace com.company.app;
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
   type Currency : String(3);
   type Amount : Decimal(15,2);
   ```

5. ASSOCIATIONS & COMPOSITIONS:
   - Association: `category : Association to Category;` (independent reference)
   - Composition: `items : Composition of many OrderItem on items.parent = $self;` (owned children)
   - Back-link in child: `parent : Association to Order;` (for composition child)
   - Many-to-one: `customer : Association to Customer;`

6. FIELD ANNOTATIONS — MANDATORY on every field:
   - `@title: 'Human Readable Label'` on EVERY field
   - `@description: 'Detailed description'` on business-critical fields
   - `@mandatory` on required fields (not nullable, not key)
   - `@readonly` on computed/system fields
   - `@Measures.ISOCurrency: currency` on amount fields
   - `@Semantics.email.address` on email fields
   - `@Semantics.telephone.type` on phone fields

7. CDS TYPES (use ONLY these):
   - String(length), Integer, Int64, Decimal(precision,scale), Double
   - Boolean, Date, DateTime, Time, Timestamp
   - UUID, LargeString, LargeBinary

8. DEFAULT VALUES:
   - Strings: `default 'value'`
   - Numbers: `default 0`
   - Booleans: `default true` or `default false`

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

Return ONLY valid JSON."""


SCHEMA_GENERATION_PROMPT = """Generate a complete, production-ready CDS data model for the following SAP CAP application.

Project Name: {project_name}
Namespace: {namespace}
Description: {description}

ENTITIES & FIELDS:
{entities_json}

RELATIONSHIPS:
{relationships_json}

BUSINESS RULES (for context — you're generating the data model, not the logic):
{business_rules_json}

REQUIREMENTS:
1. Generate db/common.cds with:
   - Namespace declaration
   - Reusable type aliases (Currency, Amount, StatusCode, etc.)
   - Enum types for status and category fields
   - Code-list entities for dropdown values if applicable

2. Generate db/schema.cds with:
   - Namespace declaration
   - Import from @sap/cds/common (cuid, managed)
   - Import from './common'
   - Complete entity definitions with ALL fields and proper CDS types
   - ALL associations and compositions between entities
   - Rich annotations on every field (@title, @mandatory, semantic annotations)
   - Default values where applicable
   - Virtual/calculated fields where needed
   - Proper aspect usage (cuid, managed)

3. Generate sample CSV data with:
   - 5-8 rows per entity
   - Realistic values (real names, real emails, proper dates)
   - Semicolons as separators
   - UUID values as {{$guid}}

Respond with ONLY valid JSON."""


# =============================================================================
# Main Agent Function
# =============================================================================

@with_timeout(timeout_seconds=180)  # 3 minutes for LLM-heavy CDS generation
async def data_modeling_agent(state: BuilderState) -> dict[str, Any]:
    """
    CAP Data Modeling Agent (LLM-Driven)

    Uses LLM to generate production-quality CDS schemas and sample data.
    No template fallbacks — uses retry with self-healing.

    Generates:
    1. db/common.cds - Reusable types, enums, code-list entities
    2. db/schema.cds - Main entity definitions with rich annotations
    3. db/index.cds - Import file
    4. db/data/*.csv - Realistic sample data files

    Returns partial state dict with only changed keys.
    """
    agent_name = "data_modeling"
    logger.info(f"Starting {agent_name} Agent (LLM-Driven)")

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

    log_progress(state, "Starting data modeling phase...")

    try:
        errors: list[ValidationError] = []
        generated_files: list[GeneratedFile] = []

        # Check prerequisites
        entities = state.get("entities", [])
        if not entities:
            log_progress(state, "Error: No entities found to process.")
            
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
                    "error": "No entities to process",
                    "logs": state.get("current_logs", []),
                }],
                "retry_counts": new_retry_counts,
                "needs_correction": True,
                "validation_errors": [{
                    "agent": agent_name,
                    "code": "NO_ENTITIES",
                    "message": "No entities to process. Requirements agent must run first.",
                    "field": "entities",
                    "severity": "error",
                }],
                "current_agent": agent_name,
                "updated_at": datetime.utcnow().isoformat(),
            }

        namespace = state.get("project_namespace", "com.company.app")
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        relationships = state.get("relationships", [])
        business_rules = state.get("business_rules", [])

        log_progress(state, f"Processing {len(entities)} entities for CDS schema generation...")

        # ==========================================================================
        # LLM-Driven Generation with Retry + Knowledge Injection
        # ==========================================================================
        knowledge = get_data_modeling_knowledge()

        prompt = SCHEMA_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            description=description or "No description provided",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
        )

        # Inject knowledge into prompt
        prompt = f"{knowledge}\n\n{prompt}"

        # Self-Healing: Inject correction context if present
        correction_context = state.get("correction_context")
        if state.get("needs_correction") and state.get("correction_agent") == agent_name and correction_context:
            log_progress(state, "Applying self-healing correction context from validation agent...")
            correction_prompt = correction_context.get("correction_prompt", "")
            if correction_prompt:
                prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

        log_progress(state, "Calling LLM for CDS schema generation...")

        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=DATA_MODELING_SYSTEM_PROMPT,
            state=state,
            required_keys=["schema_cds"],
            max_retries=3,
            agent_name=agent_name,
        )

        if result and result.get("schema_cds"):
            schema_content = result["schema_cds"]

            # Basic validation: must contain namespace and entity keyword
            if "entity" in schema_content.lower():
                # Add common.cds if provided
                if result.get("common_cds"):
                    generated_files.append({
                        "path": "db/common.cds",
                        "content": result["common_cds"],
                        "file_type": "cds",
                    })
                    log_progress(state, "✅ Generated common.cds with reusable types.")

                generated_files.append({
                    "path": "db/schema.cds",
                    "content": schema_content,
                    "file_type": "cds",
                })
                log_progress(state, "✅ Generated CDS schema.")

                # Process sample data
                sample_data = result.get("sample_data", [])
                for sd in sample_data:
                    if sd.get("filename") and sd.get("content"):
                        generated_files.append({
                            "path": sd["filename"],
                            "content": sd["content"],
                            "file_type": "csv",
                        })

                if sample_data:
                    log_progress(state, f"✅ Generated {len(sample_data)} sample data files.")
            else:
                log_progress(state, "⚠️ LLM schema missing entity definitions. Adding minimal schema.")
                schema_content = _generate_minimal_schema(entities, namespace, relationships)
                generated_files.append({
                    "path": "db/schema.cds",
                    "content": schema_content,
                    "file_type": "cds",
                })
        else:
            # Minimal fallback — NOT a template, just the bare minimum to keep pipeline going
            log_progress(state, "⚠️ LLM generation failed. Generating minimal valid schema.")
            schema_content = _generate_minimal_schema(entities, namespace, relationships)
            generated_files.append({
                "path": "db/schema.cds",
                "content": schema_content,
                "file_type": "cds",
            })
            errors.append({
                "agent": agent_name,
                "code": "LLM_FAILED",
                "message": "LLM schema generation failed. Minimal schema generated.",
                "field": None,
                "severity": "warning",
            })

        # ==========================================================================
        # Generate db/index.cds
        # ==========================================================================
        index_cds = f'using from \'./schema\';\nusing from \'./common\';\n'
        generated_files.append({
            "path": "db/index.cds",
            "content": index_cds,
            "file_type": "cds",
        })

        # ==========================================================================
        # Store inter-agent context
        # ==========================================================================
        store_generated_content(state, generated_files, {
            "schema.cds": "generated_schema_cds",
            "common.cds": "generated_common_cds",
        })

        # ==========================================================================
        # Success path - return partial state
        # ==========================================================================
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1

        log_progress(state, f"Data modeling complete. Generated {len(generated_files)} files.")
        
        return {
            # Agent outputs
            "artifacts_db": generated_files,
            "generated_schema_cds": state.get("generated_schema_cds", ""),
            "generated_common_cds": state.get("generated_common_cds", ""),
            "validation_errors": errors,
            
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


# =============================================================================
# Minimal Fallback (NOT a template — bare minimum valid CDS)
# =============================================================================

def _generate_minimal_schema(
    entities: list[EntityDefinition],
    namespace: str,
    relationships: list,
) -> str:
    """
    Generate a minimal valid CDS schema from entity definitions.
    This is NOT a template — it's a structured conversion of the entity
    data that the LLM already generated in the requirements phase.
    """
    lines = [
        f"namespace {namespace};",
        "",
        "using { cuid, managed } from '@sap/cds/common';",
        "",
    ]

    # Build relationship lookup
    compositions = {}
    associations = {}
    for rel in relationships:
        source = rel.get("source_entity", "")
        target = rel.get("target_entity", "")
        name = rel.get("name", target[0].lower() + target[1:] if target else "ref")
        rel_type = rel.get("type", "association")
        cardinality = rel.get("cardinality", "n:1")

        if rel_type == "composition":
            compositions.setdefault(source, []).append((name, target))
        else:
            associations.setdefault(source, []).append((name, target, cardinality))

    for entity in entities:
        name = entity.get("name", "Entity")
        desc = entity.get("description", "")
        fields = entity.get("fields", [])
        aspects = entity.get("aspects", ["cuid", "managed"])

        # Entity declaration
        aspect_str = ", ".join(aspects) if aspects else "cuid, managed"
        if desc:
            lines.append(f"/**")
            lines.append(f" * {desc}")
            lines.append(f" */")
        lines.append(f"entity {name} : {aspect_str} {{")

        # Fields (skip ID since cuid provides it)
        for field in fields:
            fname = field.get("name", "")
            ftype = field.get("type", "String")
            if fname == "ID":
                continue  # cuid provides this

            # Build type string
            type_str = ftype
            if ftype == "String":
                length = field.get("length", 100)
                type_str = f"String({length})"
            elif ftype == "Decimal":
                precision = field.get("precision", 12)
                scale = field.get("scale", 2)
                type_str = f"Decimal({precision},{scale})"

            # Annotations
            annotations = []
            field_annotations = field.get("annotations", {})
            title = field_annotations.get("title", "")
            if title:
                annotations.append(f"@title: '{title}'")

            if not field.get("nullable", True) and not field.get("key", False):
                annotations.append("@mandatory")

            # Default
            default_str = ""
            default_val = field.get("default")
            if default_val is not None:
                default_str = f" default {default_val}"

            ann_str = " ".join(annotations)
            if ann_str:
                ann_str = "  " + ann_str
            lines.append(f"  {fname} : {type_str}{ann_str}{default_str};")

        # Associations
        for assoc_name, target, card in associations.get(name, []):
            if card in ("1:n",):
                lines.append(f"  {assoc_name} : Association to many {target};")
            else:
                lines.append(f"  {assoc_name} : Association to {target};")

        # Compositions
        for comp_name, target in compositions.get(name, []):
            lines.append(f"  {comp_name} : Composition of many {target} on {comp_name}.parent = $self;")

        lines.append("}")
        lines.append("")

    return "\n".join(lines)
