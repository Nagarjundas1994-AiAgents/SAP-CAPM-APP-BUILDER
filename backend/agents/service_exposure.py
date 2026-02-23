"""
Agent 3: CAP Service Exposure Agent

Generates OData service definitions, projections, actions, functions,
and Fiori UI annotations for SAP CAP services.

Industry-level features:
- @odata.draft.enabled for all root entities
- Custom actions/functions from business rules
- Deep Fiori annotations: UI.LineItem, HeaderInfo, Facets, FieldGroups
- @Capabilities annotations (InsertRestrictions, DeleteRestrictions)
- @Common.ValueList for association/enum fields
- @UI.DataPoint for KPIs (status progress, ratings)
- @UI.SelectionFields for filter bars
- Status criticality coloring
- Composition facets on Object Pages
- @Common.SideEffects for calculated fields
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

SERVICE_SYSTEM_PROMPT = """You are a senior SAP CAP service architect with deep expertise in Fiori Elements.
Generate production-ready, enterprise-grade OData service definitions and Fiori annotations.

STRICT RULES:

1. SERVICE DEFINITION (srv/service.cds):
   - Import schema: `using { namespace as db } from '../db/schema';`
   - Declare: `service ServiceName @(path: '/endpoint') { ... }`
   - Use projections: `entity X as projection on db.X;`
   - Add `@odata.draft.enabled` for all root editable entities
   - Define custom actions for every business rule:
     - `action approve() returns Boolean;` (bound to entity)
     - `function getDashboard() returns array of DashboardItem;` (unbound)
   - Add `@requires: 'authenticated-user'` at service level

2. ANNOTATIONS (srv/annotations.cds):
   Generate COMPLETE annotations for EVERY entity including:

   a) UI.HeaderInfo — entity title/description for Object Page header:
      ```cds
      UI.HeaderInfo: {
          TypeName: 'Order',
          TypeNamePlural: 'Orders',
          Title: { Value: orderNumber },
          Description: { Value: customerName },
          ImageUrl: imageUrl,
          TypeImageUrl: 'sap-icon://sales-order'
      }
      ```

   b) UI.SelectionFields — filter bar on List Report:
      - Include 3-5 most useful filterable fields (status, date, name)

   c) UI.LineItem — columns on List Report table:
      - Show 5-8 most important fields
      - Add DataFieldForAction for custom actions
      - Add criticality coloring for status fields:
        `{ Value: status, Criticality: criticality }`

   d) UI.Facets — Object Page sections:
      - GeneralInfo field group
      - Status/Details field group
      - Composition child table (ReferenceFacet → child UI.LineItem)
      - Notes/Administrative section

   e) UI.FieldGroup — grouped fields on Object Page:
      - #GeneralInfo: key business fields
      - #Details: secondary fields
      - #Admin: created/modified fields with @readonly

   f) UI.DataPoint — KPI values in header:
      - Status progress, total amounts, ratings

   g) @Capabilities — CRUD restrictions:
      ```cds
      @Capabilities.DeleteRestrictions.Deletable: false  // for read-only entities
      @Capabilities.InsertRestrictions.Insertable: false  // for lookup tables
      ```

   h) @Common.ValueList — for association and enum fields:
      ```cds
      status @Common.ValueListWithFixedValues;
      ```

   i) @Common.SideEffects — reactive form updates:
      ```cds
      @Common.SideEffects: {
          SourceProperties: [quantity, unitPrice],
          TargetProperties: [netAmount]
      }
      ```

OUTPUT FORMAT:
Return a JSON object:
{
    "service_cds": "... srv/service.cds content ...",
    "annotations_cds": "... srv/annotations.cds content ..."
}
Return ONLY the JSON."""


SERVICE_GENERATION_PROMPT = """Generate enterprise-grade srv/service.cds and srv/annotations.cds.

Project: {project_name} ({namespace})
Draft enabled: {draft_enabled}

=== Schema (db/schema.cds) ===
{schema_content}

=== Entities ===
{entities_json}

=== Relationships ===
{relationships_json}

=== Business Rules ===
{business_rules_json}

REQUIREMENTS:
1. Service name: '{service_name}' at path '/{service_path}'
2. Project ALL entities from the schema
3. Enable @odata.draft.enabled for all root business entities
4. Define bound actions for business rules (approve, reject, cancel)
5. All annotations must cover EVERY entity:
   - UI.HeaderInfo with TypeName, Title, Description, TypeImageUrl
   - UI.SelectionFields (3-5 most filterable fields)
   - UI.LineItem (5-8 columns with criticality for status)
   - UI.Facets with multiple FieldGroups and composition LineItems
   - UI.FieldGroup#GeneralInfo, #Details, #AdminData
   - UI.DataPoint for status and total amount fields
   - @Capabilities restrictions for read-only entities
   - @Common.ValueListWithFixedValues for enum/status fields

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
# Entity analysis helpers
# =============================================================================

def _humanize(name: str) -> str:
    """Convert camelCase/PascalCase to human-readable text."""
    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
    return " ".join(w.capitalize() for w in words) if words else name


def _pluralize(name: str) -> str:
    """Simple pluralization for entity names."""
    human = _humanize(name)
    if human.endswith("y") and human[-2] not in "aeiou":
        return human[:-1] + "ies"
    if human.endswith(("s", "sh", "ch", "x")):
        return human + "es"
    return human + "s"


def _get_icon(entity_name: str) -> str:
    """Get SAP icon based on entity name."""
    name_lower = entity_name.lower()
    icon_map = {
        "order": "sap-icon://sales-order",
        "salesorder": "sap-icon://sales-order",
        "purchaseorder": "sap-icon://purchase-order",
        "invoice": "sap-icon://money-bills",
        "customer": "sap-icon://customer",
        "supplier": "sap-icon://supplier",
        "product": "sap-icon://product",
        "employee": "sap-icon://employee",
        "department": "sap-icon://org-chart",
        "project": "sap-icon://project-definition-2",
        "task": "sap-icon://task",
        "category": "sap-icon://group",
        "review": "sap-icon://feedback",
        "leave": "sap-icon://date-time",
        "shipment": "sap-icon://shipping-status",
        "inventory": "sap-icon://inventory",
        "payment": "sap-icon://payment-approval",
        "contract": "sap-icon://official-service",
        "ticket": "sap-icon://it-instance",
    }
    for key, icon in icon_map.items():
        if key in name_lower:
            return icon
    return "sap-icon://document"


def _is_status_field(name: str) -> bool:
    return name.lower() in ("status", "state", "lifecycle", "phase")


def _is_priority_field(name: str) -> bool:
    return name.lower() in ("priority", "urgency", "importance")


def _is_amount_field(name: str) -> bool:
    keywords = ("amount", "total", "price", "cost", "net", "gross", "tax", "value", "subtotal")
    return any(k in name.lower() for k in keywords)


def _is_date_field(field: dict) -> bool:
    return field.get("type", "") in ("Date", "DateTime")


def _is_searchable(field: dict) -> bool:
    """Is this field good for filter bar?"""
    name = field.get("name", "").lower()
    ftype = field.get("type", "")
    if _is_status_field(name) or _is_priority_field(name):
        return True
    if ftype in ("Date", "DateTime"):
        return True
    if name in ("name", "description", "title", "category", "type"):
        return True
    return False


def _is_child_entity(entity_name: str, relationships: list) -> bool:
    """Check if entity is a composition child."""
    return any(
        r.get("type") == "composition" and r.get("target_entity") == entity_name
        for r in relationships
    )


def _get_children(entity_name: str, relationships: list) -> list:
    """Get composition children of an entity."""
    return [
        r for r in relationships
        if r.get("type") == "composition" and r.get("source_entity") == entity_name
    ]


# =============================================================================
# Template Fallback Functions
# =============================================================================

