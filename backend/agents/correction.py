"""
Correction Prompt Generator

Generates intelligent correction prompts for the LLM when validation fails.
Includes context from the original task, specific errors, and hints for fixing.

Enhanced with agent-specific hints for all 9 agents and common mistake patterns.
"""

import logging
from typing import Any

from backend.agents.state import BuilderState
from backend.agents.validator import ValidationResult, extract_error_context

logger = logging.getLogger(__name__)


CORRECTION_SYSTEM_PROMPT = """You are an expert SAP CAP developer tasked with fixing code errors.

You will receive:
1. The original task requirements
2. The code you previously generated
3. Specific validation errors found in that code

Your job is to:
- Analyze the errors carefully
- Fix ONLY the issues mentioned in the error report
- Maintain the original logic and structure where possible
- Follow SAP CAP best practices

Return the corrected code in the same JSON format as before.
"""


# =============================================================================
# Agent-Specific Correction Hints
# =============================================================================

AGENT_HINTS = {
    "data_modeling": [
        "All entities should have a key field (use `key ID : UUID;` or `cuid` aspect)",
        "Use proper CDS types: String, Integer, Decimal, Boolean, Date, DateTime, UUID",
        "Include namespace declaration: `namespace com.company.app;`",
        "Use aspects like `managed` for createdAt/createdBy tracking",
        "Compositions: `items : Composition of many Items on items.parent = $self;`",
        "Associations: `category : Association to Categories;`",
        "Enum types: `type Status : String enum { New; InProcess; Completed; Cancelled; };`",
        "String lengths: `name : String(100);`",
        "Annotations: `@mandatory`, `@title: 'Label'`, `@assert.range`",
    ],
    "service_exposure": [
        "Use `@odata.draft.enabled` for root editable entities (not children)",
        "Proper projection: `entity Orders as projection on db.Orders;`",
        "Include @UI.HeaderInfo with TypeName and TypeNamePlural",
        "Include @UI.LineItem with Position and Importance",
        "Include @UI.Facets with ReferenceFacet targeting @UI.FieldGroup",
        "@Common.ValueListWithFixedValues for enum fields",
        "Expose related entities for navigation: entity Items as projection...",
        "Custom actions: `action approve(ID : UUID) returns String;`",
    ],
    "business_logic": [
        "Use async/await for all handlers",
        "Use `cds.log('service')` instead of console.log",
        "Use `req.error(statusCode, message, target)` for validation errors",
        "Pattern: `module.exports = cds.service.impl(async function() { ... });`",
        "Always use `this.before()`, `this.after()`, `this.on()` inside the impl",
        "Draft handlers: `this.before('SAVE', Entity, ...)` for activation validation",
        "SELECT: `const rows = await SELECT.from(Entity).where({ID})`",
        "UPDATE: `await UPDATE(Entity).set({status: 'Approved'}).where({ID})`",
    ],
    "fiori_ui": [
        "manifest.json must have 'sap.app', 'sap.ui', 'sap.ui5' sections",
        "Component.js must extend 'sap/fe/core/AppComponent'",
        "Routes must match pattern: `EntityName({key}):?query:`",
        "Target type should be 'Component' with name 'sap.fe.templates.ListReport' or 'sap.fe.templates.ObjectPage'",
        "FCL config: routing.config.flexibleColumnLayout",
        "Model 'i18n': type 'sap.ui.model.resource.ResourceModel'",
        "Default model '': dataSource 'mainService'",
    ],
    "security": [
        "xs-security.json requires 'xsappname' and 'tenant-mode'",
        "Scopes use '$XSAPPNAME.scopeName' format",
        "Role templates reference scopes via 'scope-references' array",
        "@restrict syntax: `@(restrict: [{ grant: 'READ', to: 'Viewer' }])`",
        "Instance-based: `where: 'createdBy = $user'`",
        "@PersonalData annotations for GDPR fields",
    ],
    "deployment": [
        "mta.yaml requires '_schema-version', 'ID', 'modules', 'resources'",
        "package.json must have '@sap/cds' in dependencies",
        "Include scripts: start, watch, build, deploy",
        "CDS profiles in package.json: [production] and [development]",
        "Dockerfile: Use node:18-alpine, expose port 4004",
        "GitHub Actions: Node.js 18, npm ci, mbt build, cf deploy",
    ],
    "extension": [
        "Extensions should be additive and not break existing functionality",
        "Custom UI annotations go in srv/annotations.cds",
        "Custom pages need proper route configuration in manifest.json",
    ],
    "validation": [
        "Run all validators on the final output",
        "Cross-file consistency: entity names match across schema→service→annotations",
    ],
    "requirements": [
        "Ensure all entities have at least one non-key field",
        "Entity names should be PascalCase",
        "Field names should be camelCase",
    ],
}


