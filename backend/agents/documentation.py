"""
Agent: Documentation

OpenAPI spec, CDS docs, ADRs, runbooks, changelog.
"""

import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


async def documentation_agent(state: BuilderState) -> BuilderState:
    """
    Documentation Agent - OpenAPI, CDS docs, ADRs, runbooks.
    
    Generates:
    - OpenAPI specification
    - CDS documentation
    - Architecture Decision Records (ADRs)
    - Operational runbooks
    - CHANGELOG.md
    """
    logger.info("Starting Documentation Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "documentation"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting documentation phase...")
    
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
    return state
