"""
Chat Modifier Agent (Enhanced — Selective Regeneration)

LLM-powered agent that interprets user natural language prompts
and translates them into SAP CAP application configuration changes.

Enhanced capabilities:
1. Modifies configuration JSON based on user prompts
2. Determines which agents need to re-run based on the changes
3. Triggers selective regeneration through the graph pipeline
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.llm_utils import parse_llm_json

logger = logging.getLogger(__name__)


CHAT_SYSTEM_PROMPT = """You are an expert SAP CAP + Fiori Elements application architect.
You help users modify their SAP application configuration through natural language.

CURRENT APPLICATION CONFIGURATION:
{current_config}

YOUR TASK:
Given the user's modification request, produce an UPDATED configuration.
You must return a JSON response with the following structure:

{{
  "explanation": "Brief human-friendly description of what you changed",
  "change_type": "schema|service|ui|security|logic|config|all",
  "updated_config": {{
    "project_name": "...",
    "project_namespace": "...",
    "project_description": "...",
    "domain": "custom",
    "entities": [
      {{
        "name": "EntityName",
        "description": "What this entity represents",
        "fields": [
          {{"name": "ID", "type": "UUID", "key": true, "nullable": false}},
          {{"name": "fieldName", "type": "String", "length": 100, "nullable": false}},
          ...
        ],
        "aspects": ["cuid", "managed"]
      }}
    ],
    "relationships": [
      {{"name": "relName", "source_entity": "Entity1", "target_entity": "Entity2", "type": "association", "cardinality": "n:1"}}
    ],
    "business_rules": [
      {{"name": "ruleName", "description": "...", "entity": "EntityName", "rule_type": "validation"}}
    ],
    "fiori_theme": "sap_horizon",
    "fiori_main_entity": "MainEntityName",
    "auth_type": "mock",
    "llm_provider": "...",
    "llm_model": "..."
  }},
  "agents_to_rerun": ["data_modeling", "service_exposure"],
  "suggested_followups": [
    "A helpful next modification the user might want",
    "Another suggestion"
  ]
}}

CHANGE TYPES AND AGENT MAPPING:
- "schema" changes (add/modify/remove entities, fields, relationships):
  agents_to_rerun: ["data_modeling", "service_exposure", "business_logic", "fiori_ui", "security", "deployment", "validation"]
- "service" changes (modify service projections, actions):
  agents_to_rerun: ["service_exposure", "business_logic", "validation"]
- "logic" changes (modify business rules, validations, calculations):
  agents_to_rerun: ["business_logic", "validation"]
- "ui" changes (theme, layout, Fiori config):
  agents_to_rerun: ["fiori_ui", "validation"]
- "security" changes (auth type, roles):
  agents_to_rerun: ["security", "validation"]
- "config" changes (name, namespace, description):
  agents_to_rerun: ["data_modeling", "service_exposure", "business_logic", "fiori_ui", "security", "deployment", "validation"]
- "all" — full regeneration

