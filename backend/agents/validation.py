"""
Agent 9: Validation & Compliance Agent (Self-Healing)

Validates all generated artifacts against SAP best practices.
When errors are found, attributes them to the responsible agent and generates
correction prompts so the graph can route back for self-healing.

Uses LLM for holistic validation + rule-based structural checks.
"""

import logging
import json
import re
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.llm_utils import generate_with_retry, parse_llm_json
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
    GenerationStatus,
)
from backend.agents.progress import log_progress
from backend.rag.rule_extractor import check_all_rules, get_all_rules

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

VALIDATION_SYSTEM_PROMPT = """You are an expert SAP CAP code reviewer and quality assurance engineer.
Your task is to validate generated SAP CAP artifacts for correctness, consistency, and best practices.

VALIDATION CRITERIA:
1. CDS Syntax: proper namespace, entity definitions, type references, association syntax
2. Service Layer: projections reference correct entities, annotations are well-formed
3. JavaScript Handlers: proper cds.service.impl pattern, correct event handler registration
4. manifest.json: valid Fiori Elements routing, correct data source URIs
5. xs-security.json: proper scope naming, role template references
6. mta.yaml: correct module types, resource bindings, build parameters
7. Cross-file consistency: entity names match across schema, service, and annotations
8. SAP best practices: draft handling, error handling, authorization patterns

ATTRIBUTION: For each issue, identify which agent is responsible:
- "data_modeling" — schema.cds, common.cds, sample data issues
- "service_exposure" — service.cds, annotations.cds issues
- "business_logic" — service.js, handler code issues
- "fiori_ui" — manifest.json, Component.js, i18n issues
- "security" — xs-security.json, auth annotations issues
- "deployment" — mta.yaml, package.json issues

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "validation_results": [
    {
      "file": "path/to/file",
      "severity": "error|warning|info",
      "code": "VALIDATION_CODE",
      "message": "Human-readable description of the issue",
      "responsible_agent": "agent_name",
      "fix_hint": "Brief suggestion on how to fix this"
    }
  ],
  "overall_score": 85,
  "summary": "Brief overall assessment"
}

Return ONLY the JSON object."""


VALIDATION_PROMPT = """Validate ALL the following generated SAP CAP artifacts for correctness, consistency, and best practices.

Project Name: {project_name}
Project Namespace: {namespace}

Generated Files:
{files_content}

Check for:
1. CDS syntax errors (missing semicolons, invalid types, broken references)
2. Cross-file consistency (entity names match between schema.cds, service.cds, annotations)
3. manifest.json structure (valid routing, correct service paths)
4. JavaScript handler correctness (proper cds patterns, valid entity references)
5. xs-security.json validity (proper scope/role structure)
6. mta.yaml completeness (all required modules and resources)
7. SAP Fiori best practices compliance
8. Missing files or configurations
9. Potential runtime errors

IMPORTANT: For each issue, specify which agent is responsible and a fix hint.
Be thorough but practical. Focus on issues that would cause runtime failures or deployment errors.

Respond with ONLY valid JSON."""


CORRECTION_PROMPT_TEMPLATE = """The validation agent found the following issues in your generated code.
Please fix these issues and regenerate the output.

ISSUES FOUND:
{issues}

PREVIOUSLY GENERATED CODE:
{previous_output}

FIX HINTS:
{fix_hints}

Regenerate the corrected output. Respond with ONLY valid JSON in the same format as before."""


# =============================================================================
# Rule-Based Validation
# =============================================================================

