"""
Agent 7: Customization & Extension Agent

Generates Clean Core compliant extension points and hooks for SAP CAP applications.
Follows SAP's extensibility best practices for S/4HANA and BTP.
"""

import logging
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Extension Point Generation
# =============================================================================

def generate_extension_cds(state: BuilderState) -> str:
    """Generate extension points CDS file."""
    namespace = state.get("project_namespace", "com.company.app")
    entities = state.get("entities", [])
    
    lines = []
    lines.append("// Extension Points")
    lines.append("// Clean Core compliant extension hooks")
    lines.append("")
    lines.append(f"namespace {namespace}.extensions;")
    lines.append("")
    lines.append("using from '../db/schema';")
    lines.append("")
    
    # Generate extension aspect for each entity
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        
        lines.append(f"/**")
        lines.append(f" * Extension aspect for {entity_name}")
        lines.append(f" * Add custom fields by extending this aspect")
        lines.append(f" */")
        lines.append(f"aspect {entity_name}Extension {{")
        lines.append(f"    // Custom fields go here")
        lines.append(f"    // Example:")
        lines.append(f"    // customField : String(100);")
        lines.append(f"}}")
        lines.append("")
    
    # Generate extension service
    lines.append("// Extension Service")
    lines.append("// Expose extension-specific actions")
    lines.append("service ExtensionService @(path: '/extensions') {")
    lines.append("    // Custom actions for extensions")
    lines.append("}")
    
    return "\n".join(lines)


def generate_hooks_js(state: BuilderState) -> str:
    """Generate extensible hooks JavaScript module."""
    entities = state.get("entities", [])
    
    lines = []
    lines.append("/**")
    lines.append(" * Extension Hooks Module")
    lines.append(" * Provides Clean Core compliant extension points")
    lines.append(" */")
    lines.append("")
    lines.append("const cds = require('@sap/cds');")
    lines.append("")
    lines.append("/**")
    lines.append(" * Extension registry for custom handlers")
    lines.append(" */")
    lines.append("class ExtensionRegistry {")
    lines.append("    constructor() {")
    lines.append("        this.hooks = new Map();")
    lines.append("    }")
    lines.append("")
    lines.append("    /**")
    lines.append("     * Register an extension hook")
    lines.append("     * @param {string} hookName - Name of the hook point")
    lines.append("     * @param {Function} handler - Handler function")
    lines.append("     */")
    lines.append("    register(hookName, handler) {")
    lines.append("        if (!this.hooks.has(hookName)) {")
    lines.append("            this.hooks.set(hookName, []);")
    lines.append("        }")
    lines.append("        this.hooks.get(hookName).push(handler);")
    lines.append("    }")
    lines.append("")
    lines.append("    /**")
    lines.append("     * Execute all handlers for a hook")
    lines.append("     * @param {string} hookName - Name of the hook point")
    lines.append("     * @param {Object} context - Execution context")
    lines.append("     */")
    lines.append("    async execute(hookName, context) {")
    lines.append("        const handlers = this.hooks.get(hookName) || [];")
    lines.append("        for (const handler of handlers) {")
    lines.append("            await handler(context);")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    lines.append("// Global extension registry")
    lines.append("const extensionRegistry = new ExtensionRegistry();")
    lines.append("")
    
    # Generate hook points for each entity
    lines.append("// Available Hook Points:")
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        lines.append(f"// - before{entity_name}Create")
        lines.append(f"// - after{entity_name}Create")
        lines.append(f"// - before{entity_name}Update")
        lines.append(f"// - after{entity_name}Update")
        lines.append(f"// - before{entity_name}Delete")
        lines.append(f"// - after{entity_name}Delete")
        lines.append(f"// - validate{entity_name}")
    
    lines.append("")
    lines.append("module.exports = {")
    lines.append("    extensionRegistry,")
    lines.append("    register: (hookName, handler) => extensionRegistry.register(hookName, handler),")
    lines.append("    execute: (hookName, context) => extensionRegistry.execute(hookName, context)")
    lines.append("};")
    
    return "\n".join(lines)