def generate_service_cds(state: BuilderState) -> str:
    """Generate the main srv/service.cds file (template fallback)."""
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])
    odata_version = state.get("odata_version", ODataVersion.V4.value)
    draft_enabled = state.get("draft_enabled", True)

    service_name = "".join(
        word.capitalize()
        for word in project_name.replace("-", " ").replace("_", " ").split()
    )
    service_name = f"{service_name}Service"

    lines = []
    lines.append(f"using {{ {namespace} as db }} from '../db/schema';")
    lines.append("")

    if odata_version == ODataVersion.V2.value:
        lines.append("@protocol: 'odata-v2'")
    else:
        lines.append("@protocol: 'odata-v4'")

    lines.append("@requires: 'authenticated-user'")
    lines.append(f"service {service_name} @(path: '/{project_name.lower().replace(' ', '-')}') {{")
    lines.append("")

    for entity in entities:
        entity_name = entity.get("name", "Entity")
        is_child = _is_child_entity(entity_name, relationships)

        # Draft for root entities only
        if draft_enabled and not is_child:
            lines.append(f"    @odata.draft.enabled")
        lines.append(f"    entity {entity_name} as projection on db.{entity_name};")
        lines.append("")

    # Custom actions/functions from business rules
    action_rules = [r for r in business_rules if r.get("rule_type") in ("workflow", "authorization")]
    if action_rules:
        lines.append("    // ── Custom Actions ──────────────────────────────")
        for rule in action_rules:
            rule_name = rule.get("name", "customAction")
            description = rule.get("description", "")
            entity_name = rule.get("entity", "")

            action_name = re.sub(r'[\s_-]+', '', rule_name)
            action_name = action_name[0].lower() + action_name[1:] if action_name else "customAction"

            lines.append(f"    // {description}")
            if "approv" in rule_name.lower():
                lines.append(f"    action {action_name}() returns Boolean;")
            elif "reject" in rule_name.lower():
                lines.append(f"    action {action_name}(reason: String) returns Boolean;")
            elif "cancel" in rule_name.lower():
                lines.append(f"    action {action_name}() returns Boolean;")
            else:
                lines.append(f"    action {action_name}() returns Boolean;")
            lines.append("")

    lines.append("}")
    return "\n".join(lines)


def generate_annotations_cds(state: BuilderState) -> str:
    """Generate comprehensive Fiori annotations for the service (template fallback)."""
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])

    lines = []
    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("// SAP Fiori Elements Annotations")
    lines.append("// ═══════════════════════════════════════════════════════════")
    lines.append("")
    lines.append("using from './service';")
    lines.append("")

    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        is_child = _is_child_entity(entity_name, relationships)
        children = _get_children(entity_name, relationships)

        # Determine key field, title field, description field
        key_field = None
        title_field = None
        desc_field = None
        status_field = None
        priority_field = None
        amount_fields = []
        
        for f in fields:
            fname = f.get("name", "")
            if f.get("key"):
                key_field = fname
            if not title_field and f.get("type") in ("String",) and not f.get("key"):
                if any(k in fname.lower() for k in ("name", "title", "number", "code", "label")):
                    title_field = fname
            if not desc_field and f.get("type") in ("String", "LargeString") and fname != title_field:
                if any(k in fname.lower() for k in ("description", "desc", "note", "comment")):
                    desc_field = fname
            if _is_status_field(fname):
                status_field = fname
            if _is_priority_field(fname):
                priority_field = fname
            if _is_amount_field(fname):
                amount_fields.append(fname)

        if not title_field:
            # Take first non-key string field
            title_field = next(
                (f.get("name") for f in fields if not f.get("key") and f.get("type") in ("String",)),
                key_field
            )
        if not desc_field:
            desc_field = title_field

        # Filterable fields
        filter_fields = [f.get("name") for f in fields if _is_searchable(f)][:5]

        # Display columns (first 7 non-key fields)
        display_fields = [f for f in fields if not f.get("key") or f.get("type") != "UUID"][:7]

        icon = _get_icon(entity_name)
        human_name = _humanize(entity_name)
        plural_name = _pluralize(entity_name)

        lines.append(f"// ── {entity_name} ──────────────────────────────────")
        lines.append(f"annotate {entity_name} with @(")

        # --- UI.HeaderInfo ---
        lines.append(f"    UI.HeaderInfo: {{")
        lines.append(f"        TypeName: '{human_name}',")
        lines.append(f"        TypeNamePlural: '{plural_name}',")
        lines.append(f"        Title: {{ Value: {title_field} }},")
        lines.append(f"        Description: {{ Value: {desc_field} }},")
        lines.append(f"        TypeImageUrl: '{icon}'")
        lines.append(f"    }},")

        # --- UI.SelectionFields ---
        if filter_fields:
            lines.append(f"    UI.SelectionFields: [")
            for i, ff in enumerate(filter_fields):
                comma = "," if i < len(filter_fields) - 1 else ""
                lines.append(f"        {ff}{comma}")
            lines.append(f"    ],")

        # --- UI.LineItem ---
        lines.append(f"    UI.LineItem: [")
        for i, field in enumerate(display_fields):
            fname = field.get("name", "")
            comma = "," if i < len(display_fields) - 1 or (status_field and status_field not in [f.get("name") for f in display_fields]) else ""

            if _is_status_field(fname):
                lines.append(f"        {{ Value: {fname}, Criticality: criticality, ![@UI.Importance]: #High }}{comma}")
            elif _is_priority_field(fname):
                lines.append(f"        {{ Value: {fname}, ![@UI.Importance]: #High }}{comma}")
            elif _is_amount_field(fname):
                lines.append(f"        {{ Value: {fname}, ![@UI.Importance]: #High }}{comma}")
            else:
                lines.append(f"        {{ Value: {fname} }}{comma}")
        lines.append(f"    ],")

        # --- UI.DataPoint for status ---
        if status_field:
            lines.append(f"    UI.DataPoint#StatusDP: {{")
            lines.append(f"        Value: {status_field},")
            lines.append(f"        Title: 'Status',")
            lines.append(f"        Criticality: criticality")
            lines.append(f"    }},")

        # --- UI.DataPoint for total amount ---
        if amount_fields:
            first_amount = amount_fields[0]
            lines.append(f"    UI.DataPoint#AmountDP: {{")
            lines.append(f"        Value: {first_amount},")
            lines.append(f"        Title: '{_humanize(first_amount)}'")
            lines.append(f"    }},")

        # --- UI.HeaderFacets ---
        header_facets = []
        if status_field:
            header_facets.append("        { $Type: 'UI.ReferenceFacet', Target: '@UI.DataPoint#StatusDP' }")
        if amount_fields:
            header_facets.append("        { $Type: 'UI.ReferenceFacet', Target: '@UI.DataPoint#AmountDP' }")
        if header_facets:
            lines.append(f"    UI.HeaderFacets: [")
            for i, hf in enumerate(header_facets):
                comma = "," if i < len(header_facets) - 1 else ""
                lines.append(f"{hf}{comma}")
            lines.append(f"    ],")

        # --- UI.Facets (Object Page sections) ---
        lines.append(f"    UI.Facets: [")
        lines.append(f"        {{")
        lines.append(f"            $Type: 'UI.ReferenceFacet',")
        lines.append(f"            Label: 'General Information',")
        lines.append(f"            Target: '@UI.FieldGroup#GeneralInfo'")
        lines.append(f"        }},")

        if status_field or priority_field:
            lines.append(f"        {{")
            lines.append(f"            $Type: 'UI.ReferenceFacet',")
            lines.append(f"            Label: 'Status & Details',")
            lines.append(f"            Target: '@UI.FieldGroup#StatusDetails'")
            lines.append(f"        }},")

        # Composition children as List facets
        for child_rel in children:
            child_name = child_rel.get("target_entity", "")
            rel_name = child_rel.get("name", child_name.lower())
            lines.append(f"        {{")
            lines.append(f"            $Type: 'UI.ReferenceFacet',")
            lines.append(f"            Label: '{_pluralize(child_name)}',")
            lines.append(f"            Target: '{rel_name}/@UI.LineItem'")
            lines.append(f"        }},")

        # Admin section
        lines.append(f"        {{")
        lines.append(f"            $Type: 'UI.ReferenceFacet',")
        lines.append(f"            Label: 'Administrative Data',")
        lines.append(f"            Target: '@UI.FieldGroup#AdminData'")
        lines.append(f"        }}")
        lines.append(f"    ],")

        # --- UI.FieldGroup#GeneralInfo ---
        general_fields = [f for f in fields if not f.get("key") and not _is_status_field(f.get("name", ""))
                          and not _is_priority_field(f.get("name", ""))
                          and f.get("name", "").lower() not in ("createdat", "createdby", "modifiedat", "modifiedby")
                          ][:8]
        lines.append(f"    UI.FieldGroup#GeneralInfo: {{")
        lines.append(f"        Data: [")
        for i, field in enumerate(general_fields):
            fname = field.get("name", "")
            comma = "," if i < len(general_fields) - 1 else ""
            if _is_amount_field(fname):
                lines.append(f"            {{ Value: {fname}, Label: '{_humanize(fname)}' }}{comma}")
            else:
                lines.append(f"            {{ Value: {fname} }}{comma}")
        lines.append(f"        ]")
        lines.append(f"    }},")

        # --- UI.FieldGroup#StatusDetails ---
        if status_field or priority_field:
            lines.append(f"    UI.FieldGroup#StatusDetails: {{")
            lines.append(f"        Data: [")
            status_items = []
            if status_field:
                status_items.append(f"            {{ Value: {status_field}, Criticality: criticality }}")
            if priority_field:
                status_items.append(f"            {{ Value: {priority_field} }}")
            # Add date fields
            for f in fields:
                if _is_date_field(f) and f.get("name", "").lower() not in ("createdat", "modifiedat"):
                    status_items.append(f"            {{ Value: {f.get('name')} }}")
            for i, item in enumerate(status_items):
                comma = "," if i < len(status_items) - 1 else ""
                lines.append(f"{item}{comma}")
            lines.append(f"        ]")
            lines.append(f"    }},")

        # --- UI.FieldGroup#AdminData ---
        lines.append(f"    UI.FieldGroup#AdminData: {{")
        lines.append(f"        Data: [")
        lines.append(f"            {{ Value: createdBy, Label: 'Created By' }},")
        lines.append(f"            {{ Value: createdAt, Label: 'Created On' }},")
        lines.append(f"            {{ Value: modifiedBy, Label: 'Modified By' }},")
        lines.append(f"            {{ Value: modifiedAt, Label: 'Modified On' }}")
        lines.append(f"        ]")
        lines.append(f"    }}")
        lines.append(f");")
        lines.append("")

        # --- Field-level annotations ---
        has_field_annots = False
        field_annot_lines = []
        for f in fields:
            fname = f.get("name", "")
            if _is_status_field(fname) or _is_priority_field(fname):
                field_annot_lines.append(f"    {fname} @Common.ValueListWithFixedValues;")
                has_field_annots = True

        if has_field_annots:
            lines.append(f"annotate {entity_name} with {{")
            lines.extend(field_annot_lines)
            lines.append(f"}};")
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
    1. srv/service.cds - Service definition with projections, draft, and actions
    2. srv/annotations.cds - Deep Fiori annotations (HeaderInfo, LineItem, Facets, DataPoint)
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
    
    service_name = "".join(
        word.capitalize()
        for word in project_name.replace("-", " ").replace("_", " ").split()
    )
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
                log_progress(state, "✅ LLM-generated service definition accepted.")
                
                if parsed.get("annotations_cds"):
                    generated_files.append({
                        "path": "srv/annotations.cds",
                        "content": parsed["annotations_cds"],
                        "file_type": "cds",
                    })
                    log_progress(state, "✅ LLM-generated annotations accepted.")
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required service elements. Falling back.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for service exposure: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation (industry-grade)
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
            log_progress(state, "Generating srv/annotations.cds with deep Fiori annotations...")
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
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("service_exposure", 0)
    
    service_artifact = next((f for f in generated_files if f["path"] == "srv/service.cds"), None)
    if service_artifact and llm_success:
        validation_results = validate_artifact(service_artifact["path"], service_artifact["content"])
        
        if any(result.has_errors for result in validation_results):
            if should_retry_agent(validation_results, retry_count, max_retries):
                log_progress(state, f"Validation found errors. Attempting correction (retry {retry_count + 1}/{max_retries})...")
                
                if "retry_counts" not in state:
                    state["retry_counts"] = {}
                state["retry_counts"]["service_exposure"] = retry_count + 1
                state["needs_correction"] = True
                
                if "correction_history" not in state:
                    state["correction_history"] = []
                state["correction_history"].append({
                    "agent": "service_exposure",
                    "retry": retry_count + 1,
                    "errors_found": sum(r.error_count for r in validation_results),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            log_progress(state, f"  - {issue.message}")
                
                state["artifacts_srv"] = []
                return state
            else:
                log_progress(state, "⚠️ Max retries reached. Some validation errors remain.")
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            errors.append({
                                "agent": "service_exposure",
                                "code": issue.code or "VALIDATION_ERROR",
                                "message": issue.message,
                                "field": None,
                                "severity": "warning"
                            })
        else:
            if retry_count > 0:
                log_progress(state, f"✅ Validation passed after {retry_count} correction(s)")
                summary = format_correction_summary("service_exposure", retry_count, retry_count, retry_count)
                if "auto_fixed_errors" not in state:
                    state["auto_fixed_errors"] = []
                state["auto_fixed_errors"].append({
                    "agent": "service_exposure",
                    "summary": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                log_progress(state, "✅ Validation passed on first attempt")

    state["needs_correction"] = False
    
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
        "retry_count": retry_count,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Service exposure complete ({generation_method}). Generated {len(generated_files)} files.")
    logger.info(f"Service Exposure Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
