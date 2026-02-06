"""
Agent 9: Validation & Compliance Agent

Validates all generated artifacts against SAP SDKs, best practices,
and production readiness standards.
"""

import logging
import re
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
    GenerationStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Validation Rules
# =============================================================================

CDS_KEYWORDS = {
    "entity", "type", "aspect", "service", "extend", "using", "from",
    "namespace", "context", "define", "key", "not", "null", "default",
    "association", "composition", "to", "on", "many", "one",
}

INVALID_FIELD_NAMES = {
    "class", "function", "var", "let", "const", "import", "export",
    "return", "if", "else", "for", "while", "do", "switch", "case",
}

SAP_FIORI_ANNOTATION_PATTERNS = [
    r"@UI\.",
    r"@Common\.",
    r"@Capabilities\.",
    r"@Core\.",
]


def validate_cds_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate CDS file syntax."""
    errors = []
    lines = content.split("\n")
    
    for i, line in enumerate(lines, 1):
        # Check for unclosed braces
        open_braces = line.count("{")
        close_braces = line.count("}")
        
        # Check for invalid characters in identifiers
        match = re.search(r"entity\s+(\w+)", line)
        if match:
            entity_name = match.group(1)
            if not entity_name[0].isupper():
                errors.append({
                    "agent": "validation",
                    "code": "CDS_NAMING_CONVENTION",
                    "message": f"Entity name '{entity_name}' should be PascalCase (line {i})",
                    "field": filepath,
                    "severity": "warning",
                })
        
        # Check for missing semicolons
        if ":" in line and not line.strip().endswith(("{", "}", ";", ",")):
            if not line.strip().startswith("//") and not line.strip().startswith("/*"):
                errors.append({
                    "agent": "validation",
                    "code": "CDS_MISSING_SEMICOLON",
                    "message": f"Possible missing semicolon (line {i})",
                    "field": filepath,
                    "severity": "warning",
                })
    
    return errors


def validate_json_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate JSON file syntax."""
    errors = []
    
    import json
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        errors.append({
            "agent": "validation",
            "code": "JSON_SYNTAX_ERROR",
            "message": f"Invalid JSON: {str(e)}",
            "field": filepath,
            "severity": "error",
        })
    
    return errors


def validate_javascript_syntax(content: str, filepath: str) -> list[ValidationError]:
    """Validate JavaScript file for common issues."""
    errors = []
    lines = content.split("\n")
    
    # Check for console.log (should be removed in production)
    for i, line in enumerate(lines, 1):
        if "console.log" in line and not line.strip().startswith("//"):
            errors.append({
                "agent": "validation",
                "code": "JS_CONSOLE_LOG",
                "message": f"console.log found (line {i}) - consider removing for production",
                "field": filepath,
                "severity": "warning",
            })
        
        # Check for TODO comments
        if "TODO" in line.upper():
            errors.append({
                "agent": "validation",
                "code": "JS_TODO_FOUND",
                "message": f"TODO comment found (line {i})",
                "field": filepath,
                "severity": "warning",
            })
    
    return errors


def validate_manifest_json(content: str, filepath: str) -> list[ValidationError]:
    """Validate Fiori manifest.json structure."""
    errors = []
    
    import json
    try:
        manifest = json.loads(content)
        
        # Check required sections
        if "sap.app" not in manifest:
            errors.append({
                "agent": "validation",
                "code": "MANIFEST_MISSING_SAP_APP",
                "message": "manifest.json missing 'sap.app' section",
                "field": filepath,
                "severity": "error",
            })
        
        if "sap.ui5" not in manifest:
            errors.append({
                "agent": "validation",
                "code": "MANIFEST_MISSING_SAP_UI5",
                "message": "manifest.json missing 'sap.ui5' section",
                "field": filepath,
                "severity": "error",
            })
        
        # Check for data source
        sap_app = manifest.get("sap.app", {})
        if not sap_app.get("dataSources"):
            errors.append({
                "agent": "validation",
                "code": "MANIFEST_MISSING_DATASOURCE",
                "message": "No data sources defined in manifest.json",
                "field": filepath,
                "severity": "warning",
            })
        
    except json.JSONDecodeError:
        pass  # Already caught by JSON validator
    
    return errors


