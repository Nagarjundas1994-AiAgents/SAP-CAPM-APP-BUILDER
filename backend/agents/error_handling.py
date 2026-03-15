"""
Agent: Error Handling

Generates global CAP error handlers, custom exceptions, and error codes.
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


ERROR_HANDLING_SYSTEM_PROMPT = """You are an error handling and exception design expert for enterprise applications.
Your task is to design a comprehensive error handling strategy with custom error codes, exception classes, and global handlers.

ERROR HANDLING PRINCIPLES:
1. Error Codes: Unique codes for each error type (e.g., VAL_001, AUTH_002)
2. Error Categories: Validation, Authentication, Authorization, Business Logic, System
3. HTTP Status Mapping: 400 (validation), 401 (auth), 403 (forbidden), 404 (not found), 500 (system)
4. User-Friendly Messages: Clear, actionable error messages
5. Logging: Structured error logging with context
6. Recovery: Graceful degradation and retry strategies

OUTPUT FORMAT:
Return valid JSON:
{
  "error_codes": [
    {
      "code": "string",
      "category": "validation/auth/business/system",
      "http_status": 400,
      "message_template": "string",
      "user_message": "string"
    }
  ],
  "custom_exceptions": [
    {
      "name": "string",
      "base_class": "Error",
      "properties": ["code", "message", "details"]
    }
  ],
  "handlers": [
    {
      "error_type": "string",
      "handler_logic": "string",
      "logging_level": "error/warn/info"
    }
  ],
  "error_handler_code": "string (JavaScript code for srv/lib/error-handler.js)"
}

Return ONLY valid JSON."""


ERROR_HANDLING_PROMPT = """Design a comprehensive error handling strategy for this SAP CAP application.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Services:
{services_json}

Tasks:
1. Define error codes for common scenarios (validation, auth, business logic)
2. Design custom exception classes
3. Create global error handler with proper HTTP status mapping
4. Generate error-handler.js with structured error responses
5. Include logging and monitoring hooks

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)
async def error_handling_agent(state: BuilderState) -> dict[str, Any]:
    """
    Error Handling Agent - Global handlers, custom exceptions.

    Generates:
    - srv/lib/error-handler.js
    - Custom error classes
    - Error code catalog
    - Error response formatting
    """
    agent_name = "error_handling"
    started_at = datetime.utcnow().isoformat()

    logger.info(f"[{agent_name}] Starting Error Handling Agent")
    log_progress(state, "Starting error handling phase...")

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
        services = state.get("services", [])

        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("error_handling", f"SAP CAP error handling custom exceptions {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""

        prompt = ERROR_HANDLING_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            entities_json=json.dumps(entities[:5], indent=2) if entities else "[]",
            services_json=json.dumps(services[:3], indent=2) if services else "[]",
        )

        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"

        log_progress(state, "Generating error handling strategy...")

        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=ERROR_HANDLING_SYSTEM_PROMPT,
            state=state,
            required_keys=["error_codes", "error_handler_code"],
            max_retries=3,
            agent_name=agent_name,
        )

        if result:
            error_handling_spec = result
            error_handler_code = result.get("error_handler_code", "")
            log_progress(state, f"✅ Defined {len(result.get('error_codes', []))} error codes")
            log_progress(state, f"✅ Created {len(result.get('custom_exceptions', []))} custom exceptions")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal error handler")
            error_handling_spec = {
                "error_codes": [],
                "custom_exceptions": [],
                "handlers": []
            }
            error_handler_code = """// Global error handler
        module.exports = (err, req) => {
        console.error('Error:', err);
        const statusCode = err.statusCode || err.code || 500;
        return {
        error: {
        code: err.code || 'INTERNAL_ERROR',
        message: err.message || 'An error occurred',
        target: err.target,
        details: err.details || []
        }
        };
        };
        """

        # Generate error handler file
        generated_files = [{
            "path": "srv/lib/error-handler.js",
            "content": error_handler_code,
            "file_type": "js"
        }]

        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)

        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1

        log_progress(state, "Error handling complete.")

        return {
            "error_handling_spec": error_handling_spec,
            "artifacts_srv": generated_files,
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


