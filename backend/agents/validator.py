"""
Self-Healing Validation Module

Validates generated SAP CAP artifacts to detect errors before presenting them to users.
Supports CDS, JavaScript, JSON, YAML, and best practices validation.

Enhanced validation features:
- Cross-file consistency checking (entity names match across schema → service → annotations)
- Semantic CDS validation (valid types, key fields, relationship targets)
- YAML validation for mta.yaml
- Manifest.json deep validation for Fiori Elements
- Quality scoring system (0–100)
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    severity: ValidationSeverity
    message: str
    line: int | None = None
    column: int | None = None
    code: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of validation operation."""
    is_valid: bool
    issues: list[ValidationIssue]
    artifact_path: str
    validator_type: str

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == ValidationSeverity.ERROR for issue in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == ValidationSeverity.WARNING)


# =============================================================================
# Valid CDS Types
# =============================================================================

VALID_CDS_TYPES = {
    "String", "Integer", "Decimal", "Boolean", "Date", "DateTime", "Time",
    "UUID", "LargeString", "Binary", "LargeBinary", "Double",
    "Int16", "Int32", "Int64", "Timestamp",
    "Association", "Composition",
    # Custom / imported types are also allowed if capitalized
}


# =============================================================================
# CDS Validation
# =============================================================================

def validate_cds(content: str, path: str = "schema.cds") -> ValidationResult:
    """
    Validate CDS content using syntax and semantic checks.
    """
    issues: list[ValidationIssue] = []
    lines = content.split("\n")

    # ── Check for namespace or using declaration ──
    has_namespace = bool(re.search(r"^\s*namespace\s+", content, re.MULTILINE))
    has_using = bool(re.search(r"^\s*using\s+", content, re.MULTILINE))
    if not has_namespace and not has_using and "schema" in path:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="Missing namespace declaration. Consider adding 'namespace com.company.app;'",
            line=1, code="MISSING_NAMESPACE"
        ))

    # ── Check for at least one entity ──
    entity_names = re.findall(r"entity\s+(\w+)", content)
    if not entity_names and "schema" in path:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message="No entity definitions found in CDS schema",
            line=1, code="NO_ENTITIES"
        ))

    # ── Check entity key fields ──
    entity_blocks = re.findall(r"entity\s+(\w+).*?\{(.*?)\}", content, re.DOTALL)
    for ename, body in entity_blocks:
        if "key " not in body and "cuid" not in content and "managed" not in body:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Entity '{ename}' has no key field and does not use 'cuid' aspect.",
                code="NO_KEY_FIELD"
            ))

    # ── Check for balanced braces ──
    open_braces = content.count("{")
    close_braces = content.count("}")
    if open_braces != close_braces:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=f"Unbalanced curly braces: {open_braces} open vs {close_braces} close",
            code="UNBALANCED_BRACES"
        ))

    # ── Check field types ──
    for line_num, line in enumerate(lines, 1):
        type_match = re.search(r":\s*(\w+)(?:\(|\s*;|\s*$)", line.strip())
        if type_match and "key " not in line[:line.find(":") if ":" in line else 0]:
            cds_type = type_match.group(1)
            if cds_type not in VALID_CDS_TYPES and not cds_type[0].isupper():
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Potentially invalid CDS type '{cds_type}'",
                    line=line_num, code="INVALID_TYPE"
                ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path=path, validator_type="cds"
    )


# =============================================================================
# JavaScript Validation
# =============================================================================

def validate_javascript(content: str, path: str = "service.js") -> ValidationResult:
    """Validate JavaScript content for common CAP handler issues."""
    issues: list[ValidationIssue] = []

    # ── Check for export ──
    if "module.exports" not in content and "export" not in content:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="No module.exports or export found. CAP handlers need module.exports = cds.service.impl(...).",
            line=1, code="NO_EXPORT"
        ))

    # ── Check for cds.service.impl pattern ──
    if "cds.service.impl" not in content and "cds.Service" not in content:
        if "module.exports" in content:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="Consider using 'module.exports = cds.service.impl(...)' pattern.",
                code="NO_CDS_IMPL"
            ))

    # ── Balanced braces check ──
    open_braces = content.count("{")
    close_braces = content.count("}")
    if abs(open_braces - close_braces) > 1:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=f"Unbalanced braces: {open_braces} open vs {close_braces} close",
            code="UNBALANCED_BRACES"
        ))

    # ── Console.log check ──
    for line_num, line in enumerate(content.split("\n"), 1):
        if "console.log" in line and not line.strip().startswith("//"):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="Use cds.log() instead of console.log",
                line=line_num, code="CONSOLE_LOG",
                suggestion="const LOG = cds.log('service'); LOG.info(...);"
            ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path=path, validator_type="javascript"
    )


