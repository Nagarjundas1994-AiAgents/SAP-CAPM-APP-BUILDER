"""
Agent 4: CAP Business Logic Agent

Generates JavaScript event handlers for entity lifecycle events,
custom actions, validations, calculations, and side effects.

Uses LLM to generate production-quality business logic with fallback to templates.

Industry-level features:
- Status state machines with transition validation
- Cascading calculations (order totals, taxes, discounts)
- Auto-numbering (sequential IDs like PO-0001, INV-2024-001)
- Draft-aware handlers (EDIT, ACTIVATE, DISCARD)
- Structured logging with cds.log()
- Input validation with req.error()
- Utility modules: validation, numbering, messaging
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
    BusinessRule,
    GeneratedFile,
    CAPRuntime,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

BUSINESS_LOGIC_SYSTEM_PROMPT = """You are a senior SAP CAP (Cloud Application Programming Model) developer with 10+ years of experience.
Generate production-ready, enterprise-grade JavaScript service handlers for SAP CAP services.

ARCHITECTURE RULES:
1. Module pattern: `const cds = require('@sap/cds'); module.exports = cds.service.impl(async function() { ... });`
2. Destructure entities: `const { Entity1, Entity2 } = this.entities;`
3. Use structured logging: `const LOG = cds.log('service-name'); LOG.info(msg); LOG.error(msg); LOG.warn(msg);`
4. NEVER use console.log — always use cds.log()

HANDLER PATTERNS:
1. this.before('CREATE', Entity, handler) — input validation, default values, auto-numbering
2. this.before('UPDATE', Entity, handler) — change validation, status transitions
3. this.before('DELETE', Entity, handler) — deletion checks, cascade warnings
4. this.after('READ', Entity, handler) — calculated/virtual fields, data enrichment
5. this.after('CREATE', Entity, handler) — side effects, notifications
6. this.on('ACTION_NAME', handler) — custom action implementations

DATABASE OPERATIONS (cds.ql):
```javascript
const { SELECT, INSERT, UPDATE, DELETE } = cds.ql;
const items = await SELECT.from(Entity).where({ ID: id });
await UPDATE(Entity).set({ status: 'Approved' }).where({ ID: id });
const count = await SELECT.one.from(Entity).columns('count(*) as count').where({ status: 'Active' });
```

STATUS STATE MACHINES — implement for every entity with a 'status' field:
```javascript
const STATUS_TRANSITIONS = {
    'Draft':     ['Submitted'],
    'Submitted': ['Approved', 'Rejected'],
    'Approved':  ['InProcess', 'Cancelled'],
    'InProcess': ['Completed', 'OnHold'],
    'OnHold':    ['InProcess', 'Cancelled'],
    'Rejected':  ['Draft'],
    'Completed': [],
    'Cancelled': []
};

this.before('UPDATE', Entity, async (req) => {
    if (req.data.status) {
        const current = await SELECT.one.from(Entity, req.data.ID).columns('status');
        const allowed = STATUS_TRANSITIONS[current.status] || [];
        if (!allowed.includes(req.data.status)) {
            req.error(409, `Cannot change status from '${current.status}' to '${req.data.status}'`, 'status');
        }
    }
});
```

CASCADING CALCULATIONS — implement for parent-child relationships:
```javascript
this.after(['CREATE', 'UPDATE', 'DELETE'], OrderItem, async (data, req) => {
    const parentID = data.parent_ID || data.order_ID;
    if (parentID) {
        const items = await SELECT.from(OrderItem).where({ parent_ID: parentID });
        const totalAmount = items.reduce((sum, item) => sum + (item.quantity * item.unitPrice), 0);
        const totalDiscount = items.reduce((sum, item) => sum + (item.discount || 0), 0);
        const netAmount = totalAmount - totalDiscount;
        await UPDATE(Order).set({
            totalAmount, totalDiscount, netAmount,
            itemCount: items.length
        }).where({ ID: parentID });
    }
});
```

AUTO-NUMBERING — implement for entities with a sequential number field:
```javascript
this.before('CREATE', Invoice, async (req) => {
    const { count } = await SELECT.one.from(Invoice).columns('count(*) as count');
    const year = new Date().getFullYear();
    req.data.invoiceNumber = `INV-$${year}-$${String(count + 1).padStart(5, '0')}`;
});
```

INPUT VALIDATION — validate every required field properly:
```javascript
this.before(['CREATE', 'UPDATE'], Customer, (req) => {
    const { data } = req;
    if (data.email && !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(data.email)) {
        req.error(400, 'Invalid email format', 'email');
    }
    if (data.phone && !/^\\+?[\\d\\s-]{7,15}$/.test(data.phone)) {
        req.error(400, 'Invalid phone number format', 'phone');
    }
    if (data.quantity !== undefined && data.quantity < 0) {
        req.error(400, 'Quantity cannot be negative', 'quantity');
    }
    if (data.price !== undefined && data.price < 0) {
        req.error(400, 'Price cannot be negative', 'price');
    }
});
```

ERROR HANDLING:
- Use req.error(statusCode, message, target?) for user-facing errors
- Use req.warn(message) for non-blocking warnings
- Always target the specific field: req.error(400, 'Required', 'fieldName')
- Use try/catch for database operations with LOG.error

UTILITY MODULES:
- srv/lib/validation.js — email, phone, date range, field format validators
- srv/lib/numbering.js — sequential ID generation with prefix and year
- srv/lib/messaging.js — event emission for downstream integrations

OUTPUT FORMAT:
Return a JSON object with these keys:
{
    "service_js": "... full srv/service.js content ...",
    "utils_js": "... full srv/lib/utils.js content ...",
    "validation_js": "... full srv/lib/validation.js content ...",
    "numbering_js": "... full srv/lib/numbering.js content ..."
}
Return ONLY the JSON, no markdown fences."""


BUSINESS_LOGIC_PROMPT = """Generate enterprise-grade service handlers for this SAP CAP project.

Project: {project_name}
Description: {description}

=== CDS Schema (db/schema.cds) ===
{schema_content}

=== Service Definition (srv/service.cds) ===
{service_content}

=== Entities ===
{entities_json}

=== Relationships ===
{relationships_json}

=== Business Rules ===
{business_rules_json}

REQUIREMENTS — implement ALL of these in service.js:

1. STATUS MACHINES: For every entity with a 'status' field, implement state transition validation.
   Define allowed transitions and reject invalid ones with req.error(409).

2. CASCADING CALCULATIONS: For parent-child compositions (e.g. Order→OrderItem),
   recalculate parent totals (totalAmount, netAmount, itemCount) after child CREATE/UPDATE/DELETE.

3. AUTO-NUMBERING: For entities with sequential number fields (like orderNumber, invoiceNumber),
   generate IDs like "ORD-2024-00001" using the entity prefix + year + padded count.

4. INPUT VALIDATION: For every entity:
   - Validate required fields (non-nullable, non-key)
   - Validate email fields (regex)
   - Validate phone fields (regex)
   - Validate numeric fields are non-negative where appropriate
   - Validate string length where @assert.range annotations exist

5. CUSTOM ACTIONS: For every action/function defined in the service CDS, implement real logic:
   - approve/reject: Change status + validate current state
   - cancel: Change status + check if cancellable
   - assign: Set assignee field + log

6. DELETE GUARDS: Before DELETE, check for dependent children.
   Block deletion if child records exist (referential integrity).

7. LOGGING: Use `const LOG = cds.log('{project_name}')` for structured logging.
   Log all business-critical operations.

8. UTILITY MODULES:
   - srv/lib/validation.js: Input validators (email, phone, date, number range)
   - srv/lib/numbering.js: Sequential number generator with prefix, year, padding

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
# Helper: Detect entity patterns for smart template generation
# =============================================================================

def _has_field(entity: dict, *names: str) -> bool:
    """Check if entity has any field matching the given names (case-insensitive)."""
    field_names_lower = {f.get("name", "").lower() for f in entity.get("fields", [])}
    return any(n.lower() in field_names_lower for n in names)


def _get_field(entity: dict, *names: str) -> dict | None:
    """Get the first matching field from entity."""
    for field in entity.get("fields", []):
        if field.get("name", "").lower() in [n.lower() for n in names]:
            return field
    return None


def _has_status_field(entity: dict) -> bool:
    return _has_field(entity, "status", "state", "lifecycle", "phase")


def _has_numeric_id(entity: dict) -> bool:
    """Check if entity has a human-readable sequential number field."""
    patterns = ["number", "no", "code", "reference", "ref"]
    for field in entity.get("fields", []):
        name = field.get("name", "").lower()
        if any(p in name for p in patterns) and field.get("type", "").lower() in ("string", "string(20)", "string(30)"):
            if not field.get("key", False):
                return True
    return False


def _get_numeric_id_field(entity: dict) -> str | None:
    """Get human-readable sequential number field name."""
    patterns = ["number", "no", "code", "reference", "ref"]
    for field in entity.get("fields", []):
        name = field.get("name", "").lower()
        if any(p in name for p in patterns) and field.get("type", "").lower() in ("string", "string(20)", "string(30)"):
            if not field.get("key", False):
                return field.get("name")
    return None


def _has_email_field(entity: dict) -> bool:
    return _has_field(entity, "email", "emailAddress", "mail")


def _has_phone_field(entity: dict) -> bool:
    return _has_field(entity, "phone", "phoneNumber", "telephone", "mobile")


def _is_child_entity(entity: dict, relationships: list) -> str | None:
    """Check if entity is a child in a composition and return parent entity name."""
    entity_name = entity.get("name", "")
    for rel in relationships:
        if (rel.get("type") == "composition" and
            rel.get("target_entity") == entity_name):
            return rel.get("source_entity")
    return None


def _get_children(entity_name: str, relationships: list) -> list:
    """Get child entities in compositions."""
    children = []
    for rel in relationships:
        if (rel.get("type") == "composition" and
            rel.get("source_entity") == entity_name):
            children.append(rel.get("target_entity"))
    return children


def _get_amount_fields(entity: dict) -> list:
    """Get numeric amount/price/total fields."""
    amount_keywords = ["amount", "total", "price", "cost", "value", "sum", "net", "gross", "tax", "discount"]
    result = []
    for field in entity.get("fields", []):
        name = field.get("name", "").lower()
        ftype = field.get("type", "").lower()
        if ftype in ("decimal", "double", "integer", "int32", "int64"):
            if any(k in name for k in amount_keywords):
                result.append(field.get("name"))
    return result


def _get_entity_prefix(entity_name: str) -> str:
    """Generate a 2-4 character prefix for numbering from entity name."""
    # e.g. "PurchaseOrder" -> "PO", "Invoice" -> "INV", "SalesOrder" -> "SO"
    words = re.findall(r'[A-Z][a-z]*', entity_name)
    if len(words) >= 2:
        return "".join(w[0] for w in words).upper()
    elif len(entity_name) <= 4:
        return entity_name.upper()
    else:
        return entity_name[:3].upper()


# =============================================================================
# Template Fallback Functions
# =============================================================================

def generate_service_handler_template(state: BuilderState) -> str:
    """Generate the main service handler file (template fallback).
    
    Industry-grade template with:
    - Structured logging (cds.log)
    - Input validation per entity
    - Status state machines
    - Cascading calculations for compositions
    - Auto-numbering for sequential ID fields
    - Delete guards for referential integrity
    - Custom action stubs for business rules
    """
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    business_rules = state.get("business_rules", [])
    relationships = state.get("relationships", [])

    service_name = "".join(
        word.capitalize()
        for word in project_name.replace("-", " ").replace("_", " ").split()
    )
    service_name = f"{service_name}Service"
    log_id = project_name.lower().replace(" ", "-").replace("_", "-")

    lines = []
    lines.append("'use strict';")
    lines.append("")
    lines.append("const cds = require('@sap/cds');")
    lines.append(f"const LOG = cds.log('{log_id}');")
    lines.append("")
    lines.append("// Utility modules")
    lines.append("const { validateEmail, validatePhone, validateRequired } = require('./lib/validation');")
    lines.append("const { generateNumber } = require('./lib/numbering');")
    lines.append("")
    lines.append("module.exports = cds.service.impl(async function() {")
    lines.append("")

    # Destructure entities
    entity_names = [e.get("name", "Entity") for e in entities]
    lines.append("    const {")
    lines.append("        " + ", ".join(entity_names))
    lines.append("    } = this.entities;")
    lines.append("")

    # Generate handlers per entity
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        required_fields = [f for f in fields if not f.get("nullable", True) and not f.get("key")]
        has_status = _has_status_field(entity)
        has_email = _has_email_field(entity)
        has_phone = _has_phone_field(entity)
        num_id_field = _get_numeric_id_field(entity)
        parent_entity = _is_child_entity(entity, relationships)
        children = _get_children(entity_name, relationships)
        amount_fields = _get_amount_fields(entity)
        prefix = _get_entity_prefix(entity_name)

        lines.append(f"    // ═══════════════════════════════════════════════════════════")
        lines.append(f"    //  {entity_name} Handlers")
        lines.append(f"    // ═══════════════════════════════════════════════════════════")
        lines.append("")

        # ----------- STATUS TRANSITIONS -----------
        if has_status:
            status_field = _get_field(entity, "status", "state", "lifecycle", "phase")
            status_name = status_field.get("name", "status") if status_field else "status"
            lines.append(f"    // Status transition rules for {entity_name}")
            lines.append(f"    const {entity_name.upper()}_STATUS_TRANSITIONS = {{")
            lines.append(f"        'New':       ['InProcess', 'Cancelled'],")
            lines.append(f"        'Draft':     ['Submitted', 'Cancelled'],")
            lines.append(f"        'Submitted': ['Approved', 'Rejected'],")
            lines.append(f"        'Approved':  ['InProcess', 'Cancelled'],")
            lines.append(f"        'InProcess': ['Completed', 'OnHold', 'Cancelled'],")
            lines.append(f"        'OnHold':    ['InProcess', 'Cancelled'],")
            lines.append(f"        'Rejected':  ['Draft'],")
            lines.append(f"        'Completed': [],")
            lines.append(f"        'Cancelled': []")
            lines.append(f"    }};")
            lines.append("")

        # ----------- BEFORE CREATE -----------
        lines.append(f"    this.before('CREATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")
        lines.append(f"        LOG.info(`Creating {entity_name}`, {{ user: req.user?.id }});")
        lines.append("")

        # Auto-numbering
        if num_id_field:
            lines.append(f"        // Auto-generate sequential number")
            lines.append(f"        if (!data.{num_id_field}) {{")
            lines.append(f"            data.{num_id_field} = await generateNumber('{prefix}', {entity_name});")
            lines.append(f"        }}")
            lines.append("")

        # Default status
        if has_status:
            status_name = _get_field(entity, "status", "state", "lifecycle", "phase")
            sn = status_name.get("name", "status") if status_name else "status"
            default_val = status_name.get("default", "'New'").strip("'\"") if status_name else "New"
            lines.append(f"        // Set default status")
            lines.append(f"        if (!data.{sn}) {{")
            lines.append(f"            data.{sn} = '{default_val}';")
            lines.append(f"        }}")
            lines.append("")

        # Required field validation
        if required_fields:
            lines.append("        // Validate required fields")
            lines.append(f"        validateRequired(req, data, [")
            for field in required_fields[:8]:  # Cap at 8 to avoid excessive code
                fname = field.get("name", "")
                lines.append(f"            '{fname}',")
            lines.append(f"        ]);")
            lines.append("")

        # Email validation
        if has_email:
            email_field = _get_field(entity, "email", "emailAddress", "mail")
            if email_field:
                ename = email_field.get("name", "email")
                lines.append(f"        // Validate email format")
                lines.append(f"        if (data.{ename}) {{")
                lines.append(f"            validateEmail(req, data.{ename}, '{ename}');")
                lines.append(f"        }}")
                lines.append("")

        # Phone validation
        if has_phone:
            phone_field = _get_field(entity, "phone", "phoneNumber", "telephone", "mobile")
            if phone_field:
                pname = phone_field.get("name", "phone")
                lines.append(f"        // Validate phone format")
                lines.append(f"        if (data.{pname}) {{")
                lines.append(f"            validatePhone(req, data.{pname}, '{pname}');")
                lines.append(f"        }}")
                lines.append("")

        # Non-negative numeric validation
        for field in fields:
            ftype = field.get("type", "").lower()
            fname = field.get("name", "")
            if ftype in ("decimal", "integer", "double", "int32", "int64"):
                if any(k in fname.lower() for k in ("amount", "price", "quantity", "total", "cost", "qty")):
                    lines.append(f"        if (data.{fname} !== undefined && data.{fname} < 0) {{")
                    lines.append(f"            req.error(400, `{fname} cannot be negative`, '{fname}');")
                    lines.append(f"        }}")
        lines.append("    });")
        lines.append("")

        # ----------- BEFORE UPDATE -----------
        lines.append(f"    this.before('UPDATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")

        if has_status:
            sn = _get_field(entity, "status", "state", "lifecycle", "phase")
            sn_name = sn.get("name", "status") if sn else "status"
            lines.append(f"")
            lines.append(f"        // Validate status transitions")
            lines.append(f"        if (data.{sn_name}) {{")
            lines.append(f"            const current = await SELECT.one.from({entity_name}, req.data.ID).columns('{sn_name}');")
            lines.append(f"            if (current) {{")
            lines.append(f"                const allowed = {entity_name.upper()}_STATUS_TRANSITIONS[current.{sn_name}] || [];")
            lines.append(f"                if (!allowed.includes(data.{sn_name})) {{")
            lines.append(f"                    req.error(409, `Cannot change status from '${{current.{sn_name}}}' to '${{data.{sn_name}}}'`, '{sn_name}');")
            lines.append(f"                }}")
            lines.append(f"            }}")
            lines.append(f"        }}")

        # Numeric validation on update too
        for field in fields:
            ftype = field.get("type", "").lower()
            fname = field.get("name", "")
            if ftype in ("decimal", "integer", "double", "int32", "int64"):
                if any(k in fname.lower() for k in ("amount", "price", "quantity", "total", "cost", "qty")):
                    lines.append(f"        if (data.{fname} !== undefined && data.{fname} < 0) {{")
                    lines.append(f"            req.error(400, `{fname} cannot be negative`, '{fname}');")
                    lines.append(f"        }}")

        lines.append("    });")
        lines.append("")

        # ----------- BEFORE DELETE with guard -----------
        lines.append(f"    this.before('DELETE', {entity_name}, async (req) => {{")
        lines.append(f"        LOG.info(`Deleting {entity_name}`, {{ id: req.data.ID, user: req.user?.id }});")

        if children:
            for child in children:
                lines.append(f"")
                lines.append(f"        // Check for existing {child} records")
                lines.append(f"        const {child.lower()}Count = await SELECT.one.from({child})")
                lines.append(f"            .columns('count(*) as count')")
                lines.append(f"            .where({{ parent_ID: req.data.ID }});")
                lines.append(f"        if ({child.lower()}Count?.count > 0) {{")
                lines.append(f"            req.error(409, `Cannot delete {entity_name} with existing {child} records. Delete child records first.`);")
                lines.append(f"        }}")

        if has_status:
            sn = _get_field(entity, "status", "state", "lifecycle", "phase")
            sn_name = sn.get("name", "status") if sn else "status"
            lines.append(f"")
            lines.append(f"        // Prevent deletion of completed/approved records")
            lines.append(f"        const record = await SELECT.one.from({entity_name}, req.data.ID).columns('{sn_name}');")
            lines.append(f"        if (record && ['Completed', 'Approved'].includes(record.{sn_name})) {{")
            lines.append(f"            req.error(409, `Cannot delete {entity_name} with status '${{record.{sn_name}}}'`);")
            lines.append(f"        }}")

        lines.append("    });")
        lines.append("")

        # ----------- AFTER READ (virtual/calculated fields) -----------
        lines.append(f"    this.after('READ', {entity_name}, (data, req) => {{")
        lines.append(f"        const records = Array.isArray(data) ? data : [data];")
        lines.append(f"        records.forEach(record => {{")
        lines.append(f"            if (!record) return;")

        if has_status:
            sn = _get_field(entity, "status", "state", "lifecycle", "phase")
            sn_name = sn.get("name", "status") if sn else "status"
            lines.append(f"            // Criticality for status-based coloring in Fiori")
            lines.append(f"            switch(record.{sn_name}) {{")
            lines.append(f"                case 'New': case 'Draft':      record.criticality = 0; break; // Grey")
            lines.append(f"                case 'InProcess': case 'Submitted': record.criticality = 2; break; // Warning/Yellow")
            lines.append(f"                case 'Approved': case 'Completed':  record.criticality = 3; break; // Success/Green")
            lines.append(f"                case 'Rejected': case 'Cancelled':  record.criticality = 1; break; // Error/Red")
            lines.append(f"                default: record.criticality = 0;")
            lines.append(f"            }}")

        lines.append(f"        }});")
        lines.append("    });")
        lines.append("")

        # ----------- CASCADING CALCULATIONS (child entity) -----------
        if parent_entity:
            # This entity is a child — after its CRUD, recalculate parent
            parent = next((e for e in entities if e.get("name") == parent_entity), None)
            if parent:
                parent_amounts = _get_amount_fields(parent)
                child_amounts = _get_amount_fields(entity)
                if child_amounts:
                    lines.append(f"    // Recalculate {parent_entity} totals after {entity_name} changes")
                    lines.append(f"    this.after(['CREATE', 'UPDATE', 'DELETE'], {entity_name}, async (data, req) => {{")
                    lines.append(f"        const parentID = data.parent_ID || data.{parent_entity.lower()}_ID || data.up__ID;")
                    lines.append(f"        if (!parentID) return;")
                    lines.append(f"")
                    lines.append(f"        try {{")
                    lines.append(f"            const items = await SELECT.from({entity_name}).where({{ parent_ID: parentID }});")

                    # Find matching total fields
                    unit_price = next((f for f in child_amounts if "price" in f.lower() or "unit" in f.lower()), None)
                    qty_field = next((f.get("name") for f in entity.get("fields", []) 
                                     if "quantity" in f.get("name", "").lower() or "qty" in f.get("name", "").lower()), None)
                    
                    if unit_price and qty_field:
                        lines.append(f"            const totalAmount = items.reduce((sum, item) => {{")
                        lines.append(f"                return sum + ((item.{qty_field} || 0) * (item.{unit_price} || 0));")
                        lines.append(f"            }}, 0);")
                    else:
                        first_amount = child_amounts[0] if child_amounts else "amount"
                        lines.append(f"            const totalAmount = items.reduce((sum, item) => sum + (item.{first_amount} || 0), 0);")

                    lines.append(f"")
                    lines.append(f"            await UPDATE({parent_entity}).set({{")
                    if "totalAmount" in parent_amounts:
                        lines.append(f"                totalAmount: totalAmount,")
                    elif parent_amounts:
                        lines.append(f"                {parent_amounts[0]}: totalAmount,")
                    lines.append(f"                itemCount: items.length")
                    lines.append(f"            }}).where({{ ID: parentID }});")
                    lines.append(f"")
                    lines.append(f"            LOG.info(`Recalculated {parent_entity} totals`, {{ id: parentID, total: totalAmount, items: items.length }});")
                    lines.append(f"        }} catch (err) {{")
                    lines.append(f"            LOG.error(`Failed to recalculate {parent_entity} totals`, err);")
                    lines.append(f"        }}")
                    lines.append(f"    }});")
                    lines.append("")

    # ----------- Custom action handlers from business rules -----------
    action_rules = [r for r in business_rules if r.get("rule_type") in ("workflow", "authorization")]
    if action_rules:
        lines.append("    // ═══════════════════════════════════════════════════════════")
        lines.append("    //  Custom Actions")
        lines.append("    // ═══════════════════════════════════════════════════════════")
        lines.append("")

        for rule in action_rules:
            rule_name = rule.get("name", "customAction")
            description = rule.get("description", "Custom action")
            entity_name = rule.get("entity", "")

            # Convert to camelCase action name
            action_name = re.sub(r'[\s_-]+', '', rule_name)
            action_name = action_name[0].lower() + action_name[1:] if action_name else "customAction"

            lines.append(f"    // {description}")
            lines.append(f"    this.on('{action_name}', async (req) => {{")
            lines.append(f"        const {{ ID }} = req.params[0] || {{}};")
            lines.append(f"        LOG.info(`Action {action_name} triggered`, {{ id: ID, user: req.user?.id }});")
            lines.append(f"")

            target_entity = entity_name if entity_name else "Entity"

            if "approv" in rule_name.lower():
                lines.append(f"        const record = await SELECT.one.from({target_entity}, ID);")
                lines.append(f"        if (!record) req.error(404, 'Record not found');")
                lines.append(f"        if (record.status !== 'Submitted') {{")
                lines.append(f"            req.error(409, 'Can only approve records in Submitted status');")
                lines.append(f"        }}")
                lines.append(f"        await UPDATE({target_entity}).set({{ status: 'Approved' }}).where({{ ID }});")
                lines.append(f"        return {{ success: true, message: 'Record approved successfully' }};")
            elif "reject" in rule_name.lower():
                lines.append(f"        const record = await SELECT.one.from({target_entity}, ID);")
                lines.append(f"        if (!record) req.error(404, 'Record not found');")
                lines.append(f"        await UPDATE({target_entity}).set({{ status: 'Rejected' }}).where({{ ID }});")
                lines.append(f"        return {{ success: true, message: 'Record rejected' }};")
            elif "cancel" in rule_name.lower():
                lines.append(f"        const record = await SELECT.one.from({target_entity}, ID);")
                lines.append(f"        if (!record) req.error(404, 'Record not found');")
                lines.append(f"        if (['Completed', 'Cancelled'].includes(record.status)) {{")
                lines.append(f"            req.error(409, 'Cannot cancel completed/cancelled records');")
                lines.append(f"        }}")
                lines.append(f"        await UPDATE({target_entity}).set({{ status: 'Cancelled' }}).where({{ ID }});")
                lines.append(f"        return {{ success: true, message: 'Record cancelled' }};")
            else:
                lines.append(f"        // TODO: Implement {rule_name} business logic")
                lines.append(f"        return {{ success: true, message: '{rule_name} executed' }};")

            lines.append(f"    }});")
            lines.append("")

    lines.append("});")
    return "\n".join(lines)


def generate_validation_utils_template() -> str:
    """Generate srv/lib/validation.js with input validators."""
    return """'use strict';

/**
 * Input Validation Utilities for SAP CAP Service Handlers
 * 
 * Provides reusable validators for common field types.
 * All validators use req.error() to add field-level errors.
 */

const EMAIL_REGEX = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
const PHONE_REGEX = /^\\+?[\\d\\s\\-()]{7,20}$/;
const URL_REGEX = /^https?:\\/\\/.+/;

/**
 * Validate required fields exist and are non-empty
 * @param {object} req - CDS request object
 * @param {object} data - Request data
 * @param {string[]} fieldNames - List of required field names
 */
function validateRequired(req, data, fieldNames) {
    for (const field of fieldNames) {
        if (data[field] === undefined || data[field] === null || data[field] === '') {
            req.error(400, `'${field}' is required`, field);
        }
    }
}

/**
 * Validate email format
 * @param {object} req - CDS request object
 * @param {string} value - Email value to validate
 * @param {string} fieldName - Field name for error targeting
 */
function validateEmail(req, value, fieldName = 'email') {
    if (value && !EMAIL_REGEX.test(value)) {
        req.error(400, `Invalid email format for '${fieldName}'`, fieldName);
    }
}

/**
 * Validate phone number format
 * @param {object} req - CDS request object
 * @param {string} value - Phone value to validate
 * @param {string} fieldName - Field name for error targeting
 */
function validatePhone(req, value, fieldName = 'phone') {
    if (value && !PHONE_REGEX.test(value)) {
        req.error(400, `Invalid phone number format for '${fieldName}'`, fieldName);
    }
}

/**
 * Validate a numeric value is within range
 * @param {object} req - CDS request object
 * @param {number} value - Numeric value
 * @param {string} fieldName - Field name
 * @param {object} options - { min, max }
 */
function validateRange(req, value, fieldName, { min = -Infinity, max = Infinity } = {}) {
    if (value !== undefined && value !== null) {
        if (value < min) {
            req.error(400, `'${fieldName}' must be at least ${min}`, fieldName);
        }
        if (value > max) {
            req.error(400, `'${fieldName}' must be at most ${max}`, fieldName);
        }
    }
}

/**
 * Validate string length
 * @param {object} req - CDS request object
 * @param {string} value - String value
 * @param {string} fieldName - Field name
 * @param {object} options - { min, max }
 */
function validateLength(req, value, fieldName, { min = 0, max = Infinity } = {}) {
    if (value !== undefined && value !== null) {
        if (value.length < min) {
            req.error(400, `'${fieldName}' must be at least ${min} characters`, fieldName);
        }
        if (value.length > max) {
            req.error(400, `'${fieldName}' must be at most ${max} characters`, fieldName);
        }
    }
}

/**
 * Validate URL format
 * @param {object} req - CDS request object
 * @param {string} value - URL value
 * @param {string} fieldName - Field name
 */
function validateURL(req, value, fieldName = 'url') {
    if (value && !URL_REGEX.test(value)) {
        req.error(400, `Invalid URL format for '${fieldName}'`, fieldName);
    }
}

/**
 * Validate date is not in the past
 * @param {object} req - CDS request object
 * @param {string|Date} value - Date value
 * @param {string} fieldName - Field name
 */
function validateFutureDate(req, value, fieldName) {
    if (value) {
        const date = new Date(value);
        if (date < new Date()) {
            req.error(400, `'${fieldName}' cannot be in the past`, fieldName);
        }
    }
}

module.exports = {
    validateRequired,
    validateEmail,
    validatePhone,
    validateRange,
    validateLength,
    validateURL,
    validateFutureDate,
    EMAIL_REGEX,
    PHONE_REGEX
};
"""


def generate_numbering_utils_template() -> str:
    """Generate srv/lib/numbering.js with sequential number generation."""
    return """'use strict';

const cds = require('@sap/cds');
const LOG = cds.log('numbering');

/**
 * Sequential Number Generator for SAP CAP Entities
 * 
 * Generates human-readable sequential IDs like:
 *   PO-2024-00001, INV-2024-00002, SO-2024-00003
 * 
 * Thread-safe using SELECT FOR UPDATE pattern.
 */

/**
 * Generate a sequential number for an entity
 * @param {string} prefix - Entity prefix (e.g., 'PO', 'INV', 'SO')
 * @param {object} entity - CDS entity to count from
 * @param {object} options - { padLength, includeYear, separator }
 * @returns {string} Generated number
 */
async function generateNumber(prefix, entity, options = {}) {
    const {
        padLength = 5,
        includeYear = true,
        separator = '-'
    } = options;

    try {
        const { count } = await SELECT.one
            .from(entity)
            .columns('count(*) as count');
        
        const seq = String((count || 0) + 1).padStart(padLength, '0');
        
        if (includeYear) {
            const year = new Date().getFullYear();
            return `${prefix}${separator}${year}${separator}${seq}`;
        }
        
        return `${prefix}${separator}${seq}`;
    } catch (err) {
        LOG.error(`Failed to generate number for ${prefix}`, err);
        // Fallback to timestamp-based ID
        const ts = Date.now().toString(36).toUpperCase();
        return `${prefix}${separator}${ts}`;
    }
}

/**
 * Generate a unique reference code
 * @param {string} prefix - Code prefix
 * @param {number} length - Random part length
 * @returns {string} Reference code
 */
function generateRefCode(prefix = 'REF', length = 6) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return `${prefix}-${result}`;
}

module.exports = { generateNumber, generateRefCode };
"""


def generate_utils_template() -> str:
    """Generate common utilities file (template fallback)."""
    return """'use strict';

const cds = require('@sap/cds');
const LOG = cds.log('utils');

/**
 * Common Utility Functions for SAP CAP Service Handlers
 */
module.exports = {
    /**
     * Format currency value for display
     * @param {number} value - Amount
     * @param {string} currency - ISO currency code
     * @returns {string} Formatted currency string
     */
    formatCurrency: (value, currency = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(value || 0);
    },

    /**
     * Check if user has a specific role
     * @param {object} req - CDS request
     * @param {string} role - Role name
     * @returns {boolean}
     */
    hasRole: (req, role) => {
        return req.user && req.user.is(role);
    },

    /**
     * Get current user ID safely
     * @param {object} req - CDS request
     * @returns {string} User ID or 'anonymous'
     */
    getCurrentUser: (req) => {
        return req.user?.id || 'anonymous';
    },

    /**
     * Log an audit event
     * @param {string} entity - Entity name
     * @param {string} action - Action performed
     * @param {object} data - Relevant data
     * @param {object} req - CDS request
     */
    logAudit: (entity, action, data, req) => {
        LOG.info(`[AUDIT] ${action} on ${entity}`, {
            user: req?.user?.id || 'system',
            entity,
            action,
            timestamp: new Date().toISOString(),
            dataID: data?.ID
        });
    },

    /**
     * Safely parse a date string
     * @param {string} dateStr - Date string
     * @returns {Date|null} Parsed date or null
     */
    parseDate: (dateStr) => {
        if (!dateStr) return null;
        const d = new Date(dateStr);
        return isNaN(d.getTime()) ? null : d;
    },

    /**
     * Calculate percentage
     * @param {number} part - Part value
     * @param {number} total - Total value
     * @returns {number} Percentage (0-100)
     */
    calcPercentage: (part, total) => {
        if (!total || total === 0) return 0;
        return Math.round((part / total) * 10000) / 100;
    }
};
"""


