"""
Agent 7: Customization & Extension Agent (LLM-Driven)

Generates Clean Core compliant extension points and hooks for SAP CAP applications.

FULLY LLM-DRIVEN with inter-agent context.
"""

import json
import logging
from datetime import datetime

from backend.agents.llm_utils import (
    generate_with_retry,
    get_full_context,
)
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
)
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


EXTENSION_SYSTEM_PROMPT = """You are an SAP CAP extensibility architect.
Generate Clean Core compliant extension points and hooks.

RULES:
1. Follow SAP Clean Core principles — NO modification of core, ONLY extensions
2. Extension CDS using `extend` keyword for aspect overlays
3. Hook system with before/after lifecycle hooks per entity
4. Provide a developer guide in Markdown
5. Use proper module exports

OUTPUT FORMAT:
{
    "extension_cds": "... db/extensions.cds ...",
    "hooks_js": "... srv/lib/hooks.js ...",
    "extension_guide_md": "... docs/EXTENSION_GUIDE.md ..."
}
Return ONLY valid JSON."""


EXTENSION_PROMPT = """Generate extension points for this SAP CAP application.

Project: {project_name}

{context}

ENTITIES:
{entities_json}

BUSINESS RULES:
{business_rules_json}

Generate:
1. db/extensions.cds — CDS aspects for extending entities
2. srv/lib/hooks.js — Hook registration system with lifecycle hooks per entity
3. docs/EXTENSION_GUIDE.md — Developer guide for extending the app

Respond with ONLY valid JSON."""


async def extension_agent(state: BuilderState) -> BuilderState:
    """Extension Agent (LLM-Driven)"""
    logger.info("Starting Extension Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "extension"
    state["updated_at"] = now
    state["current_logs"] = []
    log_progress(state, "Starting extension phase...")

    entities = state.get("entities", [])
    project_name = state.get("project_name", "App")
    business_rules = state.get("business_rules", [])
    context = get_full_context(state)

    prompt = EXTENSION_PROMPT.format(
        project_name=project_name,
        context=context or "(no prior context available)",
        entities_json=json.dumps(entities, indent=2),
        business_rules_json=json.dumps(business_rules, indent=2),
    )

    log_progress(state, "Calling LLM for extension generation...")

    result = await generate_with_retry(
        prompt=prompt,
        system_prompt=EXTENSION_SYSTEM_PROMPT,
        state=state,
        required_keys=["hooks_js"],
        max_retries=3,
        agent_name="extension",
    )

    if result:
        file_map = {
            "extension_cds": ("db/extensions.cds", "cds"),
            "hooks_js": ("srv/lib/hooks.js", "javascript"),
            "extension_guide_md": ("docs/EXTENSION_GUIDE.md", "markdown"),
        }
        for key, (path, file_type) in file_map.items():
            content = result.get(key, "")
            if content:
                generated_files.append({"path": path, "content": content, "file_type": file_type})

        log_progress(state, f"✅ Generated {len(generated_files)} extension files.")
    else:
        log_progress(state, "⚠️ LLM failed. Generating minimal extension structure.")
        generated_files.append({
            "path": "srv/lib/hooks.js",
            "content": _minimal_hooks(entities),
            "file_type": "javascript",
        })
        errors.append({
            "agent": "extension",
            "code": "LLM_FAILED",
            "message": "LLM extension generation failed.",
            "field": None,
            "severity": "warning",
        })

    existing = state.get("artifacts_srv", [])
    state["artifacts_srv"] = existing + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    state["needs_correction"] = False

    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "extension",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Extension complete. Generated {len(generated_files)} files.")
    return state


def _minimal_hooks(entities):
    """Minimal hook system."""
    entity_names = [e.get("name", "") for e in entities]
    lines = [
        "'use strict';",
        "",
        "const hooks = {};",
        "",
    ]
    for name in entity_names:
        lines.append(f"hooks['{name}'] = {{ before: {{}}, after: {{}} }};")
    lines.append("")
    lines.append("module.exports = { hooks };")
    return "\n".join(lines)
