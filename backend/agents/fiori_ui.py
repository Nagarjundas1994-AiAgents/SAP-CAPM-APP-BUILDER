"""
Agent 5: SAP Fiori UI Agent

Generates Fiori Elements applications including manifest.json, i18n files,
Component.js, and related configuration for List Report and Object Page apps.

Industry-level features:
- FlexibleColumnLayout (FCL) with multi-level navigation
- Deep routing for ALL entities (root → child → grandchild)
- crossNavigation for Fiori Launchpad integration
- sap.cloud section for BTP deployment
- flpSandbox.html for local Launchpad testing
- ui5.yaml for SAP UI5 Tooling
- Variant management per page
- Comprehensive i18n with structured keys
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

FIORI_SYSTEM_PROMPT = """You are a senior SAP Fiori Elements developer specializing in modern SAPUI5 applications.
Generate production-ready, enterprise-grade Fiori Elements configuration files.

STRICT RULES:
1. Manifest Version: Use manifest schema 1.59.0+. Use 'sap.fe.templates' for V4.
2. Multi-Entity Routing:
   - Include a ListReport for the main entity.
   - Include ObjectPages for ALL entities (root and child).
   - Configure deep routing so users can navigate the composition tree.
3. Layout: ALWAYS use FlexibleColumnLayout (FCL).
4. Component: Component.js MUST extend 'sap.fe.core.AppComponent'.
5. Internationalization: Use 'i18n.properties' for all user-facing strings.
6. UI5 Version: Target 1.120.0 or higher.
7. Content Density: Support both 'compact' and 'cozy'.
8. Cross Navigation: Include sap.app/crossNavigation for Fiori Launchpad.
9. Cloud: Include sap.cloud section for BTP HTML5 repository.

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
   - Include crossNavigation inbound for Fiori Launchpad
   - Include sap.cloud section for BTP deployment
   - Set up navigation paths so child entities are reachable from parent Object Pages.
2. i18n.properties:
   - Generate 30+ labels covering all entities, fields, and UI sections.
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


def _humanize(name: str) -> str:
    """Convert camelCase/PascalCase to human-readable text."""
    words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
    return " ".join(w.capitalize() for w in words) if words else name


def _pluralize(name: str) -> str:
    human = _humanize(name)
    if human.endswith("y") and human[-2:] not in ("ey", "ay", "oy"):
        return human[:-1] + "ies"
    if human.endswith(("s", "sh", "ch", "x")):
        return human + "es"
    return human + "s"


def _get_children(entity_name: str, relationships: list) -> list:
    """Get composition children of an entity."""
    return [
        r for r in relationships
        if r.get("type") == "composition" and r.get("source_entity") == entity_name
    ]


def _is_child(entity_name: str, relationships: list) -> bool:
    return any(
        r.get("type") == "composition" and r.get("target_entity") == entity_name
        for r in relationships
    )


# =============================================================================
# Template Fallback Functions
# =============================================================================

