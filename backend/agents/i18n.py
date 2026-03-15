"""
Agent: Internationalization (i18n)

Generates i18n.properties files and translation key extraction.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.agents.resilience import with_timeout
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


I18N_SYSTEM_PROMPT = """You are an internationalization (i18n) expert for SAP CAP applications.
Your task is to extract translatable strings and generate i18n property files.

I18N PRINCIPLES:
1. Translation Keys: Extract labels, descriptions, error messages
2. Locale Support: Define supported locales (en, de, fr, etc.)
3. Fallback: Default to English if translation missing
4. Key Naming: Use dot notation (entity.field.label)

OUTPUT FORMAT:
Return valid JSON:
{
  "default_locale": "en",
  "supported_locales": ["en", "de", "fr"],
  "translation_keys": [
    {
      "key": "string",
      "default_value": "string",
      "context": "string"
    }
  ],
  "i18n_properties_content": "string (full content for i18n.properties)"
}

Return ONLY valid JSON."""


I18N_PROMPT = """Extract translatable strings and generate i18n configuration for this SAP CAP application.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Tasks:
1. Extract entity and field labels
2. Generate translation keys
3. Create i18n.properties file content
4. Define supported locales

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=60)
async def i18n_agent(state: BuilderState) -> dict[str, Any]:
    """
    i18n Agent - Translation bundles, locale fallback.
    
    Generates:
    - i18n.properties files
    - Translation key extraction
    - Locale fallback configuration
    """
    agent_name = "i18n"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting i18n Agent")
    log_progress(state, "Starting i18n phase...")
    
    # Check retry count
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exhausted")
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        return {
            "agent_failed": True,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": f"Max retries ({max_retries}) exhausted",
                "logs": None,
            }],
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }
    
    try:
        # Get context
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        entities = state.get("entities", [])
        
        if not entities:
            log_progress(state, "No entities found - using minimal i18n config")
            i18n_bundles = {
                "default_locale": "en",
                "supported_locales": ["en"],
                "translation_keys": []
            }
            i18n_content = f"""# i18n properties
        appTitle={project_name}
        appDescription={description or 'SAP CAP Application'}
        """
        else:
            # Retrieve RAG context
            rag_docs = await retrieve_for_agent("i18n", f"SAP CAP i18n internationalization {project_name}")
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            prompt = I18N_PROMPT.format(
                project_name=project_name,
                description=description or "No description provided",
                entities_json=json.dumps(entities[:10], indent=2) if entities else "[]",
            )
            
            if rag_context:
                prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
            
            log_progress(state, f"Extracting translation keys from {len(entities)} entities...")
            
            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=I18N_SYSTEM_PROMPT,
                state=state,
                required_keys=["default_locale", "translation_keys"],
                max_retries=3,
                agent_name=agent_name,
            )
            
            if result:
                i18n_bundles = result
                i18n_content = result.get("i18n_properties_content", f"# i18n properties\nappTitle={project_name}\n")
                log_progress(state, f"✅ Generated {len(result.get('translation_keys', []))} translation keys")
            else:
                log_progress(state, "⚠️ LLM generation failed - using minimal i18n config")
                i18n_bundles = {
                    "default_locale": "en",
                    "supported_locales": ["en", "de", "fr"],
                    "translation_keys": []
                }
                i18n_content = f"""# i18n properties
        appTitle={project_name}
        appDescription={description or 'SAP CAP Application'}
        """
        
        # Generate i18n file
        generated_files = [{
            "path": "i18n/i18n.properties",
            "content": i18n_content,
            "file_type": "properties"
        }]
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "i18n complete.")
        
        return {
            "i18n_bundles": i18n_bundles,
            "artifacts_docs": generated_files,
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": state.get("current_logs", []),
            }],
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with error: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": str(e),
                "logs": None,
            }],
            "retry_counts": new_retry_counts,
            "needs_correction": True,
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