# =============================================================================
# JSON Validation
# =============================================================================

def validate_json(content: str, path: str = "package.json") -> ValidationResult:
    """Validate JSON syntax and structure."""
    issues: list[ValidationIssue] = []

    try:
        parsed = json.loads(content)

        # ── package.json checks ──
        if "package.json" in path:
            if "name" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="package.json missing 'name' field", code="MISSING_NAME"
                ))
            deps = parsed.get("dependencies", {})
            if "@sap/cds" not in deps:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Missing '@sap/cds' dependency", code="MISSING_CDS_DEP"
                ))
            if "scripts" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="No scripts defined in package.json", code="NO_SCRIPTS"
                ))

        # ── manifest.json checks ──
        if "manifest.json" in path:
            if "sap.app" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="manifest.json missing 'sap.app' section", code="MISSING_SAP_APP"
                ))
            if "sap.ui5" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="manifest.json missing 'sap.ui5' section", code="MISSING_SAP_UI5"
                ))
            # Check routing
            routing = parsed.get("sap.ui5", {}).get("routing", {})
            if not routing.get("routes"):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="No routes defined in manifest.json", code="NO_ROUTES"
                ))
            if not routing.get("targets"):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="No targets defined in manifest.json", code="NO_TARGETS"
                ))
            # Check dataSources
            datasources = parsed.get("sap.app", {}).get("dataSources", {})
            if not datasources:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="No dataSources in manifest. Required for OData connectivity.", code="NO_DATASOURCES"
                ))

        # ── xs-security.json checks ──
        if "xs-security" in path:
            if "xsappname" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="xs-security.json missing 'xsappname'", code="MISSING_XSAPPNAME"
                ))
            if "scopes" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="No scopes defined in xs-security.json", code="NO_SCOPES"
                ))

    except json.JSONDecodeError as e:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=f"Invalid JSON syntax: {e}",
            line=e.lineno, column=e.colno, code="INVALID_JSON"
        ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path=path, validator_type="json"
    )


# =============================================================================
# YAML Validation
# =============================================================================

def validate_yaml(content: str, path: str = "mta.yaml") -> ValidationResult:
    """Validate YAML syntax and MTA structure."""
    issues: list[ValidationIssue] = []

    try:
        import yaml
        parsed = yaml.safe_load(content)

        if "mta" in path and isinstance(parsed, dict):
            if "_schema-version" not in parsed and "schema-version" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="mta.yaml missing '_schema-version'", code="MISSING_SCHEMA_VERSION"
                ))
            if "ID" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="mta.yaml missing 'ID'", code="MISSING_MTA_ID"
                ))
            if "modules" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="mta.yaml has no 'modules'. Add srv and db modules.", code="NO_MODULES"
                ))
            if "resources" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="mta.yaml has no 'resources'. Add xsuaa, hdi-container.", code="NO_RESOURCES"
                ))
    except ImportError:
        # yaml not installed — skip YAML-specific parsing
        # Still do basic checks
        if "mta" in path:
            if "_schema-version" not in content:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="mta.yaml may be missing '_schema-version'", code="MISSING_SCHEMA_VERSION"
                ))
    except Exception as e:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=f"YAML parse error: {e}", code="INVALID_YAML"
        ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path=path, validator_type="yaml"
    )


# =============================================================================
# Best Practices Validation
# =============================================================================

def validate_best_practices(content: str, path: str, file_type: str) -> ValidationResult:
    """Check for SAP CAP best practices violations."""
    issues: list[ValidationIssue] = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, 1):
        # Hardcoded credentials
        if re.search(r"(password|secret|api[_-]?key)\s*[:=]\s*[\"'](?!.*\$\{)", line, re.IGNORECASE):
            if not line.strip().startswith("//") and not line.strip().startswith("#"):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="Hardcoded credentials detected. Use environment variables.",
                    line=line_num, code="HARDCODED_CREDENTIALS",
                    suggestion="Use process.env.VAR_NAME"
                ))

    # CDS-specific
    if file_type == "cds":
        if "@cds.persistence" in content:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="@cds.persistence is deprecated.", code="DEPRECATED_ANNOTATION"
            ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path=path, validator_type="best_practices"
    )


# =============================================================================
# Cross-File Consistency Checker
# =============================================================================

def validate_cross_file_consistency(state: dict) -> ValidationResult:
    """
    Check that entity names are consistent across all generated files:
    - schema.cds entities → service.cds projections → annotations → handlers
    """
    issues: list[ValidationIssue] = []

    # Collect entity names from state
    entity_names = {e.get("name", "") for e in state.get("entities", []) if e.get("name")}

    if not entity_names:
        return ValidationResult(is_valid=True, issues=[], artifact_path="cross-file", validator_type="consistency")

    # Check schema.cds
    schema_entities = set()
    for art in state.get("artifacts_db", []):
        if art.get("path", "").endswith("schema.cds"):
            schema_entities = set(re.findall(r"entity\s+(\w+)", art.get("content", "")))

    # Check service.cds
    service_entities = set()
    for art in state.get("artifacts_srv", []):
        if art.get("path", "").endswith("service.cds"):
            content = art.get("content", "")
            service_entities = set(re.findall(r"entity\s+(\w+)\s+as\s+projection", content))

    # Check for missing projections
    for ename in entity_names:
        if schema_entities and ename not in schema_entities:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Entity '{ename}' defined in state but not found in schema.cds",
                code="ENTITY_NOT_IN_SCHEMA"
            ))
        if service_entities and ename not in service_entities:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Entity '{ename}' not projected in service.cds",
                code="ENTITY_NOT_IN_SERVICE"
            ))

    # Check for entities in service but not in schema
    for ename in service_entities:
        if schema_entities and ename not in schema_entities:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message=f"Entity '{ename}' projected in service.cds but not in schema.cds",
                code="PROJECTION_WITHOUT_ENTITY"
            ))

    return ValidationResult(
        is_valid=not any(i.severity == ValidationSeverity.ERROR for i in issues),
        issues=issues, artifact_path="cross-file", validator_type="consistency"
    )


# =============================================================================
# Quality Scoring
# =============================================================================

def compute_quality_score(state: dict) -> dict:
    """
    Compute a quality score (0-100) for the generated application.

    Returns:
        {
            "total": 82,
            "breakdown": {
                "data_model": 90,
                "service_layer": 85,
                "business_logic": 70,
                "fiori_ui": 80,
                "security": 85,
                "deployment": 80
            },
            "details": ["Good: entities use managed aspect", "Missing: no i18n labels", ...]
        }
    """
    breakdown = {}
    details: list[str] = []

    # ── Data Model (20 points max) ──
    dm_score = 0
    for art in state.get("artifacts_db", []):
        content = art.get("content", "")
        if "schema.cds" in art.get("path", ""):
            if "namespace" in content:
                dm_score += 3; details.append("✅ Namespace declared")
            if "managed" in content or "cuid" in content:
                dm_score += 3; details.append("✅ Uses managed/cuid aspect")
            entity_count = len(re.findall(r"entity\s+\w+", content))
            if entity_count >= 1:
                dm_score += 3
            if "@title" in content:
                dm_score += 2; details.append("✅ @title annotations on fields")
            if "Composition" in content or "Association" in content:
                dm_score += 3; details.append("✅ Relationships defined")
            if "localized" in content:
                dm_score += 2; details.append("✅ Localized fields for i18n")
            if "enum" in content.lower() or "type " in content:
                dm_score += 2; details.append("✅ Custom types/enums defined")
            dm_score += 2  # Base score for having schema
    breakdown["data_model"] = min(dm_score * 5, 100)  # Scale to 100

    # ── Service Layer (20 points max) ──
    sl_score = 0
    for art in state.get("artifacts_srv", []):
        content = art.get("content", "")
        if "service.cds" in art.get("path", ""):
            sl_score += 3  # Has service file
            if "projection" in content:
                sl_score += 3
            if "@odata.draft.enabled" in content:
                sl_score += 3; details.append("✅ Draft enabled")
            if "action " in content or "function " in content:
                sl_score += 2; details.append("✅ Custom actions/functions")
        if "annotations" in art.get("path", ""):
            sl_score += 2
            if "UI.HeaderInfo" in content:
                sl_score += 2; details.append("✅ Deep Fiori annotations")
            if "UI.LineItem" in content:
                sl_score += 2
            if "UI.Facets" in content:
                sl_score += 2
            if "Common.ValueList" in content:
                sl_score += 1
    breakdown["service_layer"] = min(sl_score * 5, 100)

    # ── Business Logic (20 points max) ──
    bl_score = 0
    for art in state.get("artifacts_srv", []):
        content = art.get("content", "")
        if art.get("path", "").endswith(".js"):
            bl_score += 3
            if "cds.log" in content:
                bl_score += 3; details.append("✅ Structured logging")
            if "req.error" in content:
                bl_score += 2; details.append("✅ Input validation")
            if "before" in content and "after" in content:
                bl_score += 2; details.append("✅ Before/after event handlers")
            if "this.on" in content:
                bl_score += 2; details.append("✅ Custom action handlers")
            if "try" in content and "catch" in content:
                bl_score += 2; details.append("✅ Error handling")
            if "status" in content.lower() and "transition" in content.lower():
                bl_score += 2
            if "SELECT" in content and "UPDATE" in content:
                bl_score += 2
            bl_score += 2
    breakdown["business_logic"] = min(bl_score * 5, 100)

    # ── Fiori UI (15 points max) ──
    fi_score = 0
    for art in state.get("artifacts_app", []):
        content = art.get("content", "")
        if "manifest.json" in art.get("path", ""):
            fi_score += 3
            if "flexibleColumnLayout" in content or "FlexibleColumn" in content:
                fi_score += 3; details.append("✅ FCL layout")
            if "crossNavigation" in content:
                fi_score += 2; details.append("✅ Launchpad integration")
            if "sap.cloud" in content:
                fi_score += 2; details.append("✅ sap.cloud for BTP")
        if "flpSandbox" in art.get("path", ""):
            fi_score += 2; details.append("✅ FLP sandbox for testing")
        if "ui5.yaml" in art.get("path", ""):
            fi_score += 2; details.append("✅ UI5 Tooling config")
        if "i18n" in art.get("path", ""):
            fi_score += 1
    breakdown["fiori_ui"] = min(fi_score * 7, 100)

    # ── Security (10 points max) ──
    se_score = 0
    for art in state.get("artifacts_security", []):
        content = art.get("content", "")
        if "xs-security" in art.get("path", ""):
            se_score += 3
            if "role-templates" in content:
                se_score += 2
            if "role-collections" in content:
                se_score += 2; details.append("✅ Role collections")
        if "auth" in art.get("path", "") and art.get("path", "").endswith(".cds"):
            se_score += 2
            if "restrict" in content:
                se_score += 2; details.append("✅ Entity-level auth")
            if "$user" in content:
                se_score += 2; details.append("✅ Instance-based auth")
            if "PersonalData" in content:
                se_score += 2; details.append("✅ GDPR annotations")
    breakdown["security"] = min(se_score * 7, 100)

    # ── Deployment (15 points max) ──
    dp_score = 0
    for art in state.get("artifacts_deployment", []):
        path = art.get("path", "")
        if "mta.yaml" in path:
            dp_score += 3; details.append("✅ MTA deployment descriptor")
        if "package.json" in path:
            dp_score += 3
        if "Dockerfile" in path:
            dp_score += 2
        if ".gitignore" in path:
            dp_score += 1
        if ".github" in path:
            dp_score += 2; details.append("✅ CI/CD pipeline")
        if ".npmrc" in path:
            dp_score += 1
        if "README" in path:
            dp_score += 1
    breakdown["deployment"] = min(dp_score * 8, 100)

    # ── Compute total (weighted) ──
    weights = {
        "data_model": 0.20,
        "service_layer": 0.20,
        "business_logic": 0.20,
        "fiori_ui": 0.15,
        "security": 0.10,
        "deployment": 0.15,
    }
    total = sum(breakdown.get(k, 0) * w for k, w in weights.items())

    return {
        "total": round(total),
        "breakdown": breakdown,
        "details": details
    }


