"""
Rule Extractor

Extracts deterministic validation rules from documentation.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Validation rules loaded from documentation
# In production, these would be extracted from docs using NLP
VALIDATION_RULES: List[Dict[str, Any]] = [
    {
        "rule": "CDS_NAMESPACE_REQUIRED",
        "description": "All CDS files must declare a namespace",
        "category": "data_modeling",
        "check": lambda state: bool(state.get("generated_schema_cds", "").find("namespace") >= 0),
    },
    {
        "rule": "CDS_ENTITY_REQUIRED",
        "description": "Schema must contain at least one entity definition",
        "category": "data_modeling",
        "check": lambda state: bool(state.get("generated_schema_cds", "").find("entity") >= 0),
    },
    {
        "rule": "SERVICE_DEFINITION_REQUIRED",
        "description": "Service CDS must define at least one service",
        "category": "service_exposure",
        "check": lambda state: bool(state.get("generated_service_cds", "").find("service") >= 0),
    },
    {
        "rule": "HANDLER_EXPORTS_REQUIRED",
        "description": "Service handler must export a function",
        "category": "business_logic",
        "check": lambda state: bool(state.get("generated_handler_js", "").find("module.exports") >= 0 or 
                                    state.get("generated_handler_js", "").find("export") >= 0),
    },
    {
        "rule": "MANIFEST_JSON_REQUIRED",
        "description": "Fiori app must have a manifest.json",
        "category": "fiori_ui",
        "check": lambda state: bool(state.get("generated_manifest_json", "")),
    },
    {
        "rule": "ENTITIES_NOT_EMPTY",
        "description": "At least one entity must be defined",
        "category": "requirements",
        "check": lambda state: len(state.get("entities", [])) > 0,
    },
    {
        "rule": "PROJECT_NAME_VALID",
        "description": "Project name must be non-empty",
        "category": "requirements",
        "check": lambda state: bool(state.get("project_name", "").strip()),
    },
    {
        "rule": "ARTIFACTS_GENERATED",
        "description": "At least one artifact must be generated",
        "category": "project_assembly",
        "check": lambda state: (
            len(state.get("artifacts_db", [])) > 0 or
            len(state.get("artifacts_srv", [])) > 0 or
            len(state.get("artifacts_app", [])) > 0
        ),
    },
]


def get_rules_for_category(category: str) -> List[Dict[str, Any]]:
    """
    Get validation rules for a specific category.
    
    Args:
        category: Rule category (e.g., "data_modeling", "service_exposure")
        
    Returns:
        List of rules for that category
    """
    return [rule for rule in VALIDATION_RULES if rule["category"] == category]


def get_all_rules() -> List[Dict[str, Any]]:
    """Get all validation rules."""
    return VALIDATION_RULES.copy()


def check_rule(rule: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check a single validation rule against state.
    
    Args:
        rule: Rule definition
        state: BuilderState to check
        
    Returns:
        Result dict with rule, passed, and evidence
    """
    try:
        passed = rule["check"](state)
        return {
            "rule": rule["rule"],
            "description": rule["description"],
            "category": rule["category"],
            "passed": passed,
            "evidence": "Rule check passed" if passed else "Rule check failed",
        }
    except Exception as e:
        logger.error(f"Error checking rule {rule['rule']}: {e}")
        return {
            "rule": rule["rule"],
            "description": rule["description"],
            "category": rule["category"],
            "passed": False,
            "evidence": f"Error during check: {str(e)}",
        }


def check_all_rules(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Check all validation rules against state.
    
    Args:
        state: BuilderState to check
        
    Returns:
        List of rule check results
    """
    results = []
    for rule in VALIDATION_RULES:
        result = check_rule(rule, state)
        results.append(result)
    
    return results
