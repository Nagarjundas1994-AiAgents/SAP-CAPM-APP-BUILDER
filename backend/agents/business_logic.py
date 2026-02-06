"""
Agent 4: CAP Business Logic Agent

Generates JavaScript/TypeScript event handlers for entity lifecycle events,
custom actions, validations, calculations, and side effects.
"""

import logging
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    BusinessRule,
    GeneratedFile,
    ValidationError,
    CAPRuntime,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Handler Generation
# =============================================================================

def generate_service_handler(state: BuilderState) -> str:
    """Generate the main service handler file."""
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    business_rules = state.get("business_rules", [])
    cap_runtime = state.get("cap_runtime", CAPRuntime.NODEJS.value)
    
    # Service name
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_name = f"{service_name}Service"
    
    lines = []
    
    # Imports
    if cap_runtime == CAPRuntime.NODEJS.value:
        lines.append("const cds = require('@sap/cds');")
    else:
        lines.append("import cds from '@sap/cds';")
    
    lines.append("")
    lines.append(f"module.exports = cds.service.impl(async function() {{")
    lines.append("")
    
    # Reference to this service
    lines.append("    const { ")
    entity_names = [e.get("name", "Entity") for e in entities]
    lines.append("        " + ", ".join(entity_names))
    lines.append("    } = this.entities;")
    lines.append("")
    
    # Generate handlers for each entity
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        fields = entity.get("fields", [])
        
        # Before CREATE handler
        lines.append(f"    // =========== {entity_name} Handlers ===========")
        lines.append("")
        lines.append(f"    this.before('CREATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")
        
        # Add validation for required fields
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
        
        # After READ handler (for calculations)
        lines.append(f"    this.after('READ', {entity_name}, (data, req) => {{")
        lines.append("        // Post-processing after read")
        lines.append("        if (Array.isArray(data)) {")
        lines.append("            data.forEach(record => {")
        lines.append("                // Add computed fields or transformations")
        lines.append("            });")
        lines.append("        }")
        lines.append("    });")
        lines.append("")
        
        # Before UPDATE handler
        lines.append(f"    this.before('UPDATE', {entity_name}, async (req) => {{")
        lines.append(f"        const {{ data }} = req;")
        lines.append("        // Validate update data")
        lines.append("    });")
        lines.append("")
        
        # Before DELETE handler
        lines.append(f"    this.before('DELETE', {entity_name}, async (req) => {{")
        lines.append("        // Check if deletion is allowed")
        lines.append("        // req.error(403, 'Deletion not allowed');")
        lines.append("    });")
        lines.append("")
    
    # Generate handlers for business rules
    for rule in business_rules:
        rule_name = rule.get("name", "customAction")
        rule_type = rule.get("rule_type", "")
        entity = rule.get("entity", "")
        description = rule.get("description", "")
        
        if rule_type in ["validation", "calculation"]:
            lines.append(f"    // {description}")
            lines.append(f"    this.on('{rule_name}', async (req) => {{")
            lines.append("        // Implement custom action logic")
            lines.append("        return { success: true };")
            lines.append("    });")
            lines.append("")
    
    lines.append("});")
    
    return "\n".join(lines)


