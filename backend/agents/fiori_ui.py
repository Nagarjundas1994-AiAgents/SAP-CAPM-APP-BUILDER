"""
Agent 5: SAP Fiori UI Agent

Generates Fiori Elements applications including manifest.json, i18n files,
Component.js, and related configuration for List Report and Object Page apps.

Uses LLM to generate production-quality Fiori configurations with fallback to templates.
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
    FioriAppType,
    LayoutMode,
    FioriTheme,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

FIORI_SYSTEM_PROMPT = """You are an expert SAP Fiori Elements developer specializing in modern SAPUI5 applications.
Your task is to generate production-ready, enterprise-grade Fiori Elements configuration files.

STRICT RULES:
1. Manifest Version: Use manifest schema 1.59.0+. Use 'sap.fe.templates' for V4.
2. Multi-Entity Routing:
   - Always include a ListReport for the main entity.
   - Include ObjectPages for ALL entities (root and child).
   - Configure deep routing (e.g. RootEntity -> ChildEntity) so users can navigate down the composition tree.
3. Layout: ALWAYS use FlexibleColumnLayout (FCL) for a premium master-detail-detail experience.
4. Component: Component.js MUST extend 'sap.fe.core.AppComponent'.
5. Internationalization: 
   - Use 'i18n.properties' for all user-facing strings.
   - i18n keys must be descriptive: EntityName_plural, FieldName_label, Section_Title.
6. UI5 Version: Target 1.120.0 or higher.
7. Content Density: Support both 'compact' and 'cozy'.

OUTPUT FORMAT:
Return a JSON object:
{
  "manifest_json": { ... complete object ... },
  "component_js": "... Component.js content ...",
  "i18n_properties": "... i18n.properties content ...",
  "index_html": "... index.html content ..."
}
Return ONLY the JSON object."""


FIORI_GENERATION_PROMPT = """Generate a multi-entity SAP Fiori Elements application.

Project: {project_name} ({app_id})
Main Entity: {main_entity}
Layout: {layout_mode}

Metadata:
{service_content}
{entities_json}

Requirements:
1. manifest.json:
   - Configure ListReport for "{main_entity}".
   - Configure ObjectPage for "{main_entity}" and ALL associated/composited entities.
   - Use 'FCL' (FlexibleColumnLayout) for routing.
   - Set up navigation paths so child entities are reachable from parent Object Pages.
2. i18n.properties:
   - Generate at least 30+ labels covering all entities, fields, and UI sections.
   - Use human-readable titles (e.g. 'Product Details' instead of 'ProductObjectPage').
3. index.html:
   - Use theme "{theme}" and bootstrap the component correctly.