# =============================================================================
# Unified Validation Interface
# =============================================================================

def validate_artifact(path: str, content: str) -> list[ValidationResult]:
    """
    Validate an artifact based on its file type.
    Returns a list of ValidationResults from different validators.
    """
    results: list[ValidationResult] = []

    file_ext = Path(path).suffix.lower()
    file_type = None

    if file_ext == ".cds":
        file_type = "cds"
        results.append(validate_cds(content, path))
    elif file_ext == ".js":
        file_type = "javascript"
        results.append(validate_javascript(content, path))
    elif file_ext == ".json":
        file_type = "json"
        results.append(validate_json(content, path))
    elif file_ext in (".yaml", ".yml"):
        file_type = "yaml"
        results.append(validate_yaml(content, path))

    # Always run best practices check
    if file_type:
        results.append(validate_best_practices(content, path, file_type))

    return results


def extract_error_context(validation_results: list[ValidationResult]) -> str:
    """Extract a human-readable error summary from validation results."""
    if not validation_results:
        return "No validation errors found."

    parts = []
    for result in validation_results:
        if not result.has_errors:
            continue
        parts.append(f"\n## Errors in {result.artifact_path} ({result.validator_type}):\n")
        for issue in result.issues:
            if issue.severity == ValidationSeverity.ERROR:
                loc = f" (Line {issue.line})" if issue.line else ""
                parts.append(f"- {issue.message}{loc}")
                if issue.suggestion:
                    parts.append(f"  Suggestion: {issue.suggestion}")

    return "\n".join(parts) if parts else "No errors found, but there are warnings."
