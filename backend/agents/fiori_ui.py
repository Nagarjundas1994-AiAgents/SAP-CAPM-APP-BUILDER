"""
Agent 5: SAP Fiori UI Agent

Generates Fiori Elements applications including manifest.json, i18n files,
Component.js, and related configuration for List Report and Object Page apps.
"""

import logging
import json
from datetime import datetime
from typing import Any

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
# Fiori Elements Generation
# =============================================================================

def generate_manifest_json(state: BuilderState) -> str:
    """Generate the Fiori Elements manifest.json."""
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    fiori_app_type = state.get("fiori_app_type", FioriAppType.LIST_REPORT.value)
    fiori_main_entity = state.get("fiori_main_entity", "")
    fiori_theme = state.get("fiori_theme", FioriTheme.SAP_HORIZON.value)
    layout_mode = state.get("fiori_layout_mode", LayoutMode.FLEXIBLE_COLUMN.value)
    
    # App ID
    app_id = f"{namespace}.{project_name.lower().replace('-', '').replace(' ', '')}"
    
    # Service name
    service_name = "".join(word.capitalize() for word in project_name.replace("-", " ").replace("_", " ").split())
    service_path = project_name.lower().replace(' ', '-')
    
    # Determine template based on app type
    if fiori_app_type == FioriAppType.ANALYTICAL_LIST_PAGE.value:
        template = "sap.fe.templates.AnalyticalListPage"
    elif fiori_app_type == FioriAppType.WORKLIST.value:
        template = "sap.fe.templates.ListReport"
    else:
        template = "sap.fe.templates.ListReport"
    
    manifest = {
        "_version": "1.59.0",
        "sap.app": {
            "id": app_id,
            "type": "application",
            "i18n": "i18n/i18n.properties",
            "applicationVersion": {
                "version": "1.0.0"
            },
            "title": f"{{{{appTitle}}}}",
            "description": f"{{{{appDescription}}}}",
            "resources": "resources.json",
            "sourceTemplate": {
                "id": "@sap/generator-fiori:lrop",
                "version": "1.0.0"
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
            "deviceTypes": {
                "desktop": True,
                "tablet": True,
                "phone": True
            }
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
            "contentDensities": {
                "compact": True,
                "cozy": True
            },
            "models": {
                "i18n": {
                    "type": "sap.ui.model.resource.ResourceModel",
                    "settings": {
                        "bundleName": f"{app_id}.i18n.i18n"
                    }
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
                "routes": [
                    {
                        "name": f"{fiori_main_entity}List",
                        "pattern": f":?query:",
                        "target": f"{fiori_main_entity}List"
                    },
                    {
                        "name": f"{fiori_main_entity}ObjectPage",
                        "pattern": f"{fiori_main_entity}({{key}}):?query:",
                        "target": f"{fiori_main_entity}ObjectPage"
                    }
                ],
                "targets": {
                    f"{fiori_main_entity}List": {
                        "type": "Component",
                        "id": f"{fiori_main_entity}List",
                        "name": "sap.fe.templates.ListReport",
                        "options": {
                            "settings": {
                                "contextPath": f"/{fiori_main_entity}",
                                "variantManagement": "Page",
                                "navigation": {
                                    fiori_main_entity: {
                                        "detail": {
                                            "route": f"{fiori_main_entity}ObjectPage"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    f"{fiori_main_entity}ObjectPage": {
                        "type": "Component",
                        "id": f"{fiori_main_entity}ObjectPage",
                        "name": "sap.fe.templates.ObjectPage",
                        "options": {
                            "settings": {
                                "contextPath": f"/{fiori_main_entity}",
                                "editableHeaderContent": False
                            }
                        }
                    }
                }
            }
        },
        "sap.fiori": {
            "registrationIds": [],
            "archeType": "transactional"
        }
    }
    
    # Add flexible column layout if enabled
    if layout_mode == LayoutMode.FLEXIBLE_COLUMN.value:
        manifest["sap.ui5"]["routing"]["config"]["flexibleColumnLayout"] = {
            "defaultTwoColumnLayoutType": "TwoColumnsBeginExpanded",
            "defaultThreeColumnLayoutType": "ThreeColumnsEndExpanded"
        }
    
    return json.dumps(manifest, indent=4)


def generate_component_js(state: BuilderState) -> str:
    """Generate Component.js for Fiori app."""
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
    """Generate i18n.properties file."""
    project_name = state.get("project_name", "App")
    project_description = state.get("project_description", "")
    fiori_main_entity = state.get("fiori_main_entity", "Entity")
    entities = state.get("entities", [])
    
    lines = []
    lines.append("# App Descriptor")
    lines.append(f"appTitle={project_name}")
    lines.append(f"appDescription={project_description or project_name + ' Application'}")
    lines.append("")
    lines.append("# Entity Labels")
    
    for entity in entities:
        entity_name = entity.get("name", "Entity")
        lines.append(f"{entity_name}={entity_name}")
        lines.append(f"{entity_name}s={entity_name}s")
        
        # Field labels
        for field in entity.get("fields", []):
            field_name = field.get("name", "")
            # Convert camelCase to Title Case
            label = "".join(" " + c if c.isupper() else c for c in field_name).strip().title()
            lines.append(f"{field_name}={label}")
    
    lines.append("")
    lines.append("# Common Labels")
    lines.append("Create=Create")
    lines.append("Edit=Edit")
    lines.append("Delete=Delete")
    lines.append("Save=Save")
    lines.append("Cancel=Cancel")
    
    return "\n".join(lines)


def generate_index_html(state: BuilderState) -> str:
    """Generate index.html for standalone testing."""
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


def generate_xs_app_json(state: BuilderState) -> str:
    """Generate xs-app.json for app router."""
    return json.dumps({
        "welcomeFile": "/index.html",
        "authenticationMethod": "route",
        "routes": [
            {
                "source": "^/(.*)$",
                "target": "$1",
                "service": "html5-apps-repo-rt"
            }
        ]
    }, indent=4)


# =============================================================================
# Main Agent Function
# =============================================================================

async def fiori_ui_agent(state: BuilderState) -> BuilderState:
    """
    SAP Fiori UI Agent
    
    Generates:
    1. app/{appname}/webapp/manifest.json - App descriptor
    2. app/{appname}/webapp/Component.js - UI5 component
    3. app/{appname}/webapp/i18n/i18n.properties - Translations
    4. app/{appname}/webapp/index.html - Standalone HTML
    5. app/{appname}/xs-app.json - App router config
    
    Returns updated state with generated Fiori files.
    """
    logger.info("Starting Fiori UI Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "fiori_ui"
    state["updated_at"] = now
    
    # Check prerequisites
    fiori_main_entity = state.get("fiori_main_entity", "")
    if not fiori_main_entity:
        entities = state.get("entities", [])
        if entities:
            fiori_main_entity = entities[0].get("name", "Entity")
            state["fiori_main_entity"] = fiori_main_entity
        else:
            errors.append({
                "agent": "fiori_ui",
                "code": "NO_MAIN_ENTITY",
                "message": "No main entity specified for Fiori app",
                "field": "fiori_main_entity",
                "severity": "error",
            })
            state["validation_errors"] = state.get("validation_errors", []) + errors
            return state
    
    # App name (lowercased entity)
    app_name = fiori_main_entity.lower()
    base_path = f"app/{app_name}/webapp"
    
    # ==========================================================================
    # Generate manifest.json
    # ==========================================================================
    try:
        manifest = generate_manifest_json(state)
        generated_files.append({
            "path": f"{base_path}/manifest.json",
            "content": manifest,
            "file_type": "json",
        })
        logger.info(f"Generated {base_path}/manifest.json")
    except Exception as e:
        logger.error(f"Failed to generate manifest.json: {e}")
        errors.append({
            "agent": "fiori_ui",
            "code": "MANIFEST_GENERATION_ERROR",
            "message": f"Failed to generate manifest: {str(e)}",
            "field": None,
            "severity": "error",
        })
    
    # ==========================================================================
    # Generate Component.js
    # ==========================================================================
    try:
        component = generate_component_js(state)
        generated_files.append({
            "path": f"{base_path}/Component.js",
            "content": component,
            "file_type": "js",
        })
        logger.info(f"Generated {base_path}/Component.js")
    except Exception as e:
        logger.error(f"Failed to generate Component.js: {e}")
    
    # ==========================================================================
    # Generate i18n
    # ==========================================================================
    try:
        i18n = generate_i18n_properties(state)
        generated_files.append({
            "path": f"{base_path}/i18n/i18n.properties",
            "content": i18n,
            "file_type": "properties",
        })
        logger.info(f"Generated {base_path}/i18n/i18n.properties")
    except Exception as e:
        logger.error(f"Failed to generate i18n: {e}")
    
    # ==========================================================================
    # Generate index.html
    # ==========================================================================
    try:
        index = generate_index_html(state)
        generated_files.append({
            "path": f"{base_path}/index.html",
            "content": index,
            "file_type": "html",
        })
        logger.info(f"Generated {base_path}/index.html")
    except Exception as e:
        logger.error(f"Failed to generate index.html: {e}")
    
    # ==========================================================================
    # Generate xs-app.json
    # ==========================================================================
    try:
        xs_app = generate_xs_app_json(state)
        generated_files.append({
            "path": f"app/{app_name}/xs-app.json",
            "content": xs_app,
            "file_type": "json",
        })
        logger.info(f"Generated app/{app_name}/xs-app.json")
    except Exception as e:
        logger.error(f"Failed to generate xs-app.json: {e}")
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_app"] = state.get("artifacts_app", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "fiori_ui",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Fiori UI Agent completed. Generated {len(generated_files)} files.")
    
    return state
