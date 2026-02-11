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
Your task is to generate production-ready, enterprise-grade JavaScript service handlers for SAP CAP services.

STRICT RULES:
1. Architecture: Use `const cds = require('@sap/cds');` and `module.exports = cds.service.impl(async function() { ... });`.
2. Handlers: Use this.before(), this.after(), this.on(). Destructure entities from 'this.entities'.
3. Database: Use 'cds.ql' (SELECT, INSERT, UPDATE, DELETE) or 'cds.tx(req).run(...)'.
4. Validations:
   - Perform deep data checks (length, format, business constraints).
   - Use `req.error(400, 'Message', 'targetField')` for errors.
5. Calculations:
   - Compute totals, taxes, and status-dependent values in 'after' or 'before' handlers.
   - For calculated fields in schema, ensure values are populated during CREATE/UPDATE.
6. Actions:
   - Implement custom action/function logic in '.on' handlers.
   - Return proper types as defined in CDS.
7. Side Effects: Update related entities where appropriate (e.g. updating stock when order item is created).
8. Best Practices: Use 'srv/lib/utils.js' for common helper functions to keep the main handler clean.

OUTPUT FORMAT:
Return a JSON object:
{
  "service_js": "... srv/service.js content ...",
  "utils_js": "... srv/lib/utils.js content ..."
}
Return ONLY the JSON."""


BUSINESS_LOGIC_PROMPT = """Generate an enterprise-grade srv/service.js and srv/lib/utils.js.

Project: {project_name}
Description: {description}

Service Definition:
{service_content}

Schema & Business Rules:
{schema_content}
{business_rules_json}

Requirements for service.js:
1. Implement REAL validation for every entity based on field names and business rules.
2. For entities with a 'status' field: implement status transition logic (e.g. can't move from 'Closed' to 'New').
3. For collections: compute totals (e.g. Order.totalAmount = sum of OrderItem.amount).
4. For IDs: if not UUID, implement auto-numbering logic (SHP-001, INV-001).
5. Implement all Actions defined in service.cds with functional logic.
6. Use 'srv/lib/utils.js' for shared logic like currency conversion or ID formatting.

Requirements for utils.js:
1. Provide functions for generating human-readable IDs.
2. Provide validation helpers (email format, date range).
3. Export as a module using 'module.exports'.

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
    log_progress(state, f"Business logic generation complete ({generation_method}).")
    logger.info(f"Business Logic Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