def generate_manifest_json(state: BuilderState) -> str:
    """Generate Fiori Elements manifest.json with FCL, crossNavigation, and sap.cloud."""
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    fiori_main_entity = state.get("fiori_main_entity", "")
    fiori_theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])

    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    service_name = "".join(
        word.capitalize()
        for word in project_name.replace("-", " ").replace("_", " ").split()
    )
    service_path = project_name.lower().replace(' ', '-')

    if not fiori_main_entity and entities:
        # Pick the first root entity (not a composition child)
        for e in entities:
            if not _is_child(e.get("name", ""), relationships):
                fiori_main_entity = e.get("name", "Entity")
                break
        if not fiori_main_entity:
            fiori_main_entity = entities[0].get("name", "Entity")

    # ── Build routes and targets ──
    routes = []
    targets = {}

    # Main ListReport
    routes.append({
        "name": f"{fiori_main_entity}List",
        "pattern": ":?query:",
        "target": f"{fiori_main_entity}List"
    })
    targets[f"{fiori_main_entity}List"] = {
        "type": "Component",
        "id": f"{fiori_main_entity}List",
        "name": "sap.fe.templates.ListReport",
        "options": {
            "settings": {
                "contextPath": f"/{fiori_main_entity}",
                "variantManagement": "Page",
                "initialLoad": "Enabled",
                "navigation": {
                    fiori_main_entity: {
                        "detail": {"route": f"{fiori_main_entity}ObjectPage"}
                    }
                }
            }
        }
    }

    # Main ObjectPage
    routes.append({
        "name": f"{fiori_main_entity}ObjectPage",
        "pattern": f"{fiori_main_entity}({{key}}):?query:",
        "target": f"{fiori_main_entity}ObjectPage"
    })

    # Build child navigation for main entity
    main_children = _get_children(fiori_main_entity, relationships)
    child_nav = {}
    for child_rel in main_children:
        child_name = child_rel.get("target_entity", "")
        rel_name = child_rel.get("name", child_name.lower())
        child_nav[rel_name] = {
            "detail": {"route": f"{child_name}ObjectPage"}
        }

    obj_page_settings = {
        "contextPath": f"/{fiori_main_entity}",
        "editableHeaderContent": False
    }
    if child_nav:
        obj_page_settings["navigation"] = child_nav

    targets[f"{fiori_main_entity}ObjectPage"] = {
        "type": "Component",
        "id": f"{fiori_main_entity}ObjectPage",
        "name": "sap.fe.templates.ObjectPage",
        "options": {"settings": obj_page_settings}
    }

    # Child entity ObjectPages
    for child_rel in main_children:
        child_name = child_rel.get("target_entity", "")
        rel_name = child_rel.get("name", child_name.lower())
        
        routes.append({
            "name": f"{child_name}ObjectPage",
            "pattern": f"{fiori_main_entity}({{key}})/{rel_name}({{key2}}):?query:",
            "target": f"{child_name}ObjectPage"
        })
        targets[f"{child_name}ObjectPage"] = {
            "type": "Component",
            "id": f"{child_name}ObjectPage",
            "name": "sap.fe.templates.ObjectPage",
            "options": {
                "settings": {
                    "contextPath": f"/{fiori_main_entity}/{rel_name}",
                    "editableHeaderContent": False
                }
            }
        }

    # ── Build manifest ──
    semantic_object = fiori_main_entity
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
            "sourceTemplate": {
                "id": "@sap/generator-fiori:lrop",
                "version": "1.12.0",
                "toolsId": "7c67f9e0-e1a8-49b8-a7e3-042b7e2c7d36"
            },
            "dataSources": {
                "mainService": {
                    "uri": f"/{service_path}/",
                    "type": "OData",
                    "settings": {
                        "localUri": "localService/metadata.xml",
                        "odataVersion": "4.0"
                    }
                }
            },
            "crossNavigation": {
                "inbounds": {
                    f"{semantic_object}-manage": {
                        "semanticObject": semantic_object,
                        "action": "manage",
                        "title": f"{{{{flpTitle}}}}",
                        "subTitle": f"{{{{flpSubtitle}}}}",
                        "signature": {
                            "parameters": {},
                            "additionalParameters": "allowed"
                        }
                    }
                }
            }
        },
        "sap.ui": {
            "technology": "UI5",
            "icons": {
                "icon": "",
                "favIcon": "",
                "phone": "",
                "phone@2": "",
                "tablet": "",
                "tablet@2": ""
            },
            "deviceTypes": {"desktop": True, "tablet": True, "phone": True}
        },
        "sap.ui5": {
            "flexEnabled": True,
            "dependencies": {
                "minUI5Version": "1.120.0",
                "libs": {
                    "sap.m": {},
                    "sap.ui.core": {},
                    "sap.ushell": {},
                    "sap.fe.templates": {}
                }
            },
            "contentDensities": {"compact": True, "cozy": True},
            "models": {
                "i18n": {
                    "type": "sap.ui.model.resource.ResourceModel",
                    "settings": {"bundleName": f"{app_id}.i18n.i18n"}
                },
                "": {
                    "dataSource": "mainService",
                    "preload": True,
                    "settings": {
                        "operationMode": "Server",
                        "autoExpandSelect": True,
                        "earlyRequests": True
                    }
                }
            },
            "routing": {
                "config": {},
                "routes": routes,
                "targets": targets
            }
        },
        "sap.cloud": {
            "public": True,
            "service": f"{service_path}"
        },
        "sap.fiori": {
            "registrationIds": [],
            "archeType": "transactional"
        }
    }

    # Apply FCL layout config
    if layout_mode == LayoutMode.FLEXIBLE_COLUMN.value:
        manifest["sap.ui5"]["routing"]["config"]["flexibleColumnLayout"] = {
            "defaultTwoColumnLayoutType": "TwoColumnsMidExpanded",
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
    """Generate comprehensive i18n.properties with structured keys."""
    project_name = state.get("project_name", "App")
    project_description = state.get("project_description", "")
    entities = state.get("entities", [])

    lines = [
        "# =============================================================================",
        "# App Descriptor",
        "# =============================================================================",
        f"appTitle={project_name}",
        f"appDescription={project_description or project_name + ' Application'}",
        "",
        "# Fiori Launchpad",
        f"flpTitle=Manage {_pluralize(entities[0].get('name', 'Items')) if entities else 'Items'}",
        f"flpSubtitle={project_description or 'Manage application data'}",
        "",
        "# =============================================================================",
        "# Common Labels",
        "# =============================================================================",
        "Create=Create",
        "Edit=Edit",
        "Delete=Delete",
        "Save=Save",
        "Cancel=Cancel",
        "Approve=Approve",
        "Reject=Reject",
        "GeneralInfo=General Information",
        "StatusDetails=Status & Details",
        "AdminData=Administrative Data",
        "NotesComments=Notes & Comments",
    ]

    for entity in entities:
        entity_name = entity.get("name", "Entity")
        human = _humanize(entity_name)
        plural = _pluralize(entity_name)

        lines.append("")
        lines.append(f"# =============================================================================")
        lines.append(f"# {entity_name}")
        lines.append(f"# =============================================================================")
        lines.append(f"{entity_name}={human}")
        lines.append(f"{entity_name}_plural={plural}")
        lines.append(f"{entity_name}_new=New {human}")

        for field in entity.get("fields", []):
            field_name = field.get("name", "")
            label = _humanize(field_name)
            lines.append(f"{field_name}_label={label}")

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


def generate_flp_sandbox_html(state: BuilderState) -> str:
    """Generate flpSandbox.html for Fiori Launchpad testing."""
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    fiori_theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    fiori_main_entity = state.get("fiori_main_entity", "")
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} - Fiori Launchpad Sandbox</title>
    <script>
        window["sap-ushell-config"] = {{
            defaultRenderer: "fiori2",
            applications: {{
                "{fiori_main_entity}-manage": {{
                    title: "{_humanize(project_name)}",
                    description: "Manage {_pluralize(fiori_main_entity)}",
                    additionalInformation: "SAPUI5.Component={app_id}",
                    applicationType: "URL",
                    url: "../",
                    navigationMode: "embedded"
                }}
            }}
        }};
    </script>
    <script
        id="sap-ui-bootstrap"
        src="https://sapui5.hana.ondemand.com/test-resources/sap/ushell/bootstrap/sandbox.js"
        data-sap-ui-theme="{fiori_theme}"
        data-sap-ui-compatVersion="edge"
        data-sap-ui-async="true"
        data-sap-ui-frameOptions="allow"
        data-sap-ui-language="en">
    </script>
