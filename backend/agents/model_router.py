"""
Model Routing Layer
Maps each agent to the appropriate model tier based on task complexity.

IMPORTANT: This module now respects the user's provider and model selection.
It only determines which agents need "strategic" vs "efficient" tier,
but uses the user-selected provider and model from the state.
"""

from typing import Literal, Optional

# Agent tier classification (strategic vs efficient)
# This determines which agents need more powerful models
AGENT_TIER_MAP: dict[str, Literal["strategic", "efficient"]] = {
    # Strategic tier — Complex reasoning, architecture decisions
    "enterprise_architecture": "strategic",
    "domain_modeling": "strategic",
    "business_logic": "strategic",
    "validation": "strategic",
    "security": "strategic",
    "compliance_check": "strategic",
    
    # Efficient tier — Pattern-based, rule-guided, template-based
    "data_modeling": "efficient",
    "service_exposure": "efficient",
    "fiori_ui": "efficient",
    "integration_design": "efficient",
    "error_handling": "efficient",
    "audit_logging": "efficient",
    "api_governance": "efficient",
    "performance_review": "efficient",
    "multitenancy": "efficient",
    "feature_flags": "efficient",
    "ux_design": "efficient",
    "db_migration": "efficient",
    "i18n": "efficient",
    "ci_cd": "efficient",
    "deployment": "efficient",
    "testing": "efficient",
    "documentation": "efficient",
    "observability": "efficient",
    "project_assembly": "efficient",
    "project_verification": "efficient",
    "requirements": "efficient",
    "integration": "efficient",
    "extension": "efficient",
}


def get_model_for_agent(
    agent_name: str,
    user_provider: Optional[str] = None,
    user_model: Optional[str] = None
) -> str:
    """
    Get the appropriate model for a given agent.
    
    IMPORTANT: This now uses the user's selected provider and model.
    The tier classification only matters if the user wants tier-based routing.
    
    Args:
        agent_name: Name of the agent (e.g., "data_modeling")
        user_provider: User-selected LLM provider (e.g., "openai", "xai")
        user_model: User-selected model (e.g., "gpt-4", "grok-beta")
        
    Returns:
        Model identifier string - uses user's selection
    """
    # If user specified a model, use it for ALL agents
    # This respects the user's choice from the frontend
    if user_model:
        return user_model
    
    # Fallback to a default if no user selection
    # (This should rarely happen as frontend always sends a model)
    return "gpt-4"


def get_model_tier_name(agent_name: str) -> Literal["Strategic", "Efficient"]:
    """
    Get the human-readable tier name for an agent.
    
    This is for UI display purposes only - it doesn't affect model selection.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        Tier name: "Strategic" or "Efficient"
    """
    tier = AGENT_TIER_MAP.get(agent_name, "efficient")
    return "Strategic" if tier == "strategic" else "Efficient"


def is_strategic_agent(agent_name: str) -> bool:
    """
    Check if an agent is classified as strategic tier.
    
    Args:
        agent_name: Name of the agent
        
    Returns:
        True if strategic, False if efficient
    """
    return AGENT_TIER_MAP.get(agent_name, "efficient") == "strategic"
