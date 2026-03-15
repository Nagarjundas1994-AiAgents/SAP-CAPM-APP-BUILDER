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
    get_architecture_context,
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
from backend.agents.resilience import with_timeout

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
7. MULTI-APP SUPPORT (when requested):
   - Generate a SEPARATE manifest.json, Component.js, i18n, and routing for each app.
   - Each app lives in its own directory: app/{entity_lowercase}/webapp/
   - Each app has its own sap.app.id and crossNavigation target.
   - App types:
     - List Report + Object Page (default CRUD app)
     - Worklist (task-based entity with status workflow)
     - Overview Page (dashboard with cards/KPIs across entities)

OUTPUT FORMAT:
Return a JSON object with an 'apps' array. EACH app entry has:
{
    "apps": [
        {
            "entity": "MainEntity",
            "app_type": "list_report",
            "manifest_json": "... stringified manifest.json ...",
            "component_js": "... Component.js ...",
            "i18n_properties": "... i18n.properties ..."
        }
    ],
    "index_html": "... shared index.html ...",
    "flp_sandbox_html": "... shared flpSandbox.html ..."
}
For SINGLE app (starter/standard), return exactly 1 entry in the apps array.
For MULTIPLE apps (enterprise/full_stack), return one entry per root entity.
Return ONLY valid JSON."""


FIORI_GENERATION_PROMPT = """Generate SAP Fiori Elements application configuration(s).

Project: {project_name} ({app_id})
Main Entity: {main_entity}
Layout: {layout_mode}
Theme: {fiori_theme}
Complexity: {complexity}

{architecture_context}
{service_context}

ENTITIES:
{entities_json}

RELATIONSHIPS:
{relationships_json}

{multi_app_instructions}

For EACH app, generate:
1. manifest.json — Full Fiori Elements manifest with sap.app, sap.ui5, routing, sap.cloud
2. Component.js — UIComponent extending sap.fe.core.AppComponent
3. i18n.properties — Internationalization with entity/field labels

