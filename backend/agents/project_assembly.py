"""
Agent: Project Assembly

Materializes generated artifacts into a real workspace on disk so the output
can be inspected, built, and validated like an actual CAP/Fiori project.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from backend.agents.progress import log_progress
from backend.agents.state import BuilderState, GeneratedFile
from backend.config import get_settings

logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "sap-cap-project"


def _collect_all_artifacts(state: BuilderState) -> list[GeneratedFile]:
    artifacts_by_path: dict[str, GeneratedFile] = {}
    for key in [
        "artifacts_db",
        "artifacts_srv",
        "artifacts_app",
        "artifacts_deployment",
        "artifacts_docs",
    ]:
        for artifact in state.get(key, []):
            artifacts_by_path[artifact["path"]] = artifact
    return list(artifacts_by_path.values())


def _append_artifact(
    state: BuilderState,
    category: str,
    path: str,
    content: str,
    file_type: str,
) -> None:
    artifact = {"path": path, "content": content, "file_type": file_type}
    state[category] = state.get(category, []) + [artifact]


def _ensure_essential_artifacts(state: BuilderState) -> None:
    project_name = state.get("project_name", "sap-enterprise-app")
    project_slug = _slugify(project_name)
    namespace = state.get("project_namespace", "com.company.app")

    all_paths = {artifact["path"] for artifact in _collect_all_artifacts(state)}

    if "package.json" not in all_paths:
        package_json = json.dumps(
            {
                "name": project_slug,
                "version": "1.0.0",
                "private": True,
                "description": f"Enterprise SAP CAP + Fiori app generated for {project_name}",
                "scripts": {
                    "start": "cds-serve",
                    "watch": "cds watch",
                    "build": "cds build --production",
                    "test": "jest --runInBand",
                },
                "dependencies": {
                    "@sap/cds": "^8",
                    "@sap/xssec": "^4",
                    "express": "^4",
                },
                "devDependencies": {
                    "@sap/cds-dk": "^8",
                    "sqlite3": "^5",
                    "jest": "^29",
                },
                "cds": {
                    "requires": {
                        "db": {"kind": state.get("database_type", "sqlite")},
                        "auth": {"kind": state.get("auth_type", "mock")},
                    }
                },
            },
            indent=2,
        )
        _append_artifact(state, "artifacts_deployment", "package.json", package_json, "json")

    if "mta.yaml" not in all_paths:
        mta_yaml = "\n".join([
            "_schema-version: '3.3.0'",
            f"ID: {project_slug}",
            "version: 1.0.0",
            "modules:",
            "  - name: srv",
            "    type: nodejs",
            "    path: gen/srv",
            "  - name: db-deployer",
            "    type: hdb",
            "    path: gen/db",
            "  - name: approuter",
            "    type: approuter.nodejs",
            "    path: app/router",
            "resources:",
            "  - name: xsuaa",
            "    type: org.cloudfoundry.managed-service",
            "    parameters:",
            "      service: xsuaa",
            "      service-plan: application",
        ])
        _append_artifact(state, "artifacts_deployment", "mta.yaml", mta_yaml, "yaml")

    if "README.md" not in all_paths:
        readme = "\n".join([
            f"# {project_name}",
            "",
            "Generated enterprise SAP CAP + Fiori project.",
            "",
            "## Modules",
            "- Database model under `db/`",
            "- CAP services under `srv/`",
            "- Fiori applications under `app/`",
            "- Security and deployment descriptors at project root",
            "",
            f"Namespace: `{namespace}`",
        ])
        _append_artifact(state, "artifacts_docs", "README.md", readme, "md")

    if "docs/OPERATIONS_RUNBOOK.md" not in all_paths:
        runbook = "\n".join([
            "# Operations Runbook",
            "",
            "## Production Readiness Checklist",
            "- Review destinations and XSUAA bindings",
            "- Validate CAP service build in CI",
            "- Review generated roles and tenant configuration",
            "- Review monitoring, logging, and backup strategy",
        ])
        _append_artifact(state, "artifacts_docs", "docs/OPERATIONS_RUNBOOK.md", runbook, "md")


async def project_assembly_agent(state: BuilderState) -> BuilderState:
    """Write generated artifacts to a real workspace directory."""
    logger.info("Starting Project Assembly Agent")

    now = datetime.utcnow().isoformat()
    settings = get_settings()

    state["current_agent"] = "project_assembly"
    state["updated_at"] = now
    state["current_logs"] = []

    log_progress(state, "Materializing generated project into a real workspace...")

    _ensure_essential_artifacts(state)
    artifacts = _collect_all_artifacts(state)

    session_id = state.get("session_id", "unknown-session")
    project_slug = _slugify(state.get("project_name", "sap-enterprise-app"))
    workspace = (Path(settings.artifacts_path) / "generated" / session_id / project_slug).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    written_files = []
    for artifact in artifacts:
        relative_path = artifact["path"]
        content = artifact.get("content", "")
        target = workspace / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written_files.append(relative_path)

    manifest_path = workspace / "docs" / "GENERATION_MANIFEST.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project_name": state.get("project_name"),
        "session_id": session_id,
        "workspace_path": str(workspace),
        "generated_at": datetime.utcnow().isoformat(),
        "total_files": len(written_files) + 1,
        "files": sorted(written_files + ["docs/GENERATION_MANIFEST.json"]),
        "quality_gates": state.get("quality_gates", []),
        "service_modules": state.get("service_modules", []),
        "ui_apps": state.get("ui_apps", []),
    }
    manifest_content = json.dumps(manifest, indent=2)
    manifest_path.write_text(manifest_content, encoding="utf-8")
    written_files.append("docs/GENERATION_MANIFEST.json")
    state["artifacts_docs"] = state.get("artifacts_docs", []) + [{
        "path": "docs/GENERATION_MANIFEST.json",
        "content": manifest_content,
        "file_type": "json",
    }]

    state["generated_workspace_path"] = str(workspace)
    state["generated_manifest"] = manifest
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "project_assembly",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Project assembled at {workspace} with {len(written_files)} file(s).")
    return state
