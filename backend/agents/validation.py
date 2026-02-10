"""
Agent 9: Validation & Compliance Agent

Validates all generated artifacts against SAP SDKs, best practices,
and production readiness standards.

Uses LLM for holistic validation of generated artifacts with fallback to rule-based checks.
"""

import logging
import json
import re
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
    GenerationStatus,
)

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

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "validation_results": [
    {
      "file": "path/to/file",
      "severity": "error|warning|info",
      "code": "VALIDATION_CODE",
      "message": "Human-readable description of the issue",
      "line": null
    }
  ],
  "overall_score": 85,
  "summary": "Brief overall assessment",
  "recommendations": ["recommendation 1", "recommendation 2"]
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

Be thorough but practical. Focus on issues that would cause runtime failures or deployment errors.

Respond with ONLY valid JSON."""


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
# Rule-Based Validation (Fallback)
# =============================================================================

CDS_KEYWORDS = {
    "namespace", "using", "entity", "type", "service", "aspect",
    "annotate", "extend", "view", "projection", "association",
}

SAP_FIORI_ANNOTATION_PATTERNS = [
    r"@UI\.",
    r"@Common\.",
    r"@Capabilities\.",
    r"@Core\.",
]


def validate_cds_syntax(content: str, filepath: str) -> list[ValidationError]:
    errors = []
    lines = content.split("\n")
    
    brace_count = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        brace_count += stripped.count("{") - stripped.count("}")
    
    if brace_count != 0:
        errors.append({"agent": "validation", "code": "CDS_BRACE_MISMATCH", "message": f"{filepath}: Mismatched braces (balance: {brace_count})", "field": filepath, "severity": "error"})
    
    if "namespace" not in content and "using" not in content and "annotate" not in content:
        errors.append({"agent": "validation", "code": "CDS_MISSING_HEADER", "message": f"{filepath}: Missing namespace or using statement", "field": filepath, "severity": "warning"})
    
    return errors


def validate_json_syntax(content: str, filepath: str) -> list[ValidationError]:
    errors = []
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            errors.append({"agent": "validation", "code": "JSON_NOT_OBJECT", "message": f"{filepath}: Root must be an object", "field": filepath, "severity": "error"})
    except json.JSONDecodeError as e:
        errors.append({"agent": "validation", "code": "JSON_SYNTAX_ERROR", "message": f"{filepath}: Invalid JSON - {str(e)}", "field": filepath, "severity": "error"})
    return errors


def validate_javascript_syntax(content: str, filepath: str) -> list[ValidationError]:
    errors = []
    if "cds" in filepath and "require" not in content and "import" not in content:
        errors.append({"agent": "validation", "code": "JS_NO_IMPORTS", "message": f"{filepath}: No imports found", "field": filepath, "severity": "warning"})
    
    if "service" in filepath.lower() and "module.exports" not in content and "export" not in content:
        errors.append({"agent": "validation", "code": "JS_NO_EXPORTS", "message": f"{filepath}: No module exports found", "field": filepath, "severity": "warning"})
    
    return errors


def validate_manifest_json(content: str, filepath: str) -> list[ValidationError]:
    errors = []
    try:
        manifest = json.loads(content)
        if "sap.app" not in manifest:
            errors.append({"agent": "validation", "code": "MANIFEST_MISSING_SAP_APP", "message": f"{filepath}: Missing sap.app section", "field": filepath, "severity": "error"})
        if "sap.ui5" not in manifest:
            errors.append({"agent": "validation", "code": "MANIFEST_MISSING_SAP_UI5", "message": f"{filepath}: Missing sap.ui5 section", "field": filepath, "severity": "error"})
        if manifest.get("sap.app", {}).get("dataSources") is None:
            errors.append({"agent": "validation", "code": "MANIFEST_NO_DATASOURCE", "message": f"{filepath}: No data sources configured", "field": filepath, "severity": "error"})
    except json.JSONDecodeError:
        pass
    return errors


def validate_xs_security(content: str, filepath: str) -> list[ValidationError]:
    errors = []
    try:
        xs = json.loads(content)
        if "xsappname" not in xs:
            errors.append({"agent": "validation", "code": "XS_NO_APPNAME", "message": f"{filepath}: Missing xsappname", "field": filepath, "severity": "error"})
        if "scopes" not in xs or not xs["scopes"]:
            errors.append({"agent": "validation", "code": "XS_NO_SCOPES", "message": f"{filepath}: No scopes defined", "field": filepath, "severity": "warning"})
    except json.JSONDecodeError:
        pass
    return errors


def validate_artifact(artifact: GeneratedFile) -> list[ValidationError]:
    path = artifact.get("path", "")
    content = artifact.get("content", "")
    file_type = artifact.get("file_type", "")
    
    if not content or not content.strip():
        return [{"agent": "validation", "code": "EMPTY_FILE", "message": f"{path}: File is empty", "field": path, "severity": "error"}]
    
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


def generate_compliance_report(state: BuilderState, all_errors: list[ValidationError]) -> str:
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
        lines.append("## Issues")
        for err in all_errors:
            icon = "❌" if err.get("severity") == "error" else "⚠️" if err.get("severity") == "warning" else "ℹ️"
            lines.append(f"- {icon} **{err.get('code', 'UNKNOWN')}**: {err.get('message', '')}")
    else:
        lines.append("## ✅ All Checks Passed")
        lines.append("No issues found. The generated application meets compliance standards.")
    
    return "\n".join(lines)


# =============================================================================
# Main Agent Function
# =============================================================================

async def validation_agent(state: BuilderState) -> BuilderState:
    """
    Validation & Compliance Agent (LLM-Driven)
    
    Uses LLM for holistic validation of all generated artifacts.
    Falls back to rule-based validation if LLM fails.
    """
    logger.info("Starting Validation Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    all_errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "validation"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting validation phase...")
    
    # Collect all artifacts
    all_artifacts = []
    for key in ["artifacts_db", "artifacts_srv", "artifacts_app", "artifacts_security", "artifacts_ext", "artifacts_deploy"]:
        all_artifacts.extend(state.get(key, []))
    
    if not all_artifacts:
        log_progress(state, "Warning: No artifacts found to validate.")
    
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    provider = state.get("llm_provider")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven validation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        # Build file content summary for LLM (truncate large files)
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
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=VALIDATION_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and "validation_results" in parsed:
            for result in parsed["validation_results"]:
                all_errors.append({
                    "agent": "validation",
                    "code": result.get("code", "LLM_VALIDATION"),
                    "message": result.get("message", ""),
                    "field": result.get("file"),
                    "severity": result.get("severity", "warning"),
                })
            
            summary = parsed.get("summary", "LLM validation complete")
            score = parsed.get("overall_score", 0)
            log_progress(state, f"LLM validation complete. Score: {score}/100. {summary}")
            llm_success = True
        else:
            log_progress(state, "Could not parse LLM validation response. Falling back to rules.")
    
    except Exception as e:
        logger.warning(f"LLM validation failed: {e}")
        log_progress(state, f"LLM validation failed ({str(e)[:80]}). Falling back to rule-based.")
    
    # ==========================================================================
    # Always run rule-based validation (complements LLM or serves as fallback)
    # ==========================================================================
    log_progress(state, "Running rule-based validation checks...")
    for artifact in all_artifacts:
        try:
            rule_errors = validate_artifact(artifact)
            all_errors.extend(rule_errors)
        except Exception as e:
            logger.warning(f"Validation error for {artifact.get('path')}: {e}")
    
    # ==========================================================================
    # Generate compliance report
    # ==========================================================================
    report = generate_compliance_report(state, all_errors)
    generated_files.append({
        "path": "docs/COMPLIANCE_REPORT.md",
        "content": report,
        "file_type": "md",
    })
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    error_count = sum(1 for e in all_errors if e.get("severity") == "error")
    warning_count = sum(1 for e in all_errors if e.get("severity") == "warning")
    
    state["artifacts_docs"] = state.get("artifacts_docs", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + all_errors
    state["generation_status"] = GenerationStatus.COMPLETED.value if error_count == 0 else GenerationStatus.FAILED.value
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "validation",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM + rules" if llm_success else "rule-based"
    log_progress(state, f"Validation complete ({generation_method}). Errors: {error_count}, Warnings: {warning_count}")
    logger.info(f"Validation Agent completed via {generation_method}. {error_count} errors, {warning_count} warnings.")
    
    return state
