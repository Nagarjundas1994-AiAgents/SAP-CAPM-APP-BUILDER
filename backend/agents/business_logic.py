"""
Agent 4: CAP Business Logic Agent

Generates JavaScript/TypeScript event handlers for entity lifecycle events,
custom actions, validations, calculations, and side effects.

Uses LLM to generate production-quality business logic with fallback to templates.
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

BUSINESS_LOGIC_SYSTEM_PROMPT = """You are an expert SAP CAP (Cloud Application Programming Model) backend developer.
Your task is to generate production-ready JavaScript service handlers for SAP CAP services.

STRICT RULES:
1. Use `const cds = require('@sap/cds');` for imports in Node.js runtime
2. Use `module.exports = cds.service.impl(async function() { ... });` pattern
3. Register event handlers with this.before(), this.after(), this.on()
4. Destructure entities from this.entities
5. Use req.error(statusCode, message) for validation errors (NOT throw)
6. Use cds.ql (SELECT, INSERT, UPDATE, DELETE) for database operations
7. Use req.user for authentication checks
8. Use req.data for request payload
9. Handle both single and array results in after-READ handlers
10. Add proper JSDoc comments for all handlers
11. Implement REAL business logic, not just placeholder comments
12. For validations: check data integrity, format, and business constraints
13. For calculations: compute derived fields (totals, taxes, discounts)
14. For side effects: update related entities, send notifications
15. Use proper error codes: 400 for validation, 403 for authorization, 409 for conflicts

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "service_js": "... full content of srv/service.js ...",
  "utils_js": "... full content of srv/lib/utils.js ..."
}

Do NOT include markdown code fences in the JSON values. Return ONLY the JSON object."""


BUSINESS_LOGIC_PROMPT = """Generate srv/service.js and srv/lib/utils.js for this SAP CAP project.

Project Name: {project_name}
Project Description: {description}

Service Definition (srv/service.cds):
```
{service_content}
```

Schema (db/schema.cds):
```
{schema_content}
```

Entities:
{entities_json}

Relationships:
{relationships_json}

Business Rules to implement:
{business_rules_json}

Requirements for srv/service.js:
1. Import cds and destructure all entity references
2. For EACH entity, implement these handlers with REAL logic:
   - this.before('CREATE', Entity, ...) - validate required fields, generate IDs, set defaults
   - this.after('READ', Entity, ...) - compute virtual/calculated fields
   - this.before('UPDATE', Entity, ...) - validate changes, check permissions
   - this.before('DELETE', Entity, ...) - check for dependent records, prevent orphans
3. Implement handlers for business rules (validations, calculations, custom actions)
4. Add proper error handling with meaningful messages
5. Use cds.ql for database queries where needed
6. Add audit logging calls for important operations
7. The handlers should contain REAL working JavaScript code, not stub comments

Requirements for srv/lib/utils.js:
1. Helper functions relevant to this domain (ID generators, formatters, validators)
2. Export as a module with JSDoc documentation
3. Include domain-specific validation functions

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

def generate_service_handler_template(state: BuilderState) -> str:
    """Generate the main service handler file (template fallback)."""
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    business_rules = state.get("business_rules", [])
    cap_runtime = state.get("cap_runtime", CAPRuntime.NODEJS.value)
    
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_name = f"{service_name}Service"
    
    lines = []
    if cap_runtime == CAPRuntime.NODEJS.value:
        lines.append("const cds = require('@sap/cds');")
    else:
        lines.append("import cds from '@sap/cds';")
    
    lines.append("")
    lines.append(f"module.exports = cds.service.impl(async function() {{")
    lines.append("")
    lines.append("    const { ")
    entity_names = [e.get("name", "Entity") for e in entities]
    lines.append("        " + ", ".join(entity_names))
    lines.append("    } = this.entities;")
    lines.append("")
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        
        lines.append(f"    // =========== {entity_name} Handlers ===========")
        lines.append("")
        lines.append(f"    this.before('CREATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")
        
        required_fields = [f for f in fields if not f.get("nullable", True) and not f.get("key")]
        if required_fields:
            lines.append("")
            lines.append("        // Validate required fields")
            for field in required_fields:
                field_name = field.get("name", "")
                lines.append(f"        if (!data.{field_name}) {{")
                lines.append(f"            req.error(400, `{field_name} is required`);")
                lines.append(f"        }}")
        
        lines.append("    });")
        lines.append("")
        lines.append(f"    this.after('READ', {entity_name}, (data, req) => {{")
        lines.append("        const records = Array.isArray(data) ? data : [data];")
        lines.append("        records.forEach(record => {")
        lines.append("            // Post-processing after read")
        lines.append("        });")
        lines.append("    });")
        lines.append("")
        lines.append(f"    this.before('UPDATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")
        lines.append("        // Validate update data")
        lines.append("    });")
        lines.append("")
        lines.append(f"    this.before('DELETE', {entity_name}, async (req) => {{")
        lines.append("        // Check if deletion is allowed")
        lines.append("    });")
        lines.append("")
    
    for rule in business_rules:
        rule_name = rule.get("name", "customAction")
        rule_type = rule.get("rule_type", "")
        description = rule.get("description", "")
        
        if rule_type in ["validation", "calculation"]:
            lines.append(f"    // {description}")
            lines.append(f"    this.on('{rule_name}', async (req) => {{")
            lines.append("        return { success: true };")
            lines.append("    });")
            lines.append("")
    
    lines.append("});")
    return "\n".join(lines)


def generate_utils_template() -> str:
    """Generate common utilities file (template fallback)."""
    return """const cds = require('@sap/cds');

/**
 * Common utility functions for handlers
 */
module.exports = {
    generateOrderNumber: () => {
        const timestamp = Date.now().toString(36).toUpperCase();
        const random = Math.random().toString(36).substring(2, 6).toUpperCase();
        return `ORD-${timestamp}-${random}`;
    },

    formatCurrency: (value, currency = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(value);
    },

    isValidEmail: (email) => {
        const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
        return emailRegex.test(email);
    },

    hasRole: (req, role) => {
        return req.user && req.user.is(role);
    },

    logAudit: async (entity, action, data, user) => {
        console.log(`[AUDIT] ${action} on ${entity} by ${user}: ${JSON.stringify(data)}`);
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
    1. srv/service.js - Main service handler
    2. srv/lib/utils.js - Utility functions
    
    Returns updated state with generated handler files.
    """
    logger.info("Starting Business Logic Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
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
                log_progress(state, "LLM-generated service handler accepted.")
                
                if parsed.get("utils_js"):
                    generated_files.append({
                        "path": "srv/lib/utils.js",
                        "content": parsed["utils_js"],
                        "file_type": "js",
                    })
                    log_progress(state, "LLM-generated utils accepted.")
                
                llm_success = True
            else:
                log_progress(state, "LLM response missing required JS elements. Falling back.")
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for business logic: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
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
        
        log_progress(state, "Generating srv/lib/utils.js via template fallback...")
        generated_files.append({
            "path": "srv/lib/utils.js",
            "content": generate_utils_template(),
            "file_type": "js",
        })
    
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
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Business logic generation complete ({generation_method}).")
    logger.info(f"Business Logic Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