def generate_entity_handler(entity: EntityDefinition, namespace: str) -> tuple[str, str]:
    """Generate individual entity handler file."""
    entity_name = entity.get("name", "Entity")
    fields = entity.get("fields", [])
    
    filename = f"srv/handlers/{entity_name.lower()}-handler.js"
    
    lines = []
    lines.append("const cds = require('@sap/cds');")
    lines.append("")
    lines.append(f"/**")
    lines.append(f" * Handler for {entity_name} entity")
    lines.append(f" */")
    lines.append(f"module.exports = class {entity_name}Handler {{")
    lines.append("")
    
    # Validation method
    lines.append(f"    static validate(data) {{")
    lines.append("        const errors = [];")
    
    required_fields = [f for f in fields if not f.get("nullable", True) and not f.get("key")]
    for field in required_fields:
        field_name = field.get("name", "")
        lines.append(f"        if (!data.{field_name}) {{")
        lines.append(f"            errors.push('{field_name} is required');")
        lines.append(f"        }}")
    
    lines.append("        return errors;")
    lines.append("    }")
    lines.append("")
    
    # Calculation methods for numeric fields
    numeric_fields = [f for f in fields if f.get("type") in ["Integer", "Decimal", "Double"]]
    if numeric_fields:
        lines.append(f"    static calculateTotals(data) {{")
        lines.append("        // Implement calculations")
        lines.append("        return data;")
        lines.append("    }")
        lines.append("")
    
    lines.append("};")
    
    return filename, "\n".join(lines)


def generate_utils_file() -> str:
    """Generate common utilities file."""
    return """const cds = require('@sap/cds');

/**
 * Common utility functions for handlers
 */
module.exports = {
    /**
     * Generate a unique order number
     */
    generateOrderNumber: () => {
        const timestamp = Date.now().toString(36).toUpperCase();
        const random = Math.random().toString(36).substring(2, 6).toUpperCase();
        return `ORD-${timestamp}-${random}`;
    },

    /**
     * Format currency value
     */
    formatCurrency: (value, currency = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(value);
    },

    /**
     * Validate email format
     */
    isValidEmail: (email) => {
        const emailRegex = /^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/;
        return emailRegex.test(email);
    },

    /**
     * Check if user has required role
     */
    hasRole: (req, role) => {
        return req.user && req.user.is(role);
    },

    /**
     * Log audit trail
     */
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
    CAP Business Logic Agent
    
    Generates:
    1. srv/service.js - Main service handler
    2. srv/handlers/*.js - Entity-specific handlers
    3. srv/lib/utils.js - Utility functions
    
    Returns updated state with generated handler files.
    """
    logger.info("Starting Business Logic Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "business_logic"
    state["updated_at"] = now
    
    # Check prerequisites
    entities = state.get("entities", [])
    if not entities:
        errors.append({
            "agent": "business_logic",
            "code": "NO_ENTITIES",
            "message": "No entities for handler generation",
            "field": "entities",
            "severity": "error",
        })
        state["validation_errors"] = state.get("validation_errors", []) + errors
        return state
    
    # ==========================================================================
    # Generate main service handler
    # ==========================================================================
    try:
        service_handler = generate_service_handler(state)
        generated_files.append({
            "path": "srv/service.js",
            "content": service_handler,
            "file_type": "js",
        })
        logger.info("Generated srv/service.js")
    except Exception as e:
        logger.error(f"Failed to generate service.js: {e}")
        errors.append({
            "agent": "business_logic",
            "code": "HANDLER_GENERATION_ERROR",
            "message": f"Failed to generate handler: {str(e)}",
            "field": None,
            "severity": "error",
        })
    
    # ==========================================================================
    # Generate entity-specific handlers
    # ==========================================================================
    namespace = state.get("project_namespace", "com.company.app")
    
    for entity in entities:
        try:
            filepath, content = generate_entity_handler(entity, namespace)
            generated_files.append({
                "path": filepath,
                "content": content,
                "file_type": "js",
            })
            logger.info(f"Generated {filepath}")
        except Exception as e:
            logger.warning(f"Failed to generate handler for {entity.get('name')}: {e}")
    
    # ==========================================================================
    # Generate utilities
    # ==========================================================================
    utils_content = generate_utils_file()
    generated_files.append({
        "path": "srv/lib/utils.js",
        "content": utils_content,
        "file_type": "js",
    })
    logger.info("Generated srv/lib/utils.js")
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_srv"] = state.get("artifacts_srv", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "business_logic",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Business Logic Agent completed. Generated {len(generated_files)} files.")
    
    return state