def validate_cds_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate CDS file syntax."""
    errors = []
    lines = content.split("\n")

    # Brace matching
    brace_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        brace_count += stripped.count("{") - stripped.count("}")

    if brace_count != 0:
        errors.append({
            "agent": "validation", "code": "CDS_BRACE_MISMATCH",
            "message": f"{filepath}: Mismatched braces (balance: {brace_count})",
            "field": filepath, "severity": "error",
            "responsible_agent": _infer_agent(filepath),
        })

    # Must have namespace or using or annotate
    if "namespace" not in content and "using" not in content and "annotate" not in content:
        errors.append({
            "agent": "validation", "code": "CDS_MISSING_HEADER",
            "message": f"{filepath}: Missing namespace or using statement",
            "field": filepath, "severity": "warning",
            "responsible_agent": _infer_agent(filepath),
        })

    return errors


def validate_json_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate JSON file syntax."""
    errors = []
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            errors.append({
                "agent": "validation", "code": "JSON_NOT_OBJECT",
                "message": f"{filepath}: Root must be an object",
                "field": filepath, "severity": "error",
                "responsible_agent": _infer_agent(filepath),
            })
    except json.JSONDecodeError as e:
        errors.append({
            "agent": "validation", "code": "JSON_SYNTAX_ERROR",
            "message": f"{filepath}: Invalid JSON - {str(e)}",
            "field": filepath, "severity": "error",
            "responsible_agent": _infer_agent(filepath),
        })
    return errors


def validate_javascript_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate JavaScript file syntax."""
    errors = []
    if "service" in filepath.lower() and "module.exports" not in content and "export" not in content:
        errors.append({
            "agent": "validation", "code": "JS_NO_EXPORTS",
            "message": f"{filepath}: No module exports found",
            "field": filepath, "severity": "warning",
            "responsible_agent": "business_logic",
        })
    return errors


def validate_manifest_json(content: str, filepath: str) -> list[ValidationError]:
    """Validate manifest.json structure."""
    errors = []
    try:
        manifest = json.loads(content)
        if "sap.app" not in manifest:
            errors.append({
                "agent": "validation", "code": "MANIFEST_MISSING_SAP_APP",
                "message": f"{filepath}: Missing sap.app section",
                "field": filepath, "severity": "error",
                "responsible_agent": "fiori_ui",
            })
        if "sap.ui5" not in manifest:
            errors.append({
                "agent": "validation", "code": "MANIFEST_MISSING_SAP_UI5",
                "message": f"{filepath}: Missing sap.ui5 section",
                "field": filepath, "severity": "error",
                "responsible_agent": "fiori_ui",
            })
        if manifest.get("sap.app", {}).get("dataSources") is None:
            errors.append({
                "agent": "validation", "code": "MANIFEST_NO_DATASOURCE",
                "message": f"{filepath}: No data sources configured",
                "field": filepath, "severity": "error",
                "responsible_agent": "fiori_ui",
            })
    except json.JSONDecodeError:
        pass
    return errors


def validate_xs_security(content: str, filepath: str) -> list[ValidationError]:
    """Validate xs-security.json."""
    errors = []
    try:
        xs = json.loads(content)
        if "xsappname" not in xs:
            errors.append({
                "agent": "validation", "code": "XS_NO_APPNAME",
                "message": f"{filepath}: Missing xsappname",
                "field": filepath, "severity": "error",
                "responsible_agent": "security",
            })
        if "scopes" not in xs or not xs["scopes"]:
            errors.append({
                "agent": "validation", "code": "XS_NO_SCOPES",
                "message": f"{filepath}: No scopes defined",
                "field": filepath, "severity": "warning",
                "responsible_agent": "security",
            })
    except json.JSONDecodeError:
        pass
    return errors


def validate_cross_file_consistency(state: BuilderState) -> list[ValidationError]:
    """
    Validate entity name consistency across schema, service, and annotations.
    """
    errors = []
    schema = state.get("generated_schema_cds", "")
    service = state.get("generated_service_cds", "")
    annotations = state.get("generated_annotations_cds", "")

    # Extract entity names from schema
    schema_entities = set(re.findall(r"entity\s+(\w+)\s*:", schema))

    # Check service projections reference valid entities
    if schema_entities and service:
        service_refs = set(re.findall(r"projection on db\.(\w+)", service))
        missing_in_schema = service_refs - schema_entities
        for name in missing_in_schema:
            errors.append({
                "agent": "validation", "code": "CROSS_REF_MISSING_ENTITY",
                "message": f"service.cds references entity '{name}' not found in schema.cds",
                "field": "srv/service.cds", "severity": "error",
                "responsible_agent": "service_exposure",
            })

    # Check annotations reference valid service entities
    if service and annotations:
        annotated = set(re.findall(r"annotate\s+\w+\.(\w+)", annotations))
        service_entities = set(re.findall(r"entity\s+(\w+)\s+as", service))
        missing_in_service = annotated - service_entities
        for name in missing_in_service:
            errors.append({
                "agent": "validation", "code": "CROSS_REF_ANNOTATION_MISMATCH",
                "message": f"annotations.cds annotates '{name}' not found in service.cds",
                "field": "srv/annotations.cds", "severity": "warning",
                "responsible_agent": "service_exposure",
            })

    return errors


def validate_artifact(artifact: GeneratedFile) -> list[ValidationError]:
    """Validate a single artifact file."""
    path = artifact.get("path", "")
    content = artifact.get("content", "")
    file_type = artifact.get("file_type", "")

    if not content or not content.strip():
        return [{"agent": "validation", "code": "EMPTY_FILE", "message": f"{path}: File is empty",
                 "field": path, "severity": "error", "responsible_agent": _infer_agent(path)}]

    if file_type == "cds":
        return validate_cds_syntax(content, path)
    elif file_type == "json":
        errors = validate_json_syntax(content, path)
        if "manifest" in path:
            errors.extend(validate_manifest_json(content, path))
        elif "xs-security" in path:
            errors.extend(validate_xs_security(content, path))
        return errors
    elif file_type in ["js", "javascript"]:
        return validate_javascript_syntax(content, path)

    return []


def _infer_agent(filepath: str) -> str:
    """Infer which agent is responsible for a file based on its path."""
    path_lower = filepath.lower()
    if "db/" in path_lower or "schema" in path_lower or "common" in path_lower:
        return "data_modeling"
    elif "annotations" in path_lower:
        return "service_exposure"
    elif "service.cds" in path_lower:
        return "service_exposure"
    elif "service.js" in path_lower or "handler" in path_lower or "lib/" in path_lower:
        return "business_logic"
    elif "manifest" in path_lower or "component" in path_lower or "i18n" in path_lower or "app/" in path_lower:
        return "fiori_ui"
    elif "xs-security" in path_lower or "auth" in path_lower:
        return "security"
    elif "mta" in path_lower or "package.json" in path_lower or ".npmrc" in path_lower:
        return "deployment"
    elif "hook" in path_lower or "extension" in path_lower:
        return "extension"
    return "unknown"


def generate_compliance_report(state: BuilderState, all_errors: list[ValidationError]) -> str:
    """Generate a markdown compliance report."""
    project_name = state.get("project_name", "App")
    error_count = sum(1 for e in all_errors if e.get("severity") == "error")
    warning_count = sum(1 for e in all_errors if e.get("severity") == "warning")
    info_count = sum(1 for e in all_errors if e.get("severity") == "info")

    lines = [
        f"# Compliance Report - {project_name}",
        f"Generated: {datetime.utcnow().isoformat()}",
        "",
        "## Summary",
        f"- **Errors**: {error_count}",
        f"- **Warnings**: {warning_count}",
        f"- **Info**: {info_count}",
        "",
    ]

    if all_errors:
        # Group by responsible agent
        by_agent: dict[str, list] = {}
        for err in all_errors:
            agent = err.get("responsible_agent", err.get("agent", "unknown"))
            by_agent.setdefault(agent, []).append(err)

        lines.append("## Issues by Agent")
        for agent, errs in sorted(by_agent.items()):
            lines.append(f"\n### {agent}")
            for err in errs:
                icon = "❌" if err.get("severity") == "error" else "⚠️" if err.get("severity") == "warning" else "ℹ️"
                lines.append(f"- {icon} **{err.get('code', 'UNKNOWN')}**: {err.get('message', '')}")
    else:
        lines.append("## ✅ All Checks Passed")
        lines.append("No issues found. The generated application meets compliance standards.")

    return "\n".join(lines)


# =============================================================================
# Self-Healing: Build Correction Context
# =============================================================================

def _build_correction_context(state: BuilderState, errors: list[ValidationError]) -> dict[str, dict]:
    """
    For each agent that has validation errors, build a correction prompt.
    Returns: { "agent_name": { "issues": [...], "correction_prompt": "..." } }
    """
    agent_errors: dict[str, list] = {}
    for err in errors:
        if err.get("severity") != "error":
            continue
        agent = err.get("responsible_agent", "unknown")
        if agent == "unknown" or agent == "validation":
            continue
        agent_errors.setdefault(agent, []).append(err)

    corrections = {}

    # Map agents to their output state keys
    agent_output_map = {
        "data_modeling": "generated_schema_cds",
        "service_exposure": "generated_service_cds",
        "business_logic": "generated_handler_js",
        "fiori_ui": "generated_manifest_json",
    }

    for agent_name, errs in agent_errors.items():
        issues_text = "\n".join(f"- [{e['code']}] {e['message']}" for e in errs)
        fix_hints = "\n".join(
            f"- {e.get('fix_hint', 'Review and fix the identified issue')}"
            for e in errs if e.get("fix_hint")
        ) or "Review the identified issues and regenerate corrected output."

        previous_output = state.get(agent_output_map.get(agent_name, ""), "")[:3000]

        correction_prompt = CORRECTION_PROMPT_TEMPLATE.format(
            issues=issues_text,
            previous_output=previous_output,
            fix_hints=fix_hints,
        )

        corrections[agent_name] = {
            "issues": errs,
            "correction_prompt": correction_prompt,
        }

    return corrections


# =============================================================================
# Main Agent Function
# =============================================================================

from backend.agents.resilience import with_timeout


@with_timeout(timeout_seconds=180)  # 3 minutes for LLM validation
async def validation_agent(state: BuilderState) -> dict[str, Any]:
    """
    Validation & Compliance Agent (Self-Healing)

    Uses LLM for holistic validation + rule-based structural checks.
    When critical errors are found, builds correction context and sets
    needs_correction to route back through the graph.
    
    ARCHITECTURE IMPROVEMENTS (2026-03-15):
    - Added timeout wrapper
    - Proper retry counter increment
    - Returns partial state
    - Records agent_history
    - Handles exceptions properly
    """
    agent_name = "validation"
    logger.info(f"Starting {agent_name} Agent (Self-Healing)")
    
    started_at = datetime.utcnow().isoformat()
    all_errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
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

    log_progress(state, "Starting validation phase...")

    try:
        # Collect all artifacts
        all_artifacts = []
        for key in["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_security",
                     "artifacts_ext", "artifacts_deploy", "artifacts_deployment", "artifacts_docs"]:
            all_artifacts.extend(state.get(key, []))

        if not all_artifacts:
            log_progress(state, "Warning: No artifacts found to validate.")

        project_name = state.get("project_name", "App")
        namespace = state.get("project_namespace", "com.company.app")

        # ======================================================================
        # LLM-driven validation
        # ======================================================================
        llm_success = False
        try:
            files_summary_parts = []
            for artifact in all_artifacts:
                path = artifact.get("path", "unknown")
                content = artifact.get("content", "")
                truncated = content[:3000] if len(content) > 3000 else content
                files_summary_parts.append(f"### {path}\n```\n{truncated}\n```")

            files_content = "\n\n".join(files_summary_parts)

            prompt = VALIDATION_PROMPT.format(
                project_name=project_name,
                namespace=namespace,
                files_content=files_content,
            )

            log_progress(state, f"Calling LLM to validate {len(all_artifacts)} artifacts...")

            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=VALIDATION_SYSTEM_PROMPT,
                state=state,
                required_keys=["validation_results"],
                max_retries=2,
                agent_name="validation",
            )

            if result and "validation_results" in result:
                for r in result["validation_results"]:
                    all_errors.append({
                        "agent": "validation",
                        "code": r.get("code", "LLM_VALIDATION"),
                        "message": r.get("message", ""),
                        "field": r.get("file"),
                        "severity": r.get("severity", "warning"),
                        "responsible_agent": r.get("responsible_agent", _infer_agent(r.get("file", ""))),
                        "fix_hint": r.get("fix_hint", ""),
                    })

                score = result.get("overall_score", 0)
                log_progress(state, f"LLM validation complete. Score: {score}/100.")
                llm_success = True
            else:
                log_progress(state, "Could not parse LLM validation response. Using rules only.")

        except Exception as e:
            logger.warning(f"LLM validation failed: {e}")
            log_progress(state, f"LLM validation failed ({str(e)[:80]}). Using rules only.")

        # ======================================================================
        # Deterministic Rule Checklist (NEW - from RAG module)
        # ======================================================================
        log_progress(state, "Running deterministic rule checklist...")
        rule_results = check_all_rules(state)
        
        # Store rule results in state
        validation_rules_applied = [r["rule"] for r in rule_results]
        
        # Convert failed rules to validation errors
        for rule_result in rule_results:
            if not rule_result["passed"]:
                all_errors.append({
                    "agent": "validation",
                    "code": rule_result["rule"],
                    "message": f"{rule_result['description']} - {rule_result['evidence']}",
                    "field": rule_result["category"],
                    "severity": "error",
                    "responsible_agent": rule_result["category"],
                })
        
        failed_rules = [r for r in rule_results if not r["passed"]]
        passed_rules = [r for r in rule_results if r["passed"]]
        log_progress(state, f"Rule checklist: {len(passed_rules)}/{len(rule_results)} rules passed")
        
        # ======================================================================
        # Rule-based validation (always runs)
        # ======================================================================
        log_progress(state, "Running rule-based validation checks...")
        for artifact in all_artifacts:
            try:
                rule_errors = validate_artifact(artifact)
                all_errors.extend(rule_errors)
            except Exception as e:
                logger.warning(f"Validation error for {artifact.get('path')}: {e}")

        # ======================================================================
        # Cross-file consistency check
        # ======================================================================
        cross_errors = validate_cross_file_consistency(state)
        all_errors.extend(cross_errors)
        if cross_errors:
            log_progress(state, f"Cross-file consistency: {len(cross_errors)} issue(s) found.")

        # ======================================================================
        # Self-healing: determine if correction is needed
        # ======================================================================
        error_count = sum(1 for e in all_errors if e.get("severity") == "error")
        warning_count = sum(1 for e in all_errors if e.get("severity") == "warning")

        validation_retry_count = state.get("validation_retry_count", 0)
        max_validation_retries = 5  # Maximum self-healing loops

        needs_correction = False
        correction_agent = None
        correction_context = None
        validation_retry_count_new = validation_retry_count

        if error_count > 0 and validation_retry_count < max_validation_retries:
            corrections = _build_correction_context(state, all_errors)
            if corrections:
                # Find the first agent that needs correction
                responsible_agents = list(corrections.keys())
                primary_agent = responsible_agents[0]

                needs_correction = True
                correction_agent = primary_agent
                correction_context = corrections[primary_agent]
                validation_retry_count_new = validation_retry_count + 1

                log_progress(state, f"🔁 Self-healing: routing back to '{primary_agent}' for correction (attempt {validation_retry_count + 1}/{max_validation_retries}).")
                logger.info(f"Self-healing loop: routing to {primary_agent}")
        else:
            if validation_retry_count >= max_validation_retries and error_count > 0:
                log_progress(state, f"⚠️ Max self-healing retries ({max_validation_retries}) reached. {error_count} errors remain.")

        # ======================================================================
        # Generate compliance report
        # ======================================================================
        report = generate_compliance_report(state, all_errors)
        generated_files.append({
            "path": "docs/COMPLIANCE_REPORT.md",
            "content": report,
            "file_type": "md",
        })

        # ======================================================================
        # Prepare return state
        # ======================================================================
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        method = "LLM + rules" if llm_success else "rule-based"
        log_progress(state, f"Validation complete ({method}). Errors: {error_count}, Warnings: {warning_count}")
        
        generation_status = (
            GenerationStatus.COMPLETED.value if error_count == 0
            else GenerationStatus.FAILED.value
        )
        
        # Return only changed keys (not full state copy)
        return {
            # Agent outputs
            "artifacts_docs": generated_files,
            "validation_errors": all_errors,
            "validation_rules_applied": validation_rules_applied,
            "generation_status": generation_status,
            
            # Self-healing
            "needs_correction": needs_correction,
            "correction_agent": correction_agent,
            "correction_context": correction_context,
            "validation_retry_count": validation_retry_count_new,
            
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
