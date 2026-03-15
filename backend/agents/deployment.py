"""
Agent 8: Deployment Configuration Agent (LLM-Driven)

Generates deployment configurations including mta.yaml, package.json,
CI/CD pipelines, and BTP deployment artifacts.

FULLY LLM-DRIVEN with inter-agent context.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.llm_utils import (
    generate_with_retry,
    get_full_context,
)
from backend.agents.knowledge_loader import get_security_knowledge
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    DeploymentTarget,
    ValidationError,
)
from backend.agents.progress import log_progress
from backend.agents.resilience import with_timeout

logger = logging.getLogger(__name__)


DEPLOYMENT_SYSTEM_PROMPT = """You are an SAP BTP deployment engineer.
Generate production-ready deployment configurations.

STRICT RULES:
1. mta.yaml: Standard SAP MTA Build Tool descriptor
   - MUST include `srv` and `db` (hdi-deployer) modules.
   - MUST include `hana` service (org.cloudfoundry.managed-service, hdi-shared).
   - MUST include `xsuaa` service (org.cloudfoundry.managed-service, application).
   - Use proper SAP buildpacks (nodejs_buildpack).
   - Generate approuter module (managed-approuter or standalone) binding to xsuaa and srv.
2. package.json: SAP CAP project dependencies
   - MUST include `@sap/cds`, `@sap/cds-dk`, `@sap/cds-hana`, `hdb`.
   - Correct scripts: `start`, `build`, `deploy`.
   - MUST contain an `auth` section in `cds.requires` matching XSUAA.
   - MUST contain a `db` section in `cds.requires` matching HANA.
3. .npmrc: SAP NPM registry configuration
4. .env.sample: Environment variable template
5. README.md: Project-specific getting started guide
6. .pipeline/config.yml: Project Piper CI/CD configuration.

OUTPUT FORMAT:
{
    "mta_yaml": "... mta.yaml content ...",
    "package_json": "... package.json content ...",
    "npmrc": "... .npmrc content ...",
    "env_sample": "... .env.sample content ...",
    "readme_md": "... README.md content ...",
    "gitignore": "... .gitignore content ...",
    "eslintrc_json": "... .eslintrc.json ...",
    "prettierrc_json": "... .prettierrc.json ...",
    "piper_config_yml": "... .pipeline/config.yml ..."
}
Return ONLY valid JSON."""


DEPLOYMENT_PROMPT = """Generate deployment configs for this SAP CAP application.

Project: {project_name}
Namespace: {namespace}
Deployment Target: {deployment_target}

{context}

ENTITIES:
{entities_json}

Generate:
1. mta.yaml — Full MTA descriptor with all modules/resources
2. package.json — Project dependencies and scripts
3. .npmrc — SAP NPM registry
4. .env.sample — Environment template
5. README.md — Project-specific setup guide
6. .gitignore — Proper ignore patterns for CAP
7. .eslintrc.json — ESLint config
8. .prettierrc.json — Prettier config

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=180)
async def deployment_agent(state: BuilderState) -> dict[str, Any]:
    """Deployment Configuration Agent (LLM-Driven)"""
    agent_name = "deployment"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Deployment Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "deployment"
    state["updated_at"] = now
    state["current_logs"] = []
    log_progress(state, "Starting deployment phase...")
    
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

        project_name = state.get("project_name", "App")
        namespace = state.get("project_namespace", "com.company.app")
        deployment_target = state.get("deployment_target", DeploymentTarget.CF.value)
        entities = state.get("entities", [])
        context = get_full_context(state)
        knowledge = get_security_knowledge()  # security_and_deployment reference

        prompt = DEPLOYMENT_PROMPT.format(
        project_name=project_name,
        namespace=namespace,
        deployment_target=deployment_target,
        context=context or "(no prior context)",
        entities_json=json.dumps(entities, indent=2),
        )

        # Inject knowledge into prompt
        prompt = f"{knowledge}\n\n{prompt}"

        log_progress(state, "Calling LLM for deployment configuration...")

        result = await generate_with_retry(
        prompt=prompt,
        system_prompt=DEPLOYMENT_SYSTEM_PROMPT,
        state=state,
        required_keys=["package_json"],
        max_retries=3,
        agent_name="deployment",
        )

        if result:
            file_map = {
                "mta_yaml": ("mta.yaml", "yaml"),
                "package_json": ("package.json", "json"),
                "npmrc": (".npmrc", "config"),
                "env_sample": (".env.sample", "config"),
                "readme_md": ("README.md", "markdown"),
                "gitignore": (".gitignore", "config"),
                "eslintrc_json": (".eslintrc.json", "json"),
                "prettierrc_json": (".prettierrc.json", "json"),
                "piper_config_yml": (".pipeline/config.yml", "yaml"),
            }
            for key, (path, file_type) in file_map.items():
                content = result.get(key, "")
                if content:
                    if key == "package_json" and state.get("integrations_cd_requires"):
                        try:
                            pkg = json.loads(content)
                            if "cds" not in pkg:
                                pkg["cds"] = {}
                            if "requires" not in pkg["cds"]:
                                pkg["cds"]["requires"] = {}
                            pkg["cds"]["requires"].update(state["integrations_cd_requires"])
                            content = json.dumps(pkg, indent=2)
                        except Exception as e:
                            logger.warning(f"Failed to inject integrations into package.json: {e}")
                    generated_files.append({"path": path, "content": content, "file_type": file_type})

            log_progress(state, f"✅ Generated {len(generated_files)} deployment files.")
        else:
            log_progress(state, "⚠️ LLM failed. Generating minimal deployment config.")
            generated_files.extend(_minimal_deployment(project_name, namespace))
            errors.append({
                "agent": "deployment",
                "code": "LLM_FAILED",
                "message": "LLM deployment generation failed.",
                "field": None,
                "severity": "warning",
            })

        existing = state.get("artifacts_deployment", [])
        state["artifacts_deployment"] = existing + generated_files
        state["validation_errors"] = state.get("validation_errors", []) + errors
        state["needs_correction"] = False

        state["agent_history"] = state.get("agent_history", []) + [{
            "agent_name": "deployment",
            "status": "completed",
            "started_at": now,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_ms": None,
            "error": None,
            "logs": state.get("current_logs", []),
        }]

        log_progress(state, f"Deployment complete. Generated {len(generated_files)} files.")
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


def _minimal_deployment(project_name, namespace):
    """Minimal deployment files."""
    pkg = json.dumps({
        "name": project_name.lower().replace(" ", "-"),
        "version": "1.0.0",
        "description": project_name,
        "dependencies": {
            "@sap/cds": "^8",
            "express": "^4",
        },
        "devDependencies": {
            "@sap/cds-dk": "^8",
        },
        "scripts": {
            "start": "cds-serve",
            "build": "cds build --production",
        },
    }, indent=2)

    gitignore = "node_modules/\ndefault-*.json\ngen/\n*.mtar\n.env\n"

    return [
        {"path": "package.json", "content": pkg, "file_type": "json"},
        {"path": ".gitignore", "content": gitignore, "file_type": "config"},
    ]
