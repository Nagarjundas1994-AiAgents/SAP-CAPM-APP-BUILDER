"""
Agent 7: Customization & Extension Agent

Generates Clean Core compliant extension points and hooks for SAP CAP applications.
Follows SAP's extensibility best practices for S/4HANA and BTP.

Uses LLM to generate production-quality extension configurations with fallback to templates.
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
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

EXTENSION_SYSTEM_PROMPT = """You are an expert SAP CAP extensibility architect following Clean Core principles.
Your task is to generate production-ready extension points, hooks, and developer documentation.

STRICT RULES:
1. Use CDS aspects for extending entities: "extend entity X with { ... }"
2. Create a hook registry pattern using Node.js EventEmitter or simple callback registration
3. Document extension points clearly with JSDoc
4. Follow SAP Clean Core principles - no modification of core, only extensions
5. Provide lifecycle hooks: beforeCreate, afterCreate, beforeUpdate, afterUpdate, beforeDelete, afterDelete
6. Add custom event hooks for business-process-specific events
7. Generate comprehensive developer guide in Markdown
8. Use proper module exports pattern
9. Include extension validation to prevent breaking changes
10. Support both synchronous and asynchronous hooks

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "extensions_cds": "... full content of db/extensions.cds ...",
  "hooks_js": "... full content of srv/lib/hooks.js ...",
  "extension_guide_md": "... full content of docs/EXTENSION_GUIDE.md ..."
}

Do NOT include markdown code fences in the JSON values. Return ONLY the JSON object."""


EXTENSION_GENERATION_PROMPT = """Generate extension points and hooks for this SAP CAP project.

Project Name: {project_name}
Project Description: {description}

Schema:
```
{schema_content}
```

Service:
```
{service_content}
```

Entities:
{entities_json}

Business Rules:
{business_rules_json}

Requirements:
1. db/extensions.cds:
   - Define CDS aspects to extend each entity (e.g., custom fields, computed fields)
   - Use "extend" keyword properly
   - Add documentation comments

2. srv/lib/hooks.js:
   - EventEmitter-based hook registry
   - Register/unregister hook functions
   - Lifecycle hooks per entity: before/after CRUD
   - Business event hooks (e.g., onOrderConfirmed, onStatusChanged)
   - Error handling in hook execution
   - Async hook support

3. docs/EXTENSION_GUIDE.md:
   - Overview of extension architecture
   - How to add custom fields via CDS aspects
   - How to register hooks with code examples
   - List of available hook points per entity
   - Best practices for extensions
   - Troubleshooting section

Respond with ONLY valid JSON."""


# =============================================================================
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


def _parse_llm_response(response_text: str) -> dict | None:
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

def generate_extension_cds(state: BuilderState) -> str:
    entities = state.get("entities", [])
    namespace = state.get("project_namespace", "com.company.app")
    lines = [
        f"// Extension Aspects for {namespace}",
        "// Add custom fields and computed properties via CDS aspects",
        "",
        f"using {{ {namespace} as db }} from './schema';",
        "",
    ]
    for entity in entities:
        name = entity.get("name", "Entity")
        lines.append(f"// Extension aspect for {name}")
        lines.append(f"extend entity db.{name} with {{")
        lines.append(f"    // Add custom extension fields here")
        lines.append(f"    // customField : String(100);")
        lines.append(f"}};")
        lines.append("")
    return "\n".join(lines)


def generate_hooks_js(state: BuilderState) -> str:
    entities = state.get("entities", [])
    entity_names = [e.get("name", "Entity") for e in entities]
    
    hooks_code = """'use strict';
const EventEmitter = require('events');

/**
 * Hook Registry for Extension Points
 * Allows registering custom handlers for entity lifecycle events.
 */
class HookRegistry extends EventEmitter {
    constructor() {
        super();
        this.setMaxListeners(50);
    }

    /**
     * Register a hook for an entity lifecycle event
     * @param {string} entity - Entity name
     * @param {string} event - Event name (beforeCreate, afterCreate, etc.)
     * @param {Function} handler - Handler function
     */
    registerHook(entity, event, handler) {
        const eventName = `${entity}.${event}`;
        this.on(eventName, handler);
        console.log(`[Hooks] Registered hook: ${eventName}`);
    }

    /**
     * Execute all hooks for an event
     * @param {string} entity - Entity name
     * @param {string} event - Event type
     * @param {object} context - Event context (req, data, etc.)
     */
    async executeHooks(entity, event, context) {
        const eventName = `${entity}.${event}`;
        const listeners = this.listeners(eventName);
        for (const listener of listeners) {
            try {
                await listener(context);
            } catch (err) {
                console.error(`[Hooks] Error in hook ${eventName}:`, err.message);
            }
        }
    }
}

const registry = new HookRegistry();
module.exports = { registry, HookRegistry };
"""
    return hooks_code


def generate_extension_guide_md(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    entities = state.get("entities", [])
    
    lines = [
        f"# Extension Guide - {project_name}",
        "",
        "## Overview",
        "This project follows SAP Clean Core principles for extensibility.",
        "",
        "## Adding Custom Fields",
        "Edit `db/extensions.cds` to add custom fields via CDS aspects:",
        "```cds",
        "extend entity db.YourEntity with {",
        "    customField : String(100);",
        "};",
        "```",
        "",
        "## Registering Hooks",
        "```javascript",
        "const { registry } = require('./srv/lib/hooks');",
        "registry.registerHook('EntityName', 'beforeCreate', async (ctx) => {",
        "    // Your custom logic",
        "});",
        "```",
        "",
        "## Available Hook Points",
    ]
    for entity in entities:
        name = entity.get("name", "Entity")
        lines.append(f"### {name}")
        lines.append(f"- `{name}.beforeCreate`")
        lines.append(f"- `{name}.afterCreate`")
        lines.append(f"- `{name}.beforeUpdate`")
        lines.append(f"- `{name}.afterUpdate`")
        lines.append(f"- `{name}.beforeDelete`")
        lines.append(f"- `{name}.afterDelete`")
        lines.append("")
    
    return "\n".join(lines)


# =============================================================================
# Main Agent Function
# =============================================================================

async def extension_agent(state: BuilderState) -> BuilderState:
    """
    Customization & Extension Agent (LLM-Driven)
    
    Uses LLM to generate production-quality extension points and hooks.
    Falls back to template-based generation if LLM fails.
    """
    logger.info("Starting Extension Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "extension"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting extension point generation...")
    
    entities = state.get("entities", [])
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    business_rules = state.get("business_rules", [])
    provider = state.get("llm_provider")
    
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
        
        prompt = EXTENSION_GENERATION_PROMPT.format(
            project_name=project_name,
            description=description or "No description",
            schema_content=schema_content or "(not available)",
            service_content=service_content or "(not available)",
            entities_json=json.dumps(entities, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
        )
        
        log_progress(state, "Calling LLM for extension point generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=EXTENSION_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and (parsed.get("extensions_cds") or parsed.get("hooks_js")):
            if parsed.get("extensions_cds"):
                generated_files.append({"path": "db/extensions.cds", "content": parsed["extensions_cds"], "file_type": "cds"})
            if parsed.get("hooks_js"):
                generated_files.append({"path": "srv/lib/hooks.js", "content": parsed["hooks_js"], "file_type": "js"})
            if parsed.get("extension_guide_md"):
                generated_files.append({"path": "docs/EXTENSION_GUIDE.md", "content": parsed["extension_guide_md"], "file_type": "md"})
            
            log_progress(state, "LLM-generated extension points accepted.")
            llm_success = True
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for extensions: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        log_progress(state, "Generating extension files via template fallback...")
        try:
            generated_files.append({"path": "db/extensions.cds", "content": generate_extension_cds(state), "file_type": "cds"})
            generated_files.append({"path": "srv/lib/hooks.js", "content": generate_hooks_js(state), "file_type": "js"})
            generated_files.append({"path": "docs/EXTENSION_GUIDE.md", "content": generate_extension_guide_md(state), "file_type": "md"})
        except Exception as e:
            logger.error(f"Template fallback failed for extensions: {e}")
            errors.append({"agent": "extension", "code": "EXTENSION_ERROR", "message": f"Extension generation failed: {str(e)}", "field": None, "severity": "error"})
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_ext"] = state.get("artifacts_ext", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "extension",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Extension generation complete ({generation_method}).")
    logger.info(f"Extension Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