def generate_extension_guide_md(state: BuilderState) -> str:
    """Generate extension developer guide."""
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    
    lines = []
    lines.append(f"# {project_name} Extension Guide")
    lines.append("")
    lines.append("This guide explains how to extend the application following SAP's Clean Core principles.")
    lines.append("")
    lines.append("## Clean Core Principles")
    lines.append("")
    lines.append("1. **No Modification of Core Code** - Use extension points only")
    lines.append("2. **Stable Interfaces** - Extensions communicate through defined APIs")
    lines.append("3. **Side-by-Side Extensions** - Extensions are deployed independently")
    lines.append("4. **Upgrade Stability** - Extensions survive core upgrades")
    lines.append("")
    lines.append("## Adding Custom Fields")
    lines.append("")
    lines.append("Create a new file `db/extensions.cds`:")
    lines.append("")
    lines.append("```cds")
    lines.append("using from './schema';")
    lines.append("")
    
    if entities:
        entity_name = entities[0].get("name", "Entity")
        lines.append(f"extend {entity_name} with {{")
        lines.append("    customField : String(100);")
        lines.append("    customDate  : Date;")
        lines.append("}")
    
    lines.append("```")
    lines.append("")
    lines.append("## Adding Custom Handlers")
    lines.append("")
    lines.append("Use the extension hooks in `srv/extensions/my-extension.js`:")
    lines.append("")
    lines.append("```javascript")
    lines.append("const { register } = require('../lib/hooks');")
    lines.append("")
    
    if entities:
        entity_name = entities[0].get("name", "Entity")
        lines.append(f"register('before{entity_name}Create', async (context) => {{")
        lines.append("    console.log('Extension: Before create hook');")
        lines.append("    // Add custom logic")
        lines.append("});")
    
    lines.append("```")
    lines.append("")
    lines.append("## Available Hook Points")
    lines.append("")
    lines.append("| Entity | Hook |")
    lines.append("|--------|------|")
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        lines.append(f"| {entity_name} | before{entity_name}Create, after{entity_name}Create |")
        lines.append(f"| {entity_name} | before{entity_name}Update, after{entity_name}Update |")
        lines.append(f"| {entity_name} | before{entity_name}Delete, validate{entity_name} |")
    
    return "\n".join(lines)


# =============================================================================
# Main Agent Function
# =============================================================================

async def extension_agent(state: BuilderState) -> BuilderState:
    """
    Customization & Extension Agent
    
    Generates:
    1. db/extensions.cds - Extension aspects
    2. srv/lib/hooks.js - Extension registry
    3. docs/EXTENSION_GUIDE.md - Developer guide
    
    Returns updated state with extension files.
    """
    logger.info("Starting Extension Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "extension"
    state["updated_at"] = now
    
    # Only generate if extensions are enabled
    if not state.get("fiori_extensions_enabled", True):
        logger.info("Extensions disabled, skipping agent")
        state["agent_history"] = state.get("agent_history", []) + [{
            "agent_name": "extension",
            "status": "skipped",
            "started_at": now,
            "completed_at": now,
            "duration_ms": 0,
            "error": "Extensions disabled",
        }]
        return state
    
    # ==========================================================================
    # Generate extension CDS
    # ==========================================================================
    try:
        extension_cds = generate_extension_cds(state)
        generated_files.append({
            "path": "db/extensions.cds",
            "content": extension_cds,
            "file_type": "cds",
        })
        logger.info("Generated db/extensions.cds")
    except Exception as e:
        logger.error(f"Failed to generate extensions.cds: {e}")
    
    # ==========================================================================
    # Generate hooks module
    # ==========================================================================
    try:
        hooks_js = generate_hooks_js(state)
        generated_files.append({
            "path": "srv/lib/hooks.js",
            "content": hooks_js,
            "file_type": "js",
        })
        logger.info("Generated srv/lib/hooks.js")
    except Exception as e:
        logger.error(f"Failed to generate hooks.js: {e}")
    
    # ==========================================================================
    # Generate extension guide
    # ==========================================================================
    try:
        guide = generate_extension_guide_md(state)
        generated_files.append({
            "path": "docs/EXTENSION_GUIDE.md",
            "content": guide,
            "file_type": "md",
        })
        logger.info("Generated docs/EXTENSION_GUIDE.md")
    except Exception as e:
        logger.error(f"Failed to generate extension guide: {e}")
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_docs"] = state.get("artifacts_docs", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "extension",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Extension Agent completed. Generated {len(generated_files)} files.")
    
    return state