Ensure the app is fully navigable across all entities defined in the service."""


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

def generate_manifest_json(state: BuilderState) -> str:
    """Generate the Fiori Elements manifest.json (template fallback)."""
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    fiori_app_type = state.get("fiori_app_type", FioriAppType.LIST_REPORT.value)
    fiori_main_entity = state.get("fiori_main_entity", "")
    fiori_theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
    
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_path = project_name.lower().replace(' ', '-')
    
    manifest = {
        "_version": "1.59.0",
        "sap.app": {
            "id": app_id,
            "type": "application",
            "i18n": "i18n/i18n.properties",
            "applicationVersion": {"version": "1.0.0"},
            "title": "{{appTitle}}",
            "description": "{{appDescription}}",
            "resources": "resources.json",
            "sourceTemplate": {"id": "@sap/generator-fiori:lrop", "version": "1.0.0"},
            "dataSources": {
                "mainService": {
                    "uri": f"/{service_path}/",
                    "type": "OData",
                    "settings": {"localUri": "localService/metadata.xml", "odataVersion": "4.0"}
                }
            }
        },
        "sap.ui": {
            "technology": "UI5",
            "icons": {"icon": "", "favIcon": "", "phone": "", "phone@2": "", "tablet": "", "tablet@2": ""},
            "deviceTypes": {"desktop": True, "tablet": True, "phone": True}
        },
        "sap.ui5": {
            "flexEnabled": True,
            "dependencies": {
                "minUI5Version": "1.120.0",
                "libs": {"sap.m": {}, "sap.ui.core": {}, "sap.ushell": {}, "sap.fe.templates": {}}
            },
            "contentDensities": {"compact": True, "cozy": True},
            "models": {
                "i18n": {"type": "sap.ui.model.resource.ResourceModel", "settings": {"bundleName": f"{app_id}.i18n.i18n"}},
                "": {"dataSource": "mainService", "preload": True, "settings": {"operationMode": "Server", "autoExpandSelect": True, "earlyRequests": True}}
            },
            "routing": {
                "config": {},
                "routes": [
                    {"name": f"{fiori_main_entity}List", "pattern": ":?query:", "target": f"{fiori_main_entity}List"},
                    {"name": f"{fiori_main_entity}ObjectPage", "pattern": f"{fiori_main_entity}({{key}}):?query:", "target": f"{fiori_main_entity}ObjectPage"}
                ],
                "targets": {
                    f"{fiori_main_entity}List": {
                        "type": "Component", "id": f"{fiori_main_entity}List", "name": "sap.fe.templates.ListReport",
                        "options": {"settings": {"contextPath": f"/{fiori_main_entity}", "variantManagement": "Page",
                            "navigation": {fiori_main_entity: {"detail": {"route": f"{fiori_main_entity}ObjectPage"}}}}}
                    },
                    f"{fiori_main_entity}ObjectPage": {
                        "type": "Component", "id": f"{fiori_main_entity}ObjectPage", "name": "sap.fe.templates.ObjectPage",
                        "options": {"settings": {"contextPath": f"/{fiori_main_entity}", "editableHeaderContent": False}}
                    }
                }
            }
        },
        "sap.fiori": {"registrationIds": [], "archeType": "transactional"}
    }
    
    if layout_mode == LayoutMode.FLEXIBLE_COLUMN.value:
        manifest["sap.ui5"]["routing"]["config"]["flexibleColumnLayout"] = {
            "defaultTwoColumnLayoutType": "TwoColumnsBeginExpanded",
            "defaultThreeColumnLayoutType": "ThreeColumnsEndExpanded"
        }
    
    return json.dumps(manifest, indent=4)


def generate_component_js(state: BuilderState) -> str:
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    return f'''sap.ui.define([
    "sap/fe/core/AppComponent"
], function (AppComponent) {{
    "use strict";

    return AppComponent.extend("{app_id}.Component", {{
        metadata: {{
            manifest: "json"
        }}
    }});
}});
'''


def generate_i18n_properties(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    project_description = state.get("project_description", "")
    entities = state.get("entities", [])
    lines = [
        "# App Descriptor",
        f"appTitle={project_name}",
        f"appDescription={project_description or project_name + ' Application'}",
        "", "# Entity Labels",
    ]
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        lines.append(f"{entity_name}={entity_name}")
        lines.append(f"{entity_name}s={entity_name}s")
        for field in entity.get("fields", []):
            field_name = field.get("name", "")
            label = "".join(" " + c if c.isupper() else c for c in field_name).strip().title()
            lines.append(f"{field_name}={label}")
    lines += ["", "# Common Labels", "Create=Create", "Edit=Edit", "Delete=Delete", "Save=Save", "Cancel=Cancel"]
    return "\n".join(lines)


def generate_index_html(state: BuilderState) -> str:
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    fiori_theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name}</title>
    <script
        id="sap-ui-bootstrap"
        src="https://sapui5.hana.ondemand.com/resources/sap-ui-core.js"
        data-sap-ui-theme="{fiori_theme}"
        data-sap-ui-compatVersion="edge"
        data-sap-ui-async="true"
        data-sap-ui-resourceroots='{{"{app_id}": "."}}'
        data-sap-ui-oninit="module:sap/ui/core/ComponentSupport"
        data-sap-ui-frameOptions="trusted">
    </script>
</head>
<body class="sapUiBody" id="content">
    <div data-sap-ui-component
        data-name="{app_id}"
        data-id="container"
        data-settings='{{"id": "{app_id}"}}'>
    </div>
</body>
</html>
'''


def generate_xs_app_json() -> str:
    return json.dumps({
        "welcomeFile": "/index.html",
        "authenticationMethod": "route",
        "routes": [{"source": "^/(.*)$", "target": "$1", "service": "html5-apps-repo-rt"}]
    }, indent=4)


# =============================================================================
# Main Agent Function
# =============================================================================

async def fiori_ui_agent(state: BuilderState) -> BuilderState:
    """
    SAP Fiori UI Agent (LLM-Driven)
    
    Uses LLM to generate production-quality Fiori Elements configurations.
    Falls back to template-based generation if LLM fails.
    """
    logger.info("Starting Fiori UI Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "fiori_ui"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting Fiori UI generation...")
    
    # Determine main entity
    fiori_main_entity = state.get("fiori_main_entity", "")
    if not fiori_main_entity:
        entities = state.get("entities", [])
        if entities:
            fiori_main_entity = entities[0].get("name", "Entity")
            state["fiori_main_entity"] = fiori_main_entity
        else:
            log_progress(state, "Error: No entities found for Fiori UI generation.")
            errors.append({"agent": "fiori_ui", "code": "NO_MAIN_ENTITY", "message": "No main entity specified", "field": "fiori_main_entity", "severity": "error"})
            state["validation_errors"] = state.get("validation_errors", []) + errors
            return state
    
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    app_type = state.get("fiori_app_type", FioriAppType.LIST_REPORT.value)
    theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    provider = state.get("llm_provider")
    
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    service_path = project_name.lower().replace(' ', '-')
    app_name = fiori_main_entity.lower()
    base_path = f"app/{app_name}/webapp"
    
    # Get previously generated artifacts
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
        
        prompt = FIORI_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            description=description or "No description",
            main_entity=fiori_main_entity,
            app_type=app_type,
            theme=theme,
            layout_mode=layout_mode,
            service_content=service_content or "(not available)",
            schema_content=schema_content or "(not available)",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            app_id=app_id,
            service_path=service_path,
        )
        
        log_progress(state, "Calling LLM for Fiori Elements generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=FIORI_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("manifest_json"):
            manifest_data = parsed["manifest_json"]
            if isinstance(manifest_data, dict):
                manifest_str = json.dumps(manifest_data, indent=4)
            else:
                manifest_str = str(manifest_data)
            
            generated_files.append({"path": f"{base_path}/manifest.json", "content": manifest_str, "file_type": "json"})
            log_progress(state, "LLM-generated manifest.json accepted.")
            
            if parsed.get("component_js"):
                generated_files.append({"path": f"{base_path}/Component.js", "content": parsed["component_js"], "file_type": "js"})
            
            if parsed.get("i18n_properties"):
                generated_files.append({"path": f"{base_path}/i18n/i18n.properties", "content": parsed["i18n_properties"], "file_type": "properties"})
            
            if parsed.get("index_html"):
                generated_files.append({"path": f"{base_path}/index.html", "content": parsed["index_html"], "file_type": "html"})
            
            llm_success = True
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for Fiori UI: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        try:
            log_progress(state, "Generating Fiori files via template fallback...")
            generated_files.append({"path": f"{base_path}/manifest.json", "content": generate_manifest_json(state), "file_type": "json"})
            generated_files.append({"path": f"{base_path}/Component.js", "content": generate_component_js(state), "file_type": "js"})
            generated_files.append({"path": f"{base_path}/i18n/i18n.properties", "content": generate_i18n_properties(state), "file_type": "properties"})
            generated_files.append({"path": f"{base_path}/index.html", "content": generate_index_html(state), "file_type": "html"})
        except Exception as e:
            logger.error(f"Template fallback failed for Fiori UI: {e}")
            errors.append({"agent": "fiori_ui", "code": "FIORI_GENERATION_ERROR", "message": f"Fiori generation failed: {str(e)}", "field": None, "severity": "error"})
    
    # xs-app.json (always template - trivial)
    generated_files.append({"path": f"app/{app_name}/xs-app.json", "content": generate_xs_app_json(), "file_type": "json"})
    
    # ==========================================================================
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    # Get retry configuration
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("fiori_ui", 0)
    
    # Validate the generated manifest.json
    manifest_artifact = next((f for f in generated_files if f["path"].endswith("manifest.json")), None)
    if manifest_artifact and llm_success:
        validation_results = validate_artifact(manifest_artifact["path"], manifest_artifact["content"])
        
        if any(result.has_errors for result in validation_results):
            if should_retry_agent(validation_results, retry_count, max_retries):
                log_progress(state, f"Validation found errors. Attempting correction (retry {retry_count + 1}/{max_retries})...")
                
                if "retry_counts" not in state:
                    state["retry_counts"] = {}
                state["retry_counts"]["fiori_ui"] = retry_count + 1
                state["needs_correction"] = True
                
                if "correction_history" not in state:
                    state["correction_history"] = []
                state["correction_history"].append({
                    "agent": "fiori_ui",
                    "retry": retry_count + 1,
                    "errors_found": sum(r.error_count for r in validation_results),
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            log_progress(state, f"  - {issue.message}")
                
                state["artifacts_app"] = []
                return state
            else:
                log_progress(state, "⚠️ Max retries reached. Some validation errors remain.")
                for result in validation_results:
                    for issue in result.issues:
                        if issue.severity.value == "error":
                            errors.append({
                                "agent": "fiori_ui",
                                "code": issue.code or "VALIDATION_ERROR",
                                "message": issue.message,
                                "field": None,
                                "severity": "warning"
                            })
        else:
            if retry_count > 0:
                log_progress(state, f"✅ Validation passed after {retry_count} correction(s)")
                summary = format_correction_summary("fiori_ui", retry_count, retry_count, retry_count)
                if "auto_fixed_errors" not in state:
                    state["auto_fixed_errors"] = []
                state["auto_fixed_errors"].append({
                    "agent": "fiori_ui",
                    "summary": summary,
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                log_progress(state, "✅ Validation passed on first attempt")

    state["needs_correction"] = False
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_app"] = state.get("artifacts_app", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "fiori_ui",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "retry_count": retry_count,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Fiori UI generation complete ({generation_method}).")
    logger.info(f"Fiori UI Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