Also generate shared files:
4. index.html — Launch page linking to first/main app
5. flpSandbox.html — FLP sandbox with tiles for ALL generated apps

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=240)
async def fiori_ui_agent(state: BuilderState) -> dict[str, Any]:
    """SAP Fiori UI Agent (LLM-Driven) — supports multi-app generation."""
    agent_name = "fiori_ui"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Fiori UI Agent (LLM-Driven)")
    log_progress(state, "Starting Fiori UI phase...")
    
    # Check retry count
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exhausted")
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        return {
            "agent_failed": True,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": f"Max retries ({max_retries}) exhausted",
                "logs": None,
            }],
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }
    
    try:
        errors: list[ValidationError] = []
        generated_files: list[GeneratedFile] = []

        entities = state.get("entities", [])
        if not entities:
            log_progress(state, "Error: No entities found.")
            raise ValueError("No entities found for Fiori UI generation")

        project_name = state.get("project_name", "App")
        main_entity = state.get("fiori_main_entity", entities[0].get("name", ""))
        layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
        fiori_theme = state.get("fiori_theme", "sap_horizon")
        relationships = state.get("relationships", [])
        complexity = state.get("complexity_level", "standard")
        app_id = project_name.lower().replace(" ", "").replace("-", "").replace("_", "")

        service_context = get_service_context(state)
        architecture_context = get_architecture_context(state)
        knowledge = get_fiori_knowledge()

        # Determine root entities (not composition children) for multi-app
        child_entities = set()
        for rel in relationships:
            if rel.get("type") == "composition":
                child_entities.add(rel.get("target_entity", ""))

        root_entities = [e for e in entities if e.get("name", "") not in child_entities]

        # Multi-app instructions based on complexity
        if complexity in ("enterprise", "full_stack") and len(root_entities) > 1:
            multi_app_instructions = f"""MULTI-APP MODE: Generate {len(root_entities)} separate Fiori apps.
        Root entities for apps: {', '.join(e.get('name', '') for e in root_entities)}
        Each entity gets its own app directory with manifest.json, Component.js, i18n.
        The main entity '{main_entity}' should be the primary/first app.
        Child/composition entities should appear as ObjectPages within their parent's app, NOT as separate apps."""
        else:
            multi_app_instructions = f"""SINGLE-APP MODE: Generate 1 Fiori app for main entity '{main_entity}'.
        Include ObjectPages for ALL entities within this single app."""

        prompt = FIORI_GENERATION_PROMPT.format(
            project_name=project_name,
            app_id=app_id,
            main_entity=main_entity,
            layout_mode=layout_mode,
            fiori_theme=fiori_theme,
            complexity=complexity,
            architecture_context=architecture_context or "(architecture blueprint not available)",
            service_context=service_context or "(service CDS not available)",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            multi_app_instructions=multi_app_instructions,
        )

        # Inject knowledge into prompt
        prompt = f"{knowledge}\n\n{prompt}"

        # Self-Healing: Inject correction context if present
        correction_context = state.get("correction_context")
        if state.get("needs_correction") and state.get("correction_agent") == agent_name and correction_context:
            log_progress(state, "Applying self-healing correction context from validation agent...")
            correction_prompt = correction_context.get("correction_prompt", "")
            if correction_prompt:
                prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

        log_progress(state, f"Calling LLM for Fiori UI generation ({complexity} complexity)...")

        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=FIORI_SYSTEM_PROMPT,
            state=state,
            required_keys=["apps"],
            max_retries=3,
            agent_name=agent_name,
        )

        if result and result.get("apps"):
            apps = result["apps"]
            if isinstance(apps, list):
                for app_entry in apps:
                    entity_name = app_entry.get("entity", main_entity)
                    app_prefix = f"app/{entity_name.lower()}/webapp"
                    app_dir = f"app/{entity_name.lower()}"

                    if app_entry.get("manifest_json"):
                        generated_files.append({"path": f"{app_prefix}/manifest.json", "content": app_entry["manifest_json"], "file_type": "json"})
                    if app_entry.get("component_js"):
                        generated_files.append({"path": f"{app_prefix}/Component.js", "content": app_entry["component_js"], "file_type": "javascript"})
                    if app_entry.get("i18n_properties"):
                        generated_files.append({"path": f"{app_prefix}/i18n/i18n.properties", "content": app_entry["i18n_properties"], "file_type": "properties"})
                    if app_entry.get("ui5_yaml"):
                        generated_files.append({"path": f"{app_dir}/ui5.yaml", "content": app_entry["ui5_yaml"], "file_type": "yaml"})
                    if app_entry.get("xs_app_json"):
                        generated_files.append({"path": f"{app_dir}/xs-app.json", "content": app_entry["xs_app_json"], "file_type": "json"})

                # Shared files
                first_entity = apps[0].get("entity", main_entity).lower()
                if result.get("index_html"):
                    generated_files.append({"path": f"app/{first_entity}/webapp/index.html", "content": result["index_html"], "file_type": "html"})
                if result.get("flp_sandbox_html"):
                    generated_files.append({"path": f"app/{first_entity}/webapp/test/flpSandbox.html", "content": result["flp_sandbox_html"], "file_type": "html"})

                log_progress(state, f"✅ Generated {len(generated_files)} Fiori UI files across {len(apps)} app(s).")
            else:
                log_progress(state, "⚠️ Invalid apps format. Generating minimal Fiori config.")
                app_prefix = f"app/{main_entity.lower()}/webapp"
                generated_files.extend(_minimal_fiori(project_name, main_entity, app_prefix, fiori_theme))
        elif result:
            # Backward compatibility: old single-app format without 'apps' key
            app_prefix = f"app/{main_entity.lower()}/webapp"
            app_dir = f"app/{main_entity.lower()}"
            file_map = {
                "manifest_json": (f"{app_prefix}/manifest.json", "json"),
                "component_js": (f"{app_prefix}/Component.js", "javascript"),
                "i18n_properties": (f"{app_prefix}/i18n/i18n.properties", "properties"),
                "index_html": (f"{app_prefix}/index.html", "html"),
                "flp_sandbox_html": (f"{app_prefix}/test/flpSandbox.html", "html"),
                "ui5_yaml": (f"{app_dir}/ui5.yaml", "yaml"),
                "xs_app_json": (f"{app_dir}/xs-app.json", "json"),
            }
            for key, (path, file_type) in file_map.items():
                content = result.get(key, "")
                if content:
                    generated_files.append({"path": path, "content": content, "file_type": file_type})
            log_progress(state, f"✅ Generated {len(generated_files)} Fiori UI files (single-app mode).")
        else:
            log_progress(state, "⚠️ LLM generation failed. Generating minimal Fiori config.")
            app_prefix = f"app/{main_entity.lower()}/webapp"
            generated_files.extend(_minimal_fiori(project_name, main_entity, app_prefix, fiori_theme))
            errors.append({
                "agent": agent_name,
                "code": "LLM_FAILED",
                "message": "LLM Fiori generation failed. Minimal config generated.",
                "field": None,
                "severity": "warning",
            })

        store_generated_content(state, generated_files, {
            "manifest.json": "generated_manifest_json",
        })

        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, f"Fiori UI complete. Generated {len(generated_files)} files.")
        
        return {
            "artifacts_app": generated_files,
            "validation_errors": errors,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": state.get("current_logs", []),
            }],
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with error: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": str(e),
                "logs": None,
            }],
            "retry_counts": new_retry_counts,
            "needs_correction": True,
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            "current_agent": agent_name,
            "updated_at": completed_at,
        }


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