RULES:
1. ALWAYS return the COMPLETE configuration, not just changes. Merge user's request into existing config.
2. Use SAP CAP naming conventions: PascalCase for entities, camelCase for fields.
3. All entities MUST have an "ID" field with type "UUID", key: true.
4. Always include "aspects": ["cuid", "managed"] unless the user specifies otherwise.
5. Valid CDS types: UUID, String, Integer, Decimal, Boolean, Date, DateTime, Time, LargeString, Int64, Timestamp.
6. For String types, include "length" (default 100).
7. For Decimal types, include "precision" and "scale".
8. Keep ALL existing entities/fields unless the user explicitly asks to remove them.
9. Provide 2-3 helpful follow-up suggestions.
10. The "explanation" should be concise and friendly.
11. Include "agents_to_rerun" based on the change_type.
12. Respond with ONLY valid JSON, no markdown formatting.
"""


# =============================================================================
# Determine which agents to re-run
# =============================================================================

CHANGE_TYPE_AGENT_MAP = {
    "schema": ["data_modeling", "service_exposure", "business_logic", "fiori_ui", "security", "deployment", "validation"],
    "service": ["service_exposure", "business_logic", "validation"],
    "logic": ["business_logic", "validation"],
    "ui": ["fiori_ui", "validation"],
    "security": ["security", "validation"],
    "config": ["data_modeling", "service_exposure", "business_logic", "fiori_ui", "security", "deployment", "validation"],
    "all": ["requirements", "data_modeling", "service_exposure", "business_logic", "fiori_ui", "security", "extension", "deployment", "validation"],
}


def determine_agents_to_rerun(change_type: str, llm_suggestion: list[str] | None = None) -> list[str]:
    """
    Determine which agents need to re-run based on the type of change.
    Uses LLM suggestion if available, otherwise falls back to the map.
    """
    if llm_suggestion and isinstance(llm_suggestion, list) and len(llm_suggestion) > 0:
        # Validate agent names
        valid_agents = {"requirements", "data_modeling", "service_exposure", "business_logic",
                       "fiori_ui", "security", "extension", "deployment", "validation"}
        validated = [a for a in llm_suggestion if a in valid_agents]
        if validated:
            # Always include validation at the end
            if "validation" not in validated:
                validated.append("validation")
            return validated

    return CHANGE_TYPE_AGENT_MAP.get(change_type, CHANGE_TYPE_AGENT_MAP["all"])


# =============================================================================
# Main Function
# =============================================================================

async def process_chat_prompt(
    user_message: str,
    current_config: dict[str, Any],
    chat_history: list[dict[str, Any]],
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    """
    Process a user chat prompt and return configuration changes + regeneration plan.

    Args:
        user_message: The user's natural language modification request
        current_config: Current session configuration
        chat_history: Previous chat messages for context
        llm_provider: Which LLM provider to use
        llm_model: Which model to use

    Returns:
        Dict with: explanation, updated_config, suggested_followups,
                   agents_to_rerun, change_type
    """
    llm_manager = get_llm_manager()

    # Build slim config for prompt (remove large/redundant keys)
    slim_config = {
        k: v for k, v in current_config.items()
        if k not in ("chat_history", "artifacts", "agent_history",
                      "validation_errors", "correction_history",
                      "generated_schema_cds", "generated_common_cds",
                      "generated_service_cds", "generated_annotations_cds",
                      "generated_handler_js", "generated_manifest_json")
    }
    for entity in slim_config.get("entities", []):
        entity.pop("entities_preview", None)

    config_str = json.dumps(slim_config, indent=2, default=str)
    system_prompt = CHAT_SYSTEM_PROMPT.format(current_config=config_str)

    # Build conversation context (last 6 messages)
    context_messages = ""
    recent_history = chat_history[-6:] if len(chat_history) > 6 else chat_history
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("message", "")
        context_messages += f"\n{role.upper()}: {content}"

    prompt = f"""Previous conversation:
{context_messages}

USER's new request: {user_message}

Analyze the request and return the updated configuration as JSON.
Remember to include "change_type" and "agents_to_rerun" in your response.
Keep ALL existing entities/fields unless explicitly asked to remove them."""

    try:
        provider_name = llm_provider or current_config.get("llm_provider")
        model_name = llm_model or current_config.get("llm_model")

        response_text = await llm_manager.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider_name,
            model=model_name,
        )

        result = parse_llm_json(response_text)

        if result:
            # Determine agents to re-run
            change_type = result.get("change_type", "all")
            agents_to_rerun = determine_agents_to_rerun(
                change_type,
                result.get("agents_to_rerun"),
            )
            result["agents_to_rerun"] = agents_to_rerun
            result["change_type"] = change_type

            logger.info(f"Chat modifier: {result.get('explanation', 'Config updated')} — re-running: {agents_to_rerun}")
            return result
        else:
            logger.warning("Chat modifier: Failed to parse LLM response, returning unchanged config")
            return {
                "explanation": "I had trouble processing that request. Could you try rephrasing it?",
                "updated_config": current_config,
                "change_type": "none",
                "agents_to_rerun": [],
                "suggested_followups": [
                    "Try a more specific request like 'Add an Employee entity'",
                    "You can also say 'Change theme to dark'",
                ],
            }

    except Exception as e:
        logger.error(f"Chat modifier error: {e}")
        return {
            "explanation": f"Sorry, I encountered an error: {str(e)}. Please try again.",
            "updated_config": current_config,
            "change_type": "none",
            "agents_to_rerun": [],
            "suggested_followups": [
                "Try again with a simpler request",
                "Check that your LLM API key is configured",
            ],
        }