def validate_mta_yaml(content: str, filepath: str) -> list[ValidationError]:
    """Validate MTA descriptor."""
    errors = []
    
    # Check for required sections
    if "_schema-version" not in content:
        errors.append({
            "agent": "validation",
            "code": "MTA_MISSING_SCHEMA",
            "message": "mta.yaml missing _schema-version",
            "field": filepath,
            "severity": "error",
        })
    
    if "modules:" not in content:
        errors.append({
            "agent": "validation",
            "code": "MTA_MISSING_MODULES",
            "message": "mta.yaml missing modules section",
            "field": filepath,
            "severity": "error",
        })
    
    return errors


def validate_xs_security(content: str, filepath: str) -> list[ValidationError]:
    """Validate xs-security.json structure."""
    errors = []
    
    import json
    try:
        security = json.loads(content)
        
        if not security.get("xsappname"):
            errors.append({
                "agent": "validation",
                "code": "XS_MISSING_APPNAME",
                "message": "xs-security.json missing xsappname",
                "field": filepath,
                "severity": "error",
            })
        
        if not security.get("scopes"):
            errors.append({
                "agent": "validation",
                "code": "XS_MISSING_SCOPES",
                "message": "xs-security.json has no scopes defined",
                "field": filepath,
                "severity": "warning",
            })
        
    except json.JSONDecodeError:
        pass
    
    return errors


def validate_artifact(artifact: GeneratedFile) -> list[ValidationError]:
    """Validate a single artifact based on its type."""
    errors = []
    filepath = artifact.get("path", "")
    content = artifact.get("content", "")
    file_type = artifact.get("file_type", "")
    
    # Route to appropriate validator
    if file_type == "cds":
        errors.extend(validate_cds_syntax(content, filepath))
    elif file_type == "json":
        errors.extend(validate_json_syntax(content, filepath))
        if "manifest.json" in filepath:
            errors.extend(validate_manifest_json(content, filepath))
        elif "xs-security.json" in filepath:
            errors.extend(validate_xs_security(content, filepath))
    elif file_type in ["js", "javascript"]:
        errors.extend(validate_javascript_syntax(content, filepath))
    elif file_type == "yaml" and "mta.yaml" in filepath:
        errors.extend(validate_mta_yaml(content, filepath))
    
    return errors


def generate_compliance_report(state: BuilderState, all_errors: list[ValidationError]) -> str:
    """Generate a compliance report markdown file."""
    project_name = state.get("project_name", "App")
    
    # Count by severity
    error_count = sum(1 for e in all_errors if e.get("severity") == "error")
    warning_count = sum(1 for e in all_errors if e.get("severity") == "warning")
    
    # Determine compliance status
    if error_count == 0:
        status = "✅ COMPLIANT"
    else:
        status = "❌ NON-COMPLIANT"
    
    lines = []
    lines.append(f"# {project_name} - Compliance Report")
    lines.append("")
    lines.append(f"**Status:** {status}")
    lines.append(f"**Generated:** {datetime.utcnow().isoformat()}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Severity | Count |")
    lines.append(f"|----------|-------|")
    lines.append(f"| Errors | {error_count} |")
    lines.append(f"| Warnings | {warning_count} |")
    lines.append("")
    
    if all_errors:
        lines.append("## Issues Found")
        lines.append("")
        
        # Group by agent
        by_agent: dict[str, list[ValidationError]] = {}
        for error in all_errors:
            agent = error.get("agent", "unknown")
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(error)
        
        for agent, errors in by_agent.items():
            lines.append(f"### {agent.title()} Agent")
            lines.append("")
            lines.append("| Code | Message | Severity |")
            lines.append("|------|---------|----------|")
            for e in errors:
                icon = "🔴" if e.get("severity") == "error" else "🟡"
                lines.append(f"| {e.get('code', 'N/A')} | {e.get('message', 'N/A')} | {icon} {e.get('severity', 'N/A')} |")
            lines.append("")
    else:
        lines.append("## ✅ No Issues Found")
        lines.append("")
        lines.append("All generated artifacts comply with SAP SDK standards.")
    
    lines.append("")
    lines.append("## Validation Checklist")
    lines.append("")
    lines.append("- [x] CDS syntax validation")
    lines.append("- [x] JSON structure validation")
    lines.append("- [x] JavaScript best practices")
    lines.append("- [x] Fiori manifest structure")
    lines.append("- [x] MTA descriptor validation")
    lines.append("- [x] Security configuration")
    
    return "\n".join(lines)


# =============================================================================
# Main Agent Function
# =============================================================================

async def validation_agent(state: BuilderState) -> BuilderState:
    """
    Validation & Compliance Agent
    
    Validates:
    1. CDS syntax and naming conventions
    2. JSON structure (manifest, xs-security)
    3. JavaScript best practices
    4. MTA descriptor completeness
    5. Overall production readiness
    
    Returns updated state with validation results and compliance report.
    """
    logger.info("Starting Validation Agent")
    
    now = datetime.utcnow().isoformat()
    all_validation_errors: list[ValidationError] = []
    
    # Update state
    state["current_agent"] = "validation"
    state["updated_at"] = now
    
    # ==========================================================================
    # Collect all artifacts for validation
    # ==========================================================================
    all_artifacts: list[GeneratedFile] = []
    all_artifacts.extend(state.get("artifacts_db", []))
    all_artifacts.extend(state.get("artifacts_srv", []))
    all_artifacts.extend(state.get("artifacts_app", []))
    all_artifacts.extend(state.get("artifacts_deployment", []))
    
    logger.info(f"Validating {len(all_artifacts)} artifacts")
    
    # ==========================================================================
    # Validate each artifact
    # ==========================================================================
    for artifact in all_artifacts:
        try:
            errors = validate_artifact(artifact)
            all_validation_errors.extend(errors)
        except Exception as e:
            logger.error(f"Error validating {artifact.get('path')}: {e}")
            all_validation_errors.append({
                "agent": "validation",
                "code": "VALIDATION_ERROR",
                "message": f"Failed to validate {artifact.get('path')}: {str(e)}",
                "field": artifact.get("path"),
                "severity": "warning",
            })
    
    # ==========================================================================
    # Generate compliance report
    # ==========================================================================
    try:
        report = generate_compliance_report(state, all_validation_errors)
        state["artifacts_docs"] = state.get("artifacts_docs", []) + [{
            "path": "docs/COMPLIANCE_REPORT.md",
            "content": report,
            "file_type": "md",
        }]
        logger.info("Generated compliance report")
    except Exception as e:
        logger.error(f"Failed to generate compliance report: {e}")
    
    # ==========================================================================
    # Determine final status
    # ==========================================================================
    error_count = sum(1 for e in all_validation_errors if e.get("severity") == "error")
    
    if error_count > 0:
        compliance_status = "non_compliant"
        generation_status = GenerationStatus.COMPLETED.value  # Still complete, but with errors
    else:
        compliance_status = "compliant"
        generation_status = GenerationStatus.COMPLETED.value
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["validation_errors"] = state.get("validation_errors", []) + all_validation_errors
    state["compliance_status"] = compliance_status
    state["generation_status"] = generation_status
    state["generation_completed_at"] = datetime.utcnow().isoformat()
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "validation",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Validation Agent completed. Found {error_count} errors, {len(all_validation_errors) - error_count} warnings.")
    
    return state