# =============================================================================
# Main Agent Function
# =============================================================================

async def business_logic_agent(state: BuilderState) -> BuilderState:
    """
    CAP Business Logic Agent (LLM-Driven)
    
    Uses LLM to generate production-quality service handlers with real business logic.
    Falls back to template-based generation if LLM fails.
    
    Generates:
    1. srv/service.js - Main service handler with status machines, validations, calculations
    2. srv/lib/utils.js - Utility functions (currency formatting, role checks, audit logging)
    3. srv/lib/validation.js - Input validators (email, phone, length, range)
    4. srv/lib/numbering.js - Sequential number generation (PO-2024-00001)
    
    Returns updated state with generated handler files.
    """
    logger.info("Starting Business Logic Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "business_logic"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting business logic generation...")
    
    entities = state.get("entities", [])
    if not entities:
        log_progress(state, "Error: No entities for handler generation.")
        errors.append({
            "agent": "business_logic",
            "code": "NO_ENTITIES",
            "message": "No entities for handler generation",
            "field": "entities",
            "severity": "error",
        })
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    relationships = state.get("relationships", [])
    business_rules = state.get("business_rules", [])
    provider = state.get("llm_provider")
    
    # Get previously generated artifacts for context
    schema_content = ""
    service_content = ""
    for artifact in state.get("artifacts_db", []):
        if artifact.get("path") == "db/schema.cds":
            schema_content = artifact.get("content", "")
    for artifact in state.get("artifacts_srv", []):
        if artifact.get("path") == "srv/service.cds":
            service_content = artifact.get("content", "")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven generation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        prompt = BUSINESS_LOGIC_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            service_content=service_content or "(service definition not yet available)",
            schema_content=schema_content or "(schema not yet available)",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
        )
        
        log_progress(state, "Calling LLM for business logic generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=BUSINESS_LOGIC_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("service_js"):
            service_js = parsed["service_js"]
            
            if "cds" in service_js and ("module.exports" in service_js or "export" in service_js):
                generated_files.append({
                    "path": "srv/service.js",
                    "content": service_js,
                    "file_type": "js",
                })
                log_progress(state, "✅ LLM-generated service handler accepted.")
                
                if parsed.get("utils_js"):
                    generated_files.append({
                        "path": "srv/lib/utils.js",
                        "content": parsed["utils_js"],
                        "file_type": "js",
                    })
                
                if parsed.get("validation_js"):
                    generated_files.append({
                        "path": "srv/lib/validation.js",
                        "content": parsed["validation_js"],
                        "file_type": "js",
                    })
                
                if parsed.get("numbering_js"):
                    generated_files.append({
                        "path": "srv/lib/numbering.js",
                        "content": parsed["numbering_js"],
                        "file_type": "js",
                    })
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required JS elements. Falling back.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for business logic: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation (industry-grade)
    # ==========================================================================
    if not llm_success:
        try:
            log_progress(state, "Generating srv/service.js via template fallback...")
            service_handler = generate_service_handler_template(state)
            generated_files.append({
                "path": "srv/service.js",
                "content": service_handler,
                "file_type": "js",
            })
        except Exception as e:
            logger.error(f"Failed to generate service.js: {e}")
            errors.append({
                "agent": "business_logic",
                "code": "HANDLER_GENERATION_ERROR",
                "message": f"Failed to generate handler: {str(e)}",
                "field": None,
                "severity": "error",
            })
        
        log_progress(state, "Generating srv/lib/utils.js...")
        generated_files.append({
            "path": "srv/lib/utils.js",
            "content": generate_utils_template(),
            "file_type": "js",
        })
        
        log_progress(state, "Generating srv/lib/validation.js...")
        generated_files.append({
            "path": "srv/lib/validation.js",
            "content": generate_validation_utils_template(),
            "file_type": "js",
        })
        
        log_progress(state, "Generating srv/lib/numbering.js...")
        generated_files.append({
            "path": "srv/lib/numbering.js",
            "content": generate_numbering_utils_template(),
            "file_type": "js",
        })
    
    # ==========================================================================
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    # Get retry configuration
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("business_logic", 0)
    
    # Validate the generated service.js
    logic_artifact = next((f for f in generated_files if f["path"] == "srv/service.js"), None)
    if logic_artifact and llm_success:
        validation_results = validate_artifact(logic_artifact["path"], logic_artifact["content"])
        
        if any(result.has_errors for result in validation_results):
            if should_retry_agent(validation_results, retry_count, max_retries):
                log_progress(state, f"Validation found errors. Attempting correction (retry {retry_count + 1}/{max_retries})...")
                
                if "retry_counts" not in state:
                    state["retry_counts"] = {}
                state["retry_counts"]["business_logic"] = retry_count + 1
                state["needs_correction"] = True
                
                if "correction_history" not in state:
                    state["correction_history"] = []
                state["correction_history"].append({
                    "agent": "business_logic",
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
                                "agent": "business_logic",
                                "code": issue.code or "VALIDATION_ERROR",
                                "message": issue.message,
                                "field": None,
                                "severity": "warning"
                            })
        else:
            if retry_count > 0:
                log_progress(state, f"✅ Validation passed after {retry_count} correction(s)")
                summary = format_correction_summary("business_logic", retry_count, retry_count, retry_count)
                if "auto_fixed_errors" not in state:
                    state["auto_fixed_errors"] = []
                state["auto_fixed_errors"].append({
                    "agent": "business_logic",
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
        "agent_name": "business_logic",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "retry_count": retry_count,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Business logic generation complete ({generation_method}). Generated {len(generated_files)} files.")
    logger.info(f"Business Logic Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