</head>
<body class="sapUiBody" id="content">
</body>
</html>
'''


def generate_ui5_yaml(state: BuilderState) -> str:
    """Generate ui5.yaml for SAP UI5 Tooling."""
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    fiori_main_entity = state.get("fiori_main_entity", "")
    service_path = project_name.lower().replace(' ', '-')
    app_name = fiori_main_entity.lower() if fiori_main_entity else project_name.lower()

    return f"""# yaml-language-server: $schema=https://sap.github.io/ui5-tooling/schema/ui5.yaml.json

specVersion: "3.0"
metadata:
  name: {namespace}.{project_name.lower().replace('-', '').replace(' ', '')}
type: application

framework:
  name: SAPUI5
  version: "1.120.0"
  libraries:
    - name: sap.m
    - name: sap.ui.core
    - name: sap.ushell
    - name: sap.fe.templates
    - name: themelib_sap_horizon

server:
  customMiddleware:
    - name: fiori-tools-proxy
      afterMiddleware: compression
      configuration:
        ignoreCertError: false
        ui5:
          path:
            - /resources
            - /test-resources
          url: https://ui5.sap.com
        backend:
          - path: /{service_path}
            url: http://localhost:4004
    - name: fiori-tools-appreload
      afterMiddleware: compression
      configuration:
        port: 35729
        path: webapp
"""


def generate_xs_app_json(state: BuilderState) -> str:
    """Generate xs-app.json for managed app router."""
    service_path = state.get("project_name", "app").lower().replace(' ', '-')
    return json.dumps({
        "welcomeFile": "/index.html",
        "authenticationMethod": "route",
        "routes": [
            {
                "source": f"^/{service_path}/(.*)$",
                "target": "$1",
                "destination": "srv-api",
                "authenticationType": "xsuaa",
                "csrfProtection": True
            },
            {
                "source": "^/(.*)$",
                "target": "$1",
                "service": "html5-apps-repo-rt",
                "authenticationType": "xsuaa"
            }
        ]
    }, indent=4)


# =============================================================================
# Main Agent Function
# =============================================================================

async def fiori_ui_agent(state: BuilderState) -> BuilderState:
    """
    SAP Fiori UI Agent (LLM-Driven)
    
    Uses LLM to generate production-quality Fiori Elements configurations.
    Falls back to template-based generation if LLM fails.
    
    Generates:
    1. app/{entity}/webapp/manifest.json - FCL routing, crossNavigation, sap.cloud
    2. app/{entity}/webapp/Component.js
    3. app/{entity}/webapp/i18n/i18n.properties - Comprehensive labels
    4. app/{entity}/webapp/index.html
    5. app/{entity}/webapp/test/flpSandbox.html - Launchpad sandbox
    6. app/{entity}/ui5.yaml - SAP UI5 Tooling config
    7. app/{entity}/xs-app.json - Managed app router config
    """
    logger.info("Starting Fiori UI Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "fiori_ui"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting Fiori UI generation...")
    
    # Determine main entity (prefer first root entity)
    fiori_main_entity = state.get("fiori_main_entity", "")
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    
    if not fiori_main_entity:
        if entities:
            for e in entities:
                if not _is_child(e.get("name", ""), relationships):
                    fiori_main_entity = e.get("name", "Entity")
                    break
            if not fiori_main_entity:
                fiori_main_entity = entities[0].get("name", "Entity")
            state["fiori_main_entity"] = fiori_main_entity
        else:
            log_progress(state, "Error: No entities found for Fiori UI generation.")
            errors.append({"agent": "fiori_ui", "code": "NO_MAIN_ENTITY", "message": "No main entity", "field": "fiori_main_entity", "severity": "error"})
            state["validation_errors"] = state.get("validation_errors", []) + errors
            return state
    
    namespace = state.get("project_namespace", "com.company.app")
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    app_type = state.get("fiori_app_type", FioriAppType.LIST_REPORT.value)
    theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
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
            manifest_str = json.dumps(manifest_data, indent=4) if isinstance(manifest_data, dict) else str(manifest_data)
            
            generated_files.append({"path": f"{base_path}/manifest.json", "content": manifest_str, "file_type": "json"})
            log_progress(state, "✅ LLM-generated manifest.json accepted.")
            
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
    # Fallback: Template-based generation (industry-grade)
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
    
    # Always generate these files via template (trivial/config files)
    log_progress(state, "Generating flpSandbox.html, ui5.yaml, xs-app.json...")
    generated_files.append({"path": f"{base_path}/test/flpSandbox.html", "content": generate_flp_sandbox_html(state), "file_type": "html"})
    generated_files.append({"path": f"app/{app_name}/ui5.yaml", "content": generate_ui5_yaml(state), "file_type": "yaml"})
    generated_files.append({"path": f"app/{app_name}/xs-app.json", "content": generate_xs_app_json(state), "file_type": "json"})
    
    # ==========================================================================
    # Validation & Self-Healing
    # ==========================================================================
    from backend.agents.validator import validate_artifact
    from backend.agents.correction import generate_correction_prompt, should_retry_agent, format_correction_summary
    
    max_retries = 3
    retry_count = state.get("retry_counts", {}).get("fiori_ui", 0)
    
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
    log_progress(state, f"Fiori UI generation complete ({generation_method}). Generated {len(generated_files)} files.")
    logger.info(f"Fiori UI Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
