"""
Agent 5: SAP Fiori UI Agent (LLM-Driven)

Generates Fiori Elements applications including manifest.json, i18n files,
Component.js, and related configuration for List Report and Object Page apps.

FULLY LLM-DRIVEN with inter-agent context.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.llm_utils import (
    generate_with_retry,
    get_schema_context,
    get_service_context,
    store_generated_content,
)
from backend.agents.knowledge_loader import get_fiori_knowledge
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    LayoutMode,
    ValidationError,
)
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


FIORI_SYSTEM_PROMPT = """You are a senior SAP Fiori Elements architect.
Generate production-ready, enterprise-grade Fiori Elements configuration files.

STRICT RULES:
1. Manifest Version: Use manifest schema 1.59.0+. Use 'sap.fe.templates' for V4.
2. Multi-Entity Routing:
   - Include a ListReport for the main entity.
   - Include ObjectPages for ALL entities (root and child).
   - Configure deep routing so users can navigate the composition tree.
3. Layout: ALWAYS use FlexibleColumnLayout (FCL).
4. Include sap.cloud configuration for deployment.
5. Include crossNavigation for Fiori Launchpad.
6. Include proper i18n bundle path.

OUTPUT FORMAT:
Return a JSON object:
{
    "manifest_json": "... stringified manifest.json ...",
    "component_js": "... Component.js ...",
    "i18n_properties": "... i18n.properties ...",
    "index_html": "... index.html ...",
    "flp_sandbox_html": "... flpSandbox.html ...",
    "ui5_yaml": "... ui5.yaml ...",
    "xs_app_json": "... xs-app.json ..."
}
Return ONLY valid JSON."""


FIORI_GENERATION_PROMPT = """Generate a complete SAP Fiori Elements application configuration.

Project: {project_name} ({app_id})
Main Entity: {main_entity}
Layout: {layout_mode}
Theme: {fiori_theme}

{service_context}

ENTITIES:
{entities_json}

RELATIONSHIPS:
{relationships_json}

REQUIREMENTS:
1. manifest.json — Full Fiori Elements manifest with:
   - sap.app with id, title, dataSources
   - sap.ui5 with routing, models, dependencies
   - ListReport for main entity
   - ObjectPage for ALL entities
   - FlexibleColumnLayout routing
   - sap.cloud configuration
   - crossNavigation for FLP
2. Component.js — UIComponent extending sap.fe.core.AppComponent
3. i18n.properties — Internationalization with all entity/field labels
4. index.html — Standalone launch page
5. flpSandbox.html — FLP sandbox for testing
6. ui5.yaml — UI5 tooling config
7. xs-app.json — Managed app router config

Respond with ONLY valid JSON."""


async def fiori_ui_agent(state: BuilderState) -> BuilderState:
    """SAP Fiori UI Agent (LLM-Driven)"""
    logger.info("Starting Fiori UI Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "fiori_ui"
    state["updated_at"] = now
    state["current_logs"] = []
    log_progress(state, "Starting Fiori UI phase...")

    entities = state.get("entities", [])
    if not entities:
        log_progress(state, "Error: No entities found.")
        return state

    project_name = state.get("project_name", "App")
    main_entity = state.get("fiori_main_entity", entities[0].get("name", ""))
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
    fiori_theme = state.get("fiori_theme", "sap_horizon")
    relationships = state.get("relationships", [])
    app_id = project_name.lower().replace(" ", "").replace("-", "").replace("_", "")

    service_context = get_service_context(state)
    knowledge = get_fiori_knowledge()

    prompt = FIORI_GENERATION_PROMPT.format(
        project_name=project_name,
        app_id=app_id,
        main_entity=main_entity,
        layout_mode=layout_mode,
        fiori_theme=fiori_theme,
        service_context=service_context or "(service CDS not available)",
        entities_json=json.dumps(entities, indent=2),
        relationships_json=json.dumps(relationships, indent=2),
    )

    # Inject knowledge into prompt
    prompt = f"{knowledge}\n\n{prompt}"

    # Self-Healing: Inject correction context if present
    correction_context = state.get("correction_context")
    if state.get("needs_correction") and state.get("correction_agent") == "fiori_ui" and correction_context:
        log_progress(state, "Applying self-healing correction context from validation agent...")
        correction_prompt = correction_context.get("correction_prompt", "")
        if correction_prompt:
            prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

    log_progress(state, "Calling LLM for Fiori UI generation...")

    result = await generate_with_retry(
        prompt=prompt,
        system_prompt=FIORI_SYSTEM_PROMPT,
        state=state,
        required_keys=["manifest_json"],
        max_retries=3,
        agent_name="fiori_ui",
    )

    app_prefix = f"app/{main_entity.lower()}/webapp"

    if result:
        file_map = {
            "manifest_json": (f"{app_prefix}/manifest.json", "json"),
            "component_js": (f"{app_prefix}/Component.js", "javascript"),
            "i18n_properties": (f"{app_prefix}/i18n/i18n.properties", "properties"),
            "index_html": (f"{app_prefix}/index.html", "html"),
            "flp_sandbox_html": (f"{app_prefix}/test/flpSandbox.html", "html"),
            "ui5_yaml": (f"app/{main_entity.lower()}/ui5.yaml", "yaml"),
            "xs_app_json": (f"app/{main_entity.lower()}/xs-app.json", "json"),
        }

        for key, (path, file_type) in file_map.items():
            content = result.get(key, "")
            if content:
                generated_files.append({
                    "path": path,
                    "content": content,
                    "file_type": file_type,
                })

        log_progress(state, f"✅ Generated {len(generated_files)} Fiori UI files.")
    else:
        log_progress(state, "⚠️ LLM generation failed. Generating minimal Fiori config.")
        generated_files.extend(_minimal_fiori(project_name, main_entity, app_prefix, fiori_theme))
        errors.append({
            "agent": "fiori_ui",
            "code": "LLM_FAILED",
            "message": "LLM Fiori generation failed. Minimal config generated.",
            "field": None,
            "severity": "warning",
        })

    store_generated_content(state, generated_files, {
        "manifest.json": "generated_manifest_json",
    })

    state["artifacts_app"] = generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    state["needs_correction"] = False

    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "fiori_ui",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Fiori UI complete. Generated {len(generated_files)} files.")
    return state


def _minimal_fiori(project_name, main_entity, app_prefix, theme):
    """Minimal Fiori config files."""
    manifest = json.dumps({
        "_version": "1.59.0",
        "sap.app": {
            "id": project_name.lower().replace(" ", ""),
            "type": "application",
            "title": project_name,
            "dataSources": {
                "mainService": {
                    "uri": f"/{project_name.lower().replace(' ', '-')}/",
                    "type": "OData",
                    "settings": {"odataVersion": "4.0"}
                }
            }
        },
        "sap.ui5": {
            "models": {
                "": {"dataSource": "mainService", "settings": {"synchronizationMode": "None"}}
            }
        }
    }, indent=2)

    component = f"""sap.ui.define(["sap/fe/core/AppComponent"], function(AppComponent) {{
  "use strict";
  return AppComponent.extend("{project_name.lower().replace(' ', '')}.Component", {{
    metadata: {{ manifest: "json" }}
  }});
}});"""

    return [
        {"path": f"{app_prefix}/manifest.json", "content": manifest, "file_type": "json"},
        {"path": f"{app_prefix}/Component.js", "content": component, "file_type": "javascript"},
    ]
