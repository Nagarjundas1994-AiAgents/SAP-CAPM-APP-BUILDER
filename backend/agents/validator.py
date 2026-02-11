"""
Self-Healing Validation Module

Validates generated SAP CAP artifacts to detect errors before presenting them to users.
Supports CDS, JavaScript, JSON, and best practices validation.
"""

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import tempfile
import os

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
# CDS Validation
# =============================================================================

def validate_cds(content: str, path: str = "schema.cds") -> ValidationResult:
    """
    Validate CDS content using basic syntax checks.
    
    In a full implementation, this would run `cds compile` in a sandbox.
    For now, we do pattern-based validation.
    """
    issues: list[ValidationIssue] = []
    
    # Check for basic CDS syntax patterns
    lines = content.split("\n")
    
    for line_num, line in enumerate(lines, start=1):
        # Check for common syntax errors
        
        # Missing semicolons at end of entity definitions
        if re.match(r'^\s*entity\s+\w+\s*\{', line):
            # Find the closing brace
            brace_count = line.count("{") - line.count("}")
            if brace_count > 0:
                # This is an opening, check if we eventually close it with ;
                continue
        
        # Check for unmatched braces
        open_braces = line.count("{")
        close_braces = line.count("}")
        if open_braces != close_braces:
            # This is expected for multi-line blocks
            continue
        
        # Check for invalid type annotations
        if re.search(r':\s*(\w+)\s*;', line):
            type_match = re.search(r':\s*(\w+)\s*;', line)
            if type_match:
                cds_type = type_match.group(1)
                valid_types = [
                    "String", "Integer", "Decimal", "Boolean", "Date", "DateTime", "Time",
                    "UUID", "LargeString", "Binary", "LargeBinary", "Double", "Int16", "Int32", "Int64"
                ]
                if cds_type not in valid_types and not cds_type[0].isupper():
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=f"Potentially invalid CDS type '{cds_type}'. Common types: {', '.join(valid_types[:5])}",
                        line=line_num,
                        code="INVALID_TYPE"
                    ))
    
    # Check for namespace declaration
    if "namespace" not in content:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="Missing namespace declaration. Consider adding 'namespace com.company.app;'",
            line=1,
            code="MISSING_NAMESPACE"
        ))
    
    # Check for at least one entity
    if not re.search(r'entity\s+\w+', content):
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message="No entity definitions found in CDS schema",
            line=1,
            code="NO_ENTITIES"
        ))
    
    return ValidationResult(
        is_valid=not any(issue.severity == ValidationSeverity.ERROR for issue in issues),
        issues=issues,
        artifact_path=path,
        validator_type="cds"
    )


# =============================================================================
# JavaScript Validation
# =============================================================================

def validate_javascript(content: str, path: str = "service.js") -> ValidationResult:
    """
    Validate JavaScript content for basic syntax errors.
    
    Uses basic pattern matching. In production, would use esprima or eslint.
    """
    issues: list[ValidationIssue] = []
    lines = content.split("\n")
    
    for line_num, line in enumerate(lines, start=1):
        # Check for common syntax errors
        
        # Unclosed strings
        single_quotes = line.count("'") - line.count("\\'")
        double_quotes = line.count('"') - line.count('\\"')
        if single_quotes % 2 != 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Unclosed string (single quote)",
                line=line_num,
                code="UNCLOSED_STRING"
            ))
        if double_quotes % 2 != 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Unclosed string (double quote)",
                line=line_num,
                code="UNCLOSED_STRING"
            ))
        
        # Unmatched parentheses
        open_parens = line.count("(")
        close_parens = line.count(")")
        if open_parens != close_parens:
            # Could be multi-line, so just warn
            pass
        
        # Check for async/await patterns
        if "await" in line and "async" not in content[:content.find(line)]:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="'await' used outside async function",
                line=line_num,
                code="AWAIT_NON_ASYNC"
            ))
    
    # Check for required CAP patterns in service handlers
    if "module.exports" not in content and "export" not in content:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            message="Missing module.exports or export statement",
            line=1,
            code="NO_EXPORT"
        ))
    
    return ValidationResult(
        is_valid=not any(issue.severity == ValidationSeverity.ERROR for issue in issues),
        issues=issues,
        artifact_path=path,
        validator_type="javascript"
    )


# =============================================================================
# JSON Validation
# =============================================================================

