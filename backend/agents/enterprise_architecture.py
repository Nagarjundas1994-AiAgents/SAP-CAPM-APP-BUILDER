"""
Agent: Enterprise Architecture Blueprint

Builds a deterministic enterprise solution blueprint before implementation
so downstream agents receive a clear service, UI, security, and delivery plan.

ARCHITECTURE IMPROVEMENTS (2026-03-15):
- Added timeout wrapper
- Proper retry counter increment
- Returns partial state
- Records agent_history
- Handles exceptions properly
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.progress import log_progress
from backend.agents.resilience import with_timeout
from backend.agents.state import (
    BuilderState,
    EnterpriseBlueprint,
    GeneratedFile,
    ServiceModuleDefinition,
    UIAppDefinition,
)

logger = logging.getLogger(__name__)


def _is_composition_child(entity_name: str, relationships: list[dict]) -> bool:
    return any(
        rel.get("type") == "composition" and rel.get("target_entity") == entity_name
        for rel in relationships
    )


def _classify_entity(entity: dict) -> str:
    fields = entity.get("fields", [])
    field_names = {str(field.get("name", "")).lower() for field in fields if isinstance(field, dict)}
    name = entity.get("name", "")
    name_lower = name.lower()

    if any(token in name_lower for token in ["item", "line", "detail", "history", "event", "log"]):
        return "line_item"
    if any(token in field_names for token in ["status", "totalamount", "amount", "quantity", "duedate", "approvedat"]):
        return "transactional"
    if any(token in name_lower for token in ["type", "category", "code", "master", "grade", "plan"]):
        return "reference"
    return "master"


def _build_service_modules(
    entities: list[dict],
    relationships: list[dict],
    integrations: list[dict],
) -> list[ServiceModuleDefinition]:
    root_entities = [
        entity for entity in entities if not _is_composition_child(entity.get("name", ""), relationships)
    ]
    transactional = [e.get("name", "") for e in root_entities if _classify_entity(e) == "transactional"]
    master = [e.get("name", "") for e in root_entities if _classify_entity(e) in {"master", "reference"}]
    analytics = [e.get("name", "") for e in root_entities if "status" in {
        str(field.get("name", "")).lower()
        for field in e.get("fields", [])
        if isinstance(field, dict)
    }]

    modules: list[ServiceModuleDefinition] = []
    if transactional:
        modules.append({
            "name": "OperationsService",
            "purpose": "Transactional processing, approvals, draft handling, and core business workflows",
            "entities": transactional,
            "exposure_type": "transactional",
        })
    if master:
        modules.append({
            "name": "MasterDataService",
            "purpose": "Reusable value help, catalog, and reference data maintenance",
            "entities": master,
            "exposure_type": "catalog",
        })
    if analytics:
        modules.append({
            "name": "AnalyticsService",
            "purpose": "Read-optimized KPIs, dashboards, and operational reporting",
            "entities": analytics,
            "exposure_type": "analytics",
        })
    if integrations:
        modules.append({
            "name": "IntegrationService",
            "purpose": "External SAP and non-SAP connectivity through destinations and mashups",
            "entities": [e.get("name", "") for e in root_entities[:3]],
            "exposure_type": "integration",
        })

    if not modules:
        modules.append({
            "name": "CoreService",
            "purpose": "Core business processing for the generated domain",
            "entities": [e.get("name", "") for e in root_entities],
            "exposure_type": "transactional",
        })

    modules.append({
        "name": "AdminService",
        "purpose": "Configuration, audit, support tooling, and privileged maintenance",
        "entities": [e.get("name", "") for e in root_entities[: max(1, min(3, len(root_entities)))]],
        "exposure_type": "admin",
    })
    return modules


def _build_ui_apps(
    root_entities: list[dict],
    service_modules: list[ServiceModuleDefinition],
    complexity: str,
) -> list[UIAppDefinition]:
    service_name = service_modules[0]["name"] if service_modules else "OperationsService"
    apps: list[UIAppDefinition] = []

    for entity in root_entities:
        name = entity.get("name", "")
        entity_type = _classify_entity(entity)
        app_type = "list_report"
        if entity_type == "transactional":
            app_type = "worklist"
        if complexity in {"enterprise", "full_stack"} and entity_type == "transactional":
            app_type = "analytical_list_page"
        apps.append({
            "name": f"{name}App",
            "main_entity": name,
            "app_type": app_type,
            "service_module": service_name,
        })

    if complexity in {"enterprise", "full_stack"} and root_entities:
        apps.append({
            "name": "ExecutiveOverview",
            "main_entity": root_entities[0].get("name", ""),
            "app_type": "overview_page",
            "service_module": "AnalyticsService",
        })

    return apps


def _default_quality_gates(complexity: str) -> list[str]:
    gates = [
        "Schema and service consistency validation",
        "Security descriptor and role model validation",
        "Fiori manifest and routing verification",
        "Workspace materialization and artifact manifest generation",
    ]
    if complexity in {"enterprise", "full_stack"}:
        gates.extend([
            "Deployment descriptor completeness for CAP, approuter, and XSUAA",
            "Analytics/reporting artifact presence check",
            "Integration configuration readiness check",
            "Automated test scaffold presence check",
        ])
    if complexity == "full_stack":
        gates.extend([
            "Release readiness report with build gate summary",
            "Operational documentation and extension guide verification",
        ])
    return gates


def _build_architecture_markdown(
    project_name: str,
    blueprint: EnterpriseBlueprint,
    integrations: list[dict],
) -> str:
    lines = [
        f"# Enterprise Solution Blueprint - {project_name}",
        "",
        "## Solution Summary",
        blueprint.get("domain_summary", ""),
        "",
        "## Service Modules",
    ]
    for module in blueprint.get("service_modules", []):
        lines.append(
            f"- **{module['name']}** ({module['exposure_type']}): {module['purpose']} | Entities: {', '.join(module['entities'])}"
        )

    lines.extend([
        "",
        "## UI Applications",
    ])
    for app in blueprint.get("ui_apps", []):
        lines.append(
            f"- **{app['name']}**: {app['app_type']} for `{app['main_entity']}` via `{app['service_module']}`"
        )

    lines.extend([
        "",
        "## Delivery Scope",
    ])
    for item in blueprint.get("delivery_scope", []):
        lines.append(f"- {item}")

    lines.extend([
        "",
        "## Quality Gates",
    ])
    for gate in blueprint.get("quality_gates", []):
        lines.append(f"- {gate}")

    if integrations:
        lines.extend([
            "",
            "## Integrations",
        ])
        for integration in integrations:
            lines.append(
                f"- **{integration.get('name', integration.get('id', 'Integration'))}** ({integration.get('system', 'External')}): destination-based integration"
            )

    lines.extend([
        "",
        "## Architecture Decisions",
    ])
    for decision in blueprint.get("architecture_decisions", []):
        lines.append(f"- {decision}")

    return "\n".join(lines)


@with_timeout(timeout_seconds=60)  # 1 minute for deterministic blueprint generation
async def enterprise_architecture_agent(state: BuilderState) -> dict[str, Any]:
    """
    Create an enterprise architecture blueprint for downstream generation.
    
    Returns partial state dict with only changed keys.
    """
    agent_name = "enterprise_architecture"
    logger.info(f"Starting {agent_name} Agent")

    started_at = datetime.utcnow().isoformat()
    
    # =========================================================================
    # Check retry count and fail if max retries exhausted
    # =========================================================================
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

    log_progress(state, "Building enterprise solution blueprint...")

    try:
        entities = state.get("entities", [])
        relationships = state.get("relationships", [])
        integrations = state.get("integrations", [])
        complexity = state.get("complexity_level", "standard")
        project_name = state.get("project_name", "App")

        root_entities = [
            entity for entity in entities if not _is_composition_child(entity.get("name", ""), relationships)
        ] or entities
        service_modules = _build_service_modules(entities, relationships, integrations)
        ui_apps = _build_ui_apps(root_entities, service_modules, complexity)
        quality_gates = _default_quality_gates(complexity)

        blueprint: EnterpriseBlueprint = {
            "solution_type": "enterprise_cap_fiori",
            "domain_summary": (
                f"{project_name} will be generated as a layered SAP CAP solution with "
                f"{len(service_modules)} service module(s), {len(ui_apps)} UI app(s), "
                "strong security defaults, deployment assets, and delivery documentation."
            ),
            "service_modules": service_modules,
            "ui_apps": ui_apps,
            "quality_gates": quality_gates,
            "deployment_modules": [
                "srv",
                "db",
                "approuter",
                "xsuaa",
                "hana" if state.get("database_type") == "hana" else "sqlite",
            ],
            "architecture_decisions": [
                "Use modular CAP services rather than a single monolithic service definition.",
                "Generate separate Fiori apps for root business capabilities at enterprise scale.",
                "Preserve clean-core extensibility through extension artifacts and hook registries.",
                "Materialize the generated project to disk for downstream build and verification steps.",
            ],
            "delivery_scope": [
                "Domain model, services, handlers, UI apps, security, deployment, testing, and documentation",
                "On-disk generated workspace with manifest and verification report",
                "Release-readiness checks before download packaging",
            ],
        }

        architecture_md = _build_architecture_markdown(project_name, blueprint, integrations)
        blueprint_json = json.dumps(blueprint, indent=2)
        generated_files: list[GeneratedFile] = [
            {
                "path": "docs/ARCHITECTURE.md",
                "content": architecture_md,
                "file_type": "md",
            },
            {
                "path": "docs/SOLUTION_BLUEPRINT.json",
                "content": blueprint_json,
                "file_type": "json",
            },
        ]

        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1

        log_progress(state, f"Enterprise blueprint ready with {len(service_modules)} service module(s).")
        
        # Return only changed keys
        return {
            # Agent outputs
            "artifacts_docs": generated_files,
            "enterprise_blueprint": blueprint,
            "architecture_context_md": architecture_md,
            "service_modules": service_modules,
            "ui_apps": ui_apps,
            "quality_gates": quality_gates,
            
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with exception: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": str(e),
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": True,
            
            # Validation errors
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
