"""
Agent: Project Verification

Runs deterministic readiness checks against the assembled workspace and,
when possible, attempts lightweight CAP tool verification.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from backend.agents.progress import log_progress
from backend.agents.state import BuilderState, GeneratedFile, VerificationCheck

logger = logging.getLogger(__name__)


def _check_file_exists(workspace: Path, relative_path: str, label: str) -> VerificationCheck:
    exists = (workspace / relative_path).exists()
    return {
        "name": label,
        "status": "passed" if exists else "failed",
        "details": relative_path if exists else f"Missing required file: {relative_path}",
    }


def _check_json_file(workspace: Path, relative_path: str, label: str) -> VerificationCheck:
    path = workspace / relative_path
    if not path.exists():
        return {"name": label, "status": "failed", "details": f"Missing {relative_path}"}
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"name": label, "status": "failed", "details": f"Invalid JSON in {relative_path}: {exc}"}
    return {"name": label, "status": "passed", "details": relative_path}


async def _run_optional_command(
    workspace: Path,
    command: list[str],
    label: str,
    timeout_seconds: int = 45,
) -> VerificationCheck:
    executable = shutil.which(command[0])
    if executable is None:
        return {
            "name": label,
            "status": "skipped",
            "details": f"{command[0]} is not available in the runtime environment",
        }

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        output = (stdout or b"").decode("utf-8", errors="replace").strip()
        if process.returncode == 0:
            return {
                "name": label,
                "status": "passed",
                "details": output[:400] or f"{' '.join(command)} completed successfully",
            }
        return {
            "name": label,
            "status": "warning",
            "details": output[:400] or f"{' '.join(command)} exited with code {process.returncode}",
        }
    except asyncio.TimeoutError:
        return {
            "name": label,
            "status": "warning",
            "details": f"{' '.join(command)} timed out after {timeout_seconds}s",
        }
    except Exception as exc:
        return {
            "name": label,
            "status": "warning",
            "details": f"{' '.join(command)} could not be executed: {exc}",
        }


def _build_report(
    project_name: str,
    workspace: Path,
    checks: list[VerificationCheck],
) -> str:
    passed = sum(1 for check in checks if check["status"] == "passed")
    failed = sum(1 for check in checks if check["status"] == "failed")
    warnings = sum(1 for check in checks if check["status"] == "warning")
    skipped = sum(1 for check in checks if check["status"] == "skipped")

    lines = [
        f"# Verification Report - {project_name}",
        "",
        f"Workspace: `{workspace}`",
        f"Generated: {datetime.utcnow().isoformat()}",
        "",
        "## Summary",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Warnings: {warnings}",
        f"- Skipped: {skipped}",
        "",
        "## Checks",
    ]

    for check in checks:
        icon = {
            "passed": "[PASS]",
            "failed": "[FAIL]",
            "warning": "[WARN]",
            "skipped": "[SKIP]",
        }[check["status"]]
        lines.append(f"- {icon} **{check['name']}**: {check['details']}")

    return "\n".join(lines)


async def project_verification_agent(state: BuilderState) -> BuilderState:
    """Run readiness checks against the generated on-disk workspace."""
    logger.info("Starting Project Verification Agent")

    now = datetime.utcnow().isoformat()
    state["current_agent"] = "project_verification"
    state["updated_at"] = now
    state["current_logs"] = []

    workspace_path = state.get("generated_workspace_path")
    if not workspace_path:
        log_progress(state, "Project verification skipped because no workspace was assembled.")
        state["verification_checks"] = [{
            "name": "Workspace Assembly",
            "status": "failed",
            "details": "No generated workspace path available",
        }]
        return state

    workspace = Path(workspace_path)
    log_progress(state, f"Running verification checks in {workspace}...")

    checks: list[VerificationCheck] = [
        _check_file_exists(workspace, "db/schema.cds", "CAP schema present"),
        _check_file_exists(workspace, "srv", "Service folder present"),
        _check_json_file(workspace, "package.json", "package.json is valid JSON"),
        _check_json_file(workspace, "xs-security.json", "xs-security.json is valid JSON"),
        _check_file_exists(workspace, "mta.yaml", "MTA descriptor present"),
        _check_file_exists(workspace, "docs/ARCHITECTURE.md", "Architecture blueprint present"),
        _check_file_exists(workspace, "docs/GENERATION_MANIFEST.json", "Generation manifest present"),
    ]

    manifest_paths = list(workspace.glob("app/**/manifest.json"))
    checks.append({
        "name": "Fiori manifest presence",
        "status": "passed" if manifest_paths else "failed",
        "details": f"Found {len(manifest_paths)} manifest.json file(s)" if manifest_paths else "No Fiori manifest.json found",
    })

    if state.get("draft_enabled", True):
        schema_path = workspace / "srv" / "service.cds"
        detail = "Draft marker skipped because srv/service.cds is missing"
        status = "warning"
        if schema_path.exists():
            content = schema_path.read_text(encoding="utf-8")
            has_draft = "@odata.draft.enabled" in content
            detail = "Draft annotation found in srv/service.cds" if has_draft else "No @odata.draft.enabled annotation found"
            status = "passed" if has_draft else "warning"
        checks.append({
            "name": "Draft support marker",
            "status": status,
            "details": detail,
        })

    checks.append(await _run_optional_command(workspace, ["node", "--version"], "Node runtime availability"))
    checks.append(await _run_optional_command(workspace, ["npm", "--version"], "NPM availability"))

    report = _build_report(state.get("project_name", "App"), workspace, checks)
    report_path = workspace / "docs" / "VERIFICATION_REPORT.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    summary = {
        "passed": sum(1 for check in checks if check["status"] == "passed"),
        "failed": sum(1 for check in checks if check["status"] == "failed"),
        "warnings": sum(1 for check in checks if check["status"] == "warning"),
        "skipped": sum(1 for check in checks if check["status"] == "skipped"),
    }

    state["verification_checks"] = checks
    state["verification_summary"] = summary
    state["artifacts_docs"] = state.get("artifacts_docs", []) + [{
        "path": "docs/VERIFICATION_REPORT.md",
        "content": report,
        "file_type": "md",
    }]
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "project_verification",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Verification complete. Passed={summary['passed']} Failed={summary['failed']}.")
    return state