def validate_json(content: str, path: str = "package.json") -> ValidationResult:
    """Validate JSON syntax and structure."""
    issues: list[ValidationIssue] = []
    
    try:
        parsed = json.loads(content)
        
        # Specific validations for package.json
        if "package.json" in path:
            if "name" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="package.json missing 'name' field",
                    code="MISSING_NAME"
                ))
            if "dependencies" not in parsed and "devDependencies" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="package.json has no dependencies",
                    code="NO_DEPENDENCIES"
                ))
            
            # Check for SAP CAP dependencies
            deps = parsed.get("dependencies", {})
            if "@sap/cds" not in deps:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="SAP CAP project should include '@sap/cds' dependency",
                    code="MISSING_CDS_DEPENDENCY"
                ))
        
        # Specific validations for manifest.json (Fiori)
        if "manifest.json" in path:
            if "sap.app" not in parsed:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message="manifest.json missing 'sap.app' section",
                    code="MISSING_SAP_APP"
                ))
    
    except json.JSONDecodeError as e:
        issues.append(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            message=f"Invalid JSON syntax: {str(e)}",
            line=e.lineno,
            column=e.colno,
            code="INVALID_JSON"
        ))
    
    return ValidationResult(
        is_valid=not any(issue.severity == ValidationSeverity.ERROR for issue in issues),
        issues=issues,
        artifact_path=path,
        validator_type="json"
    )


# =============================================================================
# Best Practices Validation
# =============================================================================

def validate_best_practices(content: str, path: str, file_type: str) -> ValidationResult:
    """
    Check for SAP CAP best practices violations.
    """
    issues: list[ValidationIssue] = []
    lines = content.split("\n")
    
    for line_num, line in enumerate(lines, start=1):
        # Check for hardcoded credentials
        if re.search(r'(password|secret|api[_-]?key)\s*[:=]\s*["\'](?!.*\$\{)', line, re.IGNORECASE):
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Hardcoded credentials detected. Use environment variables instead.",
                line=line_num,
                code="HARDCODED_CREDENTIALS",
                suggestion="Use process.env.VAR_NAME or ${env:VAR_NAME}"
            ))
        
        # Check for console.log in production code
        if file_type == "javascript" and "console.log" in line:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="Avoid console.log in production. Use cds.log() instead.",
                line=line_num,
                code="CONSOLE_LOG",
                suggestion="Replace with: const LOG = cds.log('service'); LOG.info(...);"
            ))
    
    # CDS-specific best practices
    if file_type == "cds":
        # Check for @cds.autoexpose usage
        if "@cds.persistence" in content:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="@cds.persistence is deprecated. Consider using table-based approach.",
                code="DEPRECATED_ANNOTATION"
            ))
    
    return ValidationResult(
        is_valid=not any(issue.severity == ValidationSeverity.ERROR for issue in issues),
        issues=issues,
        artifact_path=path,
        validator_type="best_practices"
    )


# =============================================================================
# Unified Validation Interface
# =============================================================================

def validate_artifact(path: str, content: str) -> list[ValidationResult]:
    """
    Validate an artifact based on its file type.
    Returns a list of ValidationResults from different validators.
    """
    results: list[ValidationResult] = []
    
    # Determine file type
    file_ext = Path(path).suffix.lower()
    file_type = None
    
    if file_ext == ".cds" or path.endswith("schema.cds") or path.endswith("service.cds"):
        file_type = "cds"
        results.append(validate_cds(content, path))
    elif file_ext == ".js":
        file_type = "javascript"
        results.append(validate_javascript(content, path))
    elif file_ext == ".json":
        file_type = "json"
        results.append(validate_json(content, path))
    
    # Always run best practices check
    if file_type:
        results.append(validate_best_practices(content, path, file_type))
    
    return results


def extract_error_context(validation_results: list[ValidationResult]) -> str:
    """
    Extract a human-readable error summary from validation results.
    This will be used to generate correction prompts for the LLM.
    """
    if not validation_results:
        return "No validation errors found."
    
    context_parts = []
    
    for result in validation_results:
        if not result.has_errors:
            continue
        
        context_parts.append(f"\n## Errors in {result.artifact_path} ({result.validator_type}):\n")
        
        for issue in result.issues:
            if issue.severity == ValidationSeverity.ERROR:
                location = f" (Line {issue.line})" if issue.line else ""
                context_parts.append(f"- {issue.message}{location}")
                if issue.suggestion:
                    context_parts.append(f"  Suggestion: {issue.suggestion}")
    
    if not context_parts:
        return "No errors found, but there are warnings."
    
    return "\n".join(context_parts)
