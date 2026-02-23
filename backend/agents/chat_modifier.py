"""
Chat Modifier Agent

LLM-powered agent that interprets user natural language prompts
and translates them into SAP CAP application configuration changes.

Used after the first generation to let users iteratively refine
their app through conversational prompts.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager

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
  "suggested_followups": [
    "A helpful next modification the user might want",
    "Another suggestion"
  ]
}}

RULES:
1. ALWAYS return the COMPLETE configuration, not just changes. Merge user's request into existing config.
2. Use SAP CAP naming conventions: PascalCase for entities, camelCase for fields.
3. All entities MUST have an "ID" field with type "UUID", key: true.
4. Always include "aspects": ["cuid", "managed"] unless the user specifies otherwise.
5. Valid CDS types: UUID, String, Integer, Decimal, Boolean, Date, DateTime, Time, LargeString, Int64.
6. For String types, include "length" (default 100).
7. For Decimal types, include "precision" and "scale".
8. Keep ALL existing entities/fields unless the user explicitly asks to remove them.
9. Provide 2-3 helpful follow-up suggestions.
10. The "explanation" should be concise and friendly.
11. Respond with ONLY valid JSON, no markdown formatting.
"""


async def process_chat_prompt(
    user_message: str,
    current_config: dict[str, Any],
    chat_history: list[dict[str, Any]],
    llm_provider: str | None = None,
) -> dict[str, Any]:
    """
    Process a user chat prompt and return configuration changes.
    
    Args:
        user_message: The user's natural language modification request
        current_config: Current session configuration
        chat_history: Previous chat messages for context
        llm_provider: Which LLM provider to use
        
    Returns:
        Dict with: explanation, updated_config, suggested_followups
    """
    llm_manager = get_llm_manager()

    # Build a slim version of the config for the system prompt.
    # Remove chat_history and other large/redundant keys to prevent
    # the prompt from growing unboundedly after many messages.
    slim_config = {
        k: v for k, v in current_config.items()
        if k not in ("chat_history", "artifacts", "agent_history",
                      "validation_errors", "correction_history")
    }
    # Also strip entities_preview from any nested entities
    for entity in slim_config.get("entities", []):
        entity.pop("entities_preview", None)

    config_str = json.dumps(slim_config, indent=2, default=str)
    system_prompt = CHAT_SYSTEM_PROMPT.format(current_config=config_str)

    # Build conversation context from history (last 6 messages, text only)
    context_messages = ""
    recent_history = chat_history[-6:] if len(chat_history) > 6 else chat_history
    for msg in recent_history:
        role = msg.get("role", "user")
        content = msg.get("message", "")
        context_messages += f"\n{role.upper()}: {content}"
    
    # Build the full prompt
    prompt = f"""Previous conversation:
{context_messages}

USER's new request: {user_message}

Analyze the request and return the updated configuration as JSON. Remember to keep ALL existing entities/fields unless explicitly asked to remove them."""

    try:
        # Determine which provider to use
        provider_name = llm_provider or current_config.get("llm_provider")
        
        response_text = await llm_manager.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider_name,
        )
        
        # Parse the JSON response
        result = _parse_llm_response(response_text)
        
        if result:
            logger.info(f"Chat modifier: {result.get('explanation', 'Config updated')}")
            return result
        else:
            # Fallback: return current config unchanged
            logger.warning("Chat modifier: Failed to parse LLM response, returning unchanged config")
            return {
                "explanation": "I had trouble processing that request. Could you try rephrasing it?",
                "updated_config": current_config,
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
            "suggested_followups": [
                "Try again with a simpler request",
                "Check that your LLM API key is configured",
            ],
        }


def _parse_llm_response(response_text: str) -> dict[str, Any] | None:
    """Parse and validate the LLM JSON response."""
    try:
        # Try direct parse first
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code block
    try:
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        pass
    
    # Try to find JSON object in the response
    try:
        start = response_text.index("{")
        end = response_text.rindex("}") + 1
        json_str = response_text[start:end]
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError):
        pass
    
    return None
