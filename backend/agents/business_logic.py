"""
Agent 4: CAP Business Logic Agent (LLM-Driven)

Generates JavaScript event handlers for entity lifecycle events,
custom actions, validations, calculations, and side effects.

FULLY LLM-DRIVEN with inter-agent context: reads actual schema.cds
AND service.cds from previous agents to generate matching handlers.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.llm_utils import (
    generate_with_retry,
    get_schema_context,
    get_service_context,
    store_generated_content,
)
from backend.agents.knowledge_loader import get_business_logic_knowledge
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
)
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompt
# =============================================================================

BUSINESS_LOGIC_SYSTEM_PROMPT = """You are a senior SAP CAP (Cloud Application Programming Model) developer with 10+ years of experience.
Generate production-ready, enterprise-grade JavaScript service handlers for SAP CAP services.

ARCHITECTURE RULES:

1. Module pattern: `const cds = require('@sap/cds'); module.exports = cds.service.impl(async function() { ... });`
2. Destructure entities: `const { Entity1, Entity2 } = this.entities;`
3. Use `cds.log()` for structured logging: `const LOG = cds.log('service-name');`
4. Events: `this.before('CREATE', Entity, handler)`, `this.after('READ', Entity, handler)`, `this.on('approve', handler)`
5. CDS QL patterns (MUST USE `cds.tx(req)` for transactional safety):
   - Obtain transaction: `const tx = cds.tx(req);`
   - SELECT: `const result = await tx.run(SELECT.from(Entity).where({field: value}));`
   - INSERT: `await tx.run(INSERT.into(Entity).entries(data));`
   - UPDATE: `await tx.run(UPDATE(Entity).set({field: value}).where({ID: id}));`
   - DELETE: `await tx.run(DELETE.from(Entity).where({ID: id}));`
   - Aggregate: `const { count } = await tx.run(SELECT.one.from(Entity).columns('count(*) as count'));`

6. ROBUST ERROR HANDLING (MANDATORY):
   - Wrap all logic in `try ... catch` blocks.
   - On error, rollback is automatic, but log with `LOG.error(e)`.
   - Reject bad inputs using `req.reject(400, 'Message')`.
   - Warn non-fatal issues using `req.warn(400, 'Warning Message')`.

STATUS STATE MACHINES — implement for every entity with a 'status' field:
```javascript
const STATUS_TRANSITIONS = {
    'Draft':     ['Submitted'],
    'Submitted': ['Approved', 'Rejected'],
    'Approved':  ['InProcess', 'Cancelled'],
    'InProcess': ['Completed', 'OnHold'],
    'OnHold':    ['InProcess', 'Cancelled'],
    'Completed': [],
    'Rejected':  ['Draft'],
    'Cancelled': []
};
```

CASCADING CALCULATIONS — for parent-child compositions:
```javascript
this.after(['CREATE', 'UPDATE', 'DELETE'], 'OrderItem', async (data, req) => {
    const parentID = data.parent_ID || req.data.parent_ID;
    if (!parentID) return;
    const items = await SELECT.from(OrderItem).where({ parent_ID: parentID });
    const totalAmount = items.reduce((sum, item) => sum + (item.quantity * item.unitPrice), 0);
    await UPDATE(Order).set({ totalAmount }).where({ ID: parentID });
});
```

AUTO-NUMBERING:
```javascript
this.before('CREATE', Invoice, async (req) => {
    const { count } = await SELECT.one.from(Invoice).columns('count(*) as count');
    const year = new Date().getFullYear();
    req.data.invoiceNumber = `INV-${year}-${String(count + 1).padStart(5, '0')}`;
});
```

INPUT VALIDATION:
```javascript
this.before(['CREATE', 'UPDATE'], Entity, (req) => {
    const { email, startDate, endDate } = req.data;
    if (email && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {
        req.error(400, 'Invalid email format', 'email');
    }
    if (startDate && endDate && new Date(endDate) <= new Date(startDate)) {
        req.error(400, 'End date must be after start date', 'endDate');
    }
});
```

DOMAIN-SPECIFIC PATTERNS — Analyze the entities and generate appropriate patterns:

1. FINANCIAL ENTITIES (with amount/price/total fields):
   - Currency-aware rounding: `Math.round(amount * 100) / 100`
   - Tax calculations: `taxAmount = netAmount * taxRate`
   - Parent total aggregation from line items
   - Budget validation: prevent overspending

2. INVENTORY/WAREHOUSE ENTITIES (with stock/quantity fields):
   - Stock deduction on order/shipment creation
   - Low stock warnings via `req.warn()`
   - Prevent negative stock levels
   - Reservation handling

3. HR/EMPLOYEE ENTITIES (with leave/timesheet/position fields):
   - Leave balance checking
   - Overlapping date range validation
   - Manager approval workflows
   - Working days calculation

4. ORDER/SALES ENTITIES (with orderNumber/status/items):
   - Auto-numbering with prefix+year+sequence
   - Order-to-invoice conversion actions
   - Line item totals cascade to header
   - Discount and tax calculations

5. SCHEDULING ENTITIES (with date/time/resource fields):
   - Conflict detection for overlapping slots
   - Duration calculation
   - Recurring event handling
   - Capacity checking

6. CRM/CUSTOMER ENTITIES (with lead/opportunity/pipeline fields):
   - Lead scoring calculations
   - Pipeline stage progression
   - Conversion rate tracking
   - Activity logging

OUTPUT FORMAT:
Return a JSON object with these keys (depending on the modular services you generate):
{
    "admin_service_js": "... full srv/admin-service.js content ...",
    "catalog_service_js": "... full srv/catalog-service.js content ...",
    "validation_js": "... srv/lib/validation.js utility ...",
    "numbering_js": "... srv/lib/numbering.js utility ..."
}

Return ONLY valid JSON."""


HANDLER_GENERATION_PROMPT = """Generate complete service handlers for this SAP CAP application.

Project Name: {project_name}
Service Name: {service_name}

{schema_context}
{service_context}

ENTITIES:
{entities_json}

RELATIONSHIPS:
{relationships_json}

BUSINESS RULES:
{business_rules_json}

REQUIREMENTS:
1. Modular Service Handlers (e.g., srv/admin-service.js, srv/catalog-service.js) — Complete handler files with:
   - ALL entity lifecycle handlers (before/after CREATE, READ, UPDATE, DELETE)
   - Status validation with state machine transitions
   - Input validation (email, phone, date ranges, required fields)
   - Cascading calculations for parent-child compositions
   - Auto-numbering for sequential ID fields
   - Custom action implementations for business rules (not just stubs!)
   - Delete guards for referential integrity
   - Structured logging
   - Role-based scoping/checks (e.g., checking `req.user.is('admin')`) if applicable

2. srv/lib/validation.js — Reusable validators:
   - Email, phone, date range, field format validators
   - Used by service.js

3. srv/lib/numbering.js — Sequential ID generation:
   - Year-prefixed auto-numbering utility
   - Used by the modular service handlers

IMPORTANT: Generate REAL business logic, not empty stubs. Every action
defined in the service CDS must have a complete implementation.

Respond with ONLY valid JSON."""


# =============================================================================
# Main Agent Function
# =============================================================================

async def business_logic_agent(state: BuilderState) -> BuilderState:
    """
    CAP Business Logic Agent (LLM-Driven)

    Uses LLM to generate production-quality service handlers.
    Reads actual schema.cds and service.cds for consistency.
    """
    logger.info("Starting Business Logic Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "business_logic"
    state["updated_at"] = now
    state["current_logs"] = []

    log_progress(state, "Starting business logic phase...")

    entities = state.get("entities", [])
    if not entities:
        log_progress(state, "Error: No entities found.")
        return state

    project_name = state.get("project_name", "App")
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])

    service_name = "".join(
        word.capitalize()
        for word in project_name.replace("-", " ").replace("_", " ").split()
    )
    service_name = f"{service_name}Service"

    # Get inter-agent context
    schema_context = get_schema_context(state)
    service_context = get_service_context(state)
    knowledge = get_business_logic_knowledge()

    prompt = HANDLER_GENERATION_PROMPT.format(
        project_name=project_name,
        service_name=service_name,
        schema_context=schema_context or "(schema not available)",
        service_context=service_context or "(service CDS not available)",
        entities_json=json.dumps(entities, indent=2),
        relationships_json=json.dumps(relationships, indent=2),
        business_rules_json=json.dumps(business_rules, indent=2),
    )

    # Inject knowledge into prompt
    prompt = f"{knowledge}\n\n{prompt}"

    # Self-Healing: Inject correction context if present
    correction_context = state.get("correction_context")
    if state.get("needs_correction") and state.get("correction_agent") == "business_logic" and correction_context:
        log_progress(state, "Applying self-healing correction context from validation agent...")
        correction_prompt = correction_context.get("correction_prompt", "")
        if correction_prompt:
            prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

    log_progress(state, "Calling LLM for business logic generation...")

    result = await generate_with_retry(
        prompt=prompt,
        system_prompt=BUSINESS_LOGIC_SYSTEM_PROMPT,
        state=state,
        required_keys=["service_js"],
        max_retries=3,
        agent_name="business_logic",
    )

    if result and any(k.endswith('_service_js') or k == 'service_js' for k in result.keys()):
        # Handle modular services or single service fallback
        handler_keys = [k for k in result.keys() if k.endswith('_service_js') or k == 'service_js']
        
        valid_handlers = False
        for key in handler_keys:
            handler_content = result[key]
            
            # Use original filename if service_js, else convert admin_service_js -> admin-service.js
            filename = 'service.js' if key == 'service_js' else key.replace('_js', '.js').replace('_', '-')
            
            if "cds" in handler_content.lower() or "module.exports" in handler_content:
                generated_files.append({
                    "path": f"srv/{filename}",
                    "content": handler_content,
                    "file_type": "javascript",
                })
                log_progress(state, f"✅ Generated service handler ({filename}).")
                valid_handlers = True

            if result.get("validation_js"):
                generated_files.append({
                    "path": "srv/lib/validation.js",
                    "content": result["validation_js"],
                    "file_type": "javascript",
                })
                log_progress(state, "✅ Generated validation utilities.")

            if result.get("numbering_js"):
                generated_files.append({
                    "path": "srv/lib/numbering.js",
                    "content": result["numbering_js"],
                    "file_type": "javascript",
                })
                log_progress(state, "✅ Generated numbering utilities.")
        if not valid_handlers:
            log_progress(state, "⚠️ Handler content looks invalid. Generating minimal modular handlers.")
            generated_files.extend(_minimal_handler(entities, service_name))
    else:
        log_progress(state, "⚠️ LLM generation failed. Generating minimal modular handlers.")
        generated_files.extend(_minimal_handler(entities, service_name))
        errors.append({
            "agent": "business_logic",
            "code": "LLM_FAILED",
            "message": "LLM handler generation failed. Minimal handler generated.",
            "field": None,
            "severity": "warning",
        })

    store_generated_content(state, generated_files, {
        "admin-service.js": "generated_handler_js",
        "service.js": "generated_handler_js" # Fallback mapping
    })

    # Update state — append to existing srv artifacts
    existing_srv = state.get("artifacts_srv", [])
    state["artifacts_srv"] = existing_srv + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    state["needs_correction"] = False

    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "business_logic",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Business logic complete. Generated {len(generated_files)} files.")
    return state


# =============================================================================
# Minimal Fallback
# =============================================================================

def _minimal_handler(entities: list, service_name: str) -> list[GeneratedFile]:
    """Generate minimal valid modular service handlers."""
    generated_files = []

    # split entities into two mock services: Admin and Catalog
    admin_entities = entities[:len(entities)//2] if len(entities) > 1 else entities
    catalog_entities = entities[len(entities)//2:] if len(entities) > 1 else []

    services = [
        {"name": f"{service_name}Admin", "path": f"{service_name.lower().replace('service', '')}-admin-service.js", "entities": admin_entities},
        {"name": f"{service_name}Catalog", "path": f"{service_name.lower().replace('service', '')}-catalog-service.js", "entities": catalog_entities}
    ]

    for svc in services:
        if not svc["entities"]:
            continue

        entity_names = [e.get("name", "") for e in svc["entities"]]
        destructure = ", ".join(entity_names)

        lines = [
            "const cds = require('@sap/cds');",
            f"const LOG = cds.log('{svc['name']}');",
            "",
            "module.exports = cds.service.impl(async function() {",
            f"  const {{ {destructure} }} = this.entities;",
            "",
        ]

        for entity in svc["entities"]:
            name = entity.get("name", "")
            lines.append(f"  // {name} handlers")
            lines.append(f"  this.before('CREATE', {name}, (req) => {{")
            lines.append(f"    LOG.info('Creating {name}:', req.data);")
            lines.append(f"  }});")
            lines.append("")

        lines.append("});")
        
        generated_files.append({
            "path": f"srv/{svc['path']}",
            "content": "\n".join(lines),
            "file_type": "javascript"
        })

    return generated_files