# =============================================================================
# Common Mistake Patterns
# =============================================================================

COMMON_MISTAKES = {
    "UNBALANCED_BRACES": "Count all { and } in your output. Each opening brace must have a matching closing brace.",
    "INVALID_JSON": "Ensure your JSON has no trailing commas, uses double quotes for strings, and has no comments.",
    "NO_ENTITIES": "Every schema.cds must define at least one entity. Use: entity EntityName { key ID : UUID; }",
    "MISSING_NAMESPACE": "Add namespace at the top: namespace com.company.app;",
    "NO_EXPORT": "Service handler must export: module.exports = cds.service.impl(async function() { ... });",
    "CONSOLE_LOG": "Replace console.log with: const LOG = cds.log('service'); LOG.info('message');",
    "MISSING_SAP_APP": "manifest.json must include 'sap.app' with id, type, dataSources.",
    "MISSING_SAP_UI5": "manifest.json must include 'sap.ui5' with routing, models, dependencies.",
    "MISSING_XSAPPNAME": "xs-security.json must include 'xsappname' field.",
    "INVALID_TYPE": "Use valid CDS types: String, Integer, Decimal, Boolean, Date, DateTime, UUID, etc.",
}


# =============================================================================
# Prompt Generator
# =============================================================================

def generate_correction_prompt(
    agent_name: str,
    original_task: str,
    generated_output: dict[str, Any],
    validation_results: list[ValidationResult],
    state: BuilderState
) -> str:
    """
    Generate a correction prompt for the LLM to fix validation errors.
    """
    error_context = extract_error_context(validation_results)

    error_count = sum(result.error_count for result in validation_results)
    warning_count = sum(result.warning_count for result in validation_results)

    parts = [
        f"## Correction Required for {agent_name}",
        f"",
        f"Your generation had **{error_count} error(s)** and {warning_count} warning(s).",
        f"",
        f"### Original Task:",
        f"{original_task}",
        f"",
        f"### Validation Errors:",
        f"{error_context}",
        f"",
        f"### Fix Instructions:",
        f"1. Fix all ERROR-level issues",
        f"2. Address WARNING-level issues if possible",
        f"3. Maintain the same output JSON structure",
        f"4. Do not change unrelated code",
        f"",
    ]

    # Add agent-specific hints
    hints = AGENT_HINTS.get(agent_name, [])
    if hints:
        parts.append(f"### {agent_name.replace('_', ' ').title()} Best Practices:")
        for hint in hints:
            parts.append(f"- {hint}")
        parts.append("")

    # Add common mistake fixes
    error_codes = set()
    for result in validation_results:
        for issue in result.issues:
            if issue.code:
                error_codes.add(issue.code)

    relevant_fixes = {k: v for k, v in COMMON_MISTAKES.items() if k in error_codes}
    if relevant_fixes:
        parts.append("### Common Fix Patterns:")
        for code, fix in relevant_fixes.items():
            parts.append(f"- **{code}**: {fix}")
        parts.append("")

    parts.append("Generate the corrected code now:")
    return "\n".join(parts)


def should_retry_agent(validation_results: list[ValidationResult], retry_count: int, max_retries: int = 3) -> bool:
    """Determine if an agent should retry based on validation results."""
    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) reached")
        return False

    has_errors = any(result.has_errors for result in validation_results)
    if not has_errors:
        return False

    error_count = sum(result.error_count for result in validation_results)
    logger.info(f"Retry needed: {error_count} errors found, attempt {retry_count + 1}/{max_retries}")
    return True


def format_correction_summary(
    agent_name: str,
    original_errors: int,
    fixed_errors: int,
    retry_count: int
) -> str:
    """Format a human-readable summary of the correction process."""
    if fixed_errors == original_errors:
        status = "✅ All errors fixed"
    elif fixed_errors > 0:
        status = f"⚠️ {fixed_errors}/{original_errors} errors fixed"
    else:
        status = "❌ Could not fix errors"

    return f"{agent_name}: {status} (after {retry_count} attempt{'s' if retry_count != 1 else ''})"
