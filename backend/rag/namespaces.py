"""
Agent Namespace Mapping

Maps each agent to its document namespace for scoped RAG retrieval.
"""

# Agent to namespace mapping
AGENT_NAMESPACES = {
    "requirements": "requirements",
    "enterprise_architecture": "architecture",
    "domain_modeling": "domain_modeling",
    "data_modeling": "data_modeling",
    "db_migration": "database",
    "integration_design": "integration",
    "integration": "integration",
    "service_exposure": "service_exposure",
    "error_handling": "error_handling",
    "audit_logging": "audit_logging",
    "api_governance": "api_governance",
    "business_logic": "business_logic",
    "ux_design": "ux_design",
    "fiori_ui": "fiori_ui",
    "security": "security",
    "multitenancy": "multitenancy",
    "i18n": "i18n",
    "feature_flags": "feature_flags",
    "compliance_check": "compliance",
    "extension": "extension",
    "performance_review": "performance",
    "ci_cd": "cicd",
    "deployment": "deployment",
    "testing": "testing",
    "observability": "observability",
    "documentation": "documentation",
    "project_assembly": "assembly",
    "project_verification": "verification",
    "validation": "validation",
}


def get_agent_namespace(agent_name: str) -> str:
    """
    Get the document namespace for an agent.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        Namespace string
    """
    return AGENT_NAMESPACES.get(agent_name, "general")
