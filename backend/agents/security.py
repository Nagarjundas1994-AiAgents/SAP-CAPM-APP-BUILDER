"""
Agent 6: Security & Authorization Agent (LLM-Driven)

Generates SAP BTP security configurations including xs-security.json,
CDS @requires annotations, and mock user configurations.

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
)
from backend.agents.knowledge_loader import get_security_knowledge
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
)
from backend.agents.progress import log_progress
from backend.agents.resilience import with_timeout

logger = logging.getLogger(__name__)


SECURITY_SYSTEM_PROMPT = """You are an SAP BTP security architect.
Generate production-ready security configurations for SAP CAP applications.

STRICT RULES:
1. xs-security.json: XSUAA config with scopes, role templates, role collections
   - MUST define `xsappname`.
   - MUST define scopes with `.Read`, `.Write`, `.Admin` suffixes.
   - MUST define `role-templates` binding those scopes.
   - MUST define `role-collections` (e.g., `Viewer`, `Manager`, `Admin`) containing those templates.
2. CDS auth: @requires and @restrict annotations for fine-grained access
   - Add service-level `@requires: 'authenticated-user'`
   - Define entity-level `@restrict: [{ grant: 'READ', to: 'Viewer' }, ...]`
3. Mock users: CSV for development testing with all roles covered
4. .cdsrc.json: Auth configuration for production and development (mocked).

Use RBAC with at minimum: Viewer (read), Editor (read+write), Admin (all).
For draft-enabled entities, include proper draft authorization.

OUTPUT FORMAT:
{
    "xs_security_json": "... xs-security.json content ...",
    "auth_cds": "... srv/auth.cds ...",
    "auth_annotations_cds": "... srv/auth-annotations.cds ...",
    "mock_users_csv": "... db/data/mock-users.csv ...",
    "cdsrc_json": "... .cdsrc.json ..."
}
Return ONLY valid JSON."""


SECURITY_GENERATION_PROMPT = """Generate security configurations for this SAP CAP application.

Project: {project_name}
Namespace: {namespace}
Auth Type: {auth_type}
XS App Name: {xsappname}

{service_context}

ENTITIES:
{entities_json}

Generate complete security files including XSUAA, CDS auth annotations,
mock users for testing, and .cdsrc.json config.

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=180)
async def security_agent(state: BuilderState) -> dict[str, Any]:
    """Security & Authorization Agent (LLM-Driven)"""
    agent_name = "security"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Security Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "security"
    state["updated_at"] = now
    state["current_logs"] = []
    log_progress(state, "Starting security phase...")
    
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
        entities = state.get("entities", [])
        project_name = state.get("project_name", "App")
        namespace = state.get("project_namespace", "com.company.app")
        auth_type = state.get("auth_type", "mock")
        xsappname = project_name.lower().replace(" ", "-").replace("_", "-")

        service_context = get_service_context(state)
        knowledge = get_security_knowledge()

        prompt = SECURITY_GENERATION_PROMPT.format(
        project_name=project_name,
        namespace=namespace,
        auth_type=auth_type,
        xsappname=xsappname,
        service_context=service_context or "(service CDS not available)",
        entities_json=json.dumps(entities, indent=2),
        )

        # Inject knowledge into prompt
        prompt = f"{knowledge}\n\n{prompt}"

        # Self-Healing: Inject correction context if present
        correction_context = state.get("correction_context")
        if state.get("needs_correction") and state.get("correction_agent") == "security" and correction_context:
            log_progress(state, "Applying self-healing correction context from validation agent...")
            correction_prompt = correction_context.get("correction_prompt", "")
            if correction_prompt:
                prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

        log_progress(state, "Calling LLM for security configuration...")

        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=SECURITY_SYSTEM_PROMPT,
            state=state,
            required_keys=["xs_security_json"],
            max_retries=3,
            agent_name="security",
        )

        if result:
            file_map = {
                "xs_security_json": ("xs-security.json", "json"),
                "auth_cds": ("srv/auth.cds", "cds"),
                "auth_annotations_cds": ("srv/auth-annotations.cds", "cds"),
                "mock_users_csv": ("db/data/mock-users.csv", "csv"),
                "cdsrc_json": (".cdsrc.json", "json"),
            }
            for key, (path, file_type) in file_map.items():
                content = result.get(key, "")
                if content:
                    generated_files.append({"path": path, "content": content, "file_type": file_type})

            log_progress(state, f"✅ Generated {len(generated_files)} security files.")
        else:
            log_progress(state, "⚠️ LLM failed. Generating minimal security config.")
            generated_files.extend(_minimal_security(xsappname))
            errors.append({
                "agent": "security",
                "code": "LLM_FAILED",
                "message": "LLM security generation failed. Minimal config generated.",
                "field": None,
                "severity": "warning",
            })


        existing = state.get("artifacts_deployment", [])
        state["artifacts_deployment"] = existing + generated_files
        state["validation_errors"] = state.get("validation_errors", []) + errors
        state["needs_correction"] = False

        state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "security",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
        }]

        log_progress(state, f"Security complete. Generated {len(generated_files)} files.")
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
    
        return {
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


        def _minimal_security(xsappname):
            """Minimal security config."""
            xs = json.dumps({
                "xsappname": xsappname,
                "tenant-mode": "dedicated",
                "scopes": [
                    {"name": f"$XSAPPNAME.Read", "description": "Read access"},
                    {"name": f"$XSAPPNAME.Write", "description": "Write access"},
                    {"name": f"$XSAPPNAME.Admin", "description": "Admin access"},
                ],
                "role-templates": [
                    {"name": "Viewer", "scope-references": [f"$XSAPPNAME.Read"]},
                    {"name": "Editor", "scope-references": [f"$XSAPPNAME.Read", f"$XSAPPNAME.Write"]},
                    {"name": "Admin", "scope-references": [f"$XSAPPNAME.Read", f"$XSAPPNAME.Write", f"$XSAPPNAME.Admin"]},
                ],
            }, indent=2)
            return [{"path": "xs-security.json", "content": xs, "file_type": "json"}]

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