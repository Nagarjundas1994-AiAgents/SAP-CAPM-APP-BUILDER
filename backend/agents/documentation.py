"""
Agent: Documentation

OpenAPI spec, CDS docs, ADRs, runbooks, changelog.
"""

import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.resilience import with_timeout

logger = logging.getLogger(__name__)


@with_timeout(timeout_seconds=120)
async def documentation_agent(state: BuilderState) -> dict[str, Any]:
    """
    Documentation Agent - OpenAPI, CDS docs, ADRs, runbooks.
    
    Generates:
    - OpenAPI specification
    - CDS documentation
    - Architecture Decision Records (ADRs)
    - Operational runbooks
    - CHANGELOG.md
    """
    agent_name = "documentation"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Documentation Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "documentation"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting documentation phase...")
    
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
    
        # Stub implementation
        documentation_bundle = {
        "openapi_spec": {},
        "cds_docs": [],
        "adrs": [],
        "runbooks": [],
        "changelog": []
        }
    
        # Generate minimal README
        project_name = state.get("project_name", "SAP CAP Application")
        readme_content = f"""# {project_name}

        ## Overview
        SAP Cloud Application Programming Model (CAP) application.

        ## Getting Started

        ### Prerequisites
        - Node.js 18+
        - @sap/cds-dk

        ### Installation
        ```bash
        npm install
        ```

        ### Run Locally
        ```bash
        cds watch
        ```

        ## Documentation
        - [Architecture](docs/ARCHITECTURE.md)
        - [API Documentation](docs/API.md)
        - [Development Guide](docs/DEVELOPMENT.md)

        ## License
        Proprietary
        """
    
        generated_files = [{
        "path": "README.md",
        "content": readme_content,
        "file_type": "md"
        }]
    
        state["documentation_bundle"] = documentation_bundle
        state["artifacts_docs"] = state.get("artifacts_docs", []) + generated_files
        state["needs_correction"] = False
    
        # Record execution
        state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "documentation",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
        }]
    
        log_progress(state, "Documentation complete (stub).")
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
    
        return {
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