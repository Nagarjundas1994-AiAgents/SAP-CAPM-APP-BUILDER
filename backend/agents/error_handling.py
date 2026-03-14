"""
Agent: Error Handling

Generates global CAP error handlers, custom exceptions, and error codes.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
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


async def error_handling_agent(state: BuilderState) -> BuilderState:
    """
    Error Handling Agent - Global handlers, custom exceptions.
    
    Generates:
    - srv/lib/error-handler.js
    - Custom error classes
    - Error code catalog
    - Error response formatting
    """
    logger.info("Starting Error Handling Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "error_handling"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting error handling phase...")
    
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
        entities_json=json.dumps(entities[:5], indent=2) if entities else "[]",  # Limit to 5 for context
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
        agent_name="error_handling",
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
    
    state["error_handling_spec"] = error_handling_spec
    state["artifacts_srv"] = state.get("artifacts_srv", []) + generated_files
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "error_handling",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Error handling complete.")
    return state
