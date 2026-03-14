# Agent Upgrade Guide

## Completed Agents (3/13)
✅ domain_modeling.py - Full LLM with DDD analysis
✅ integration_design.py - Full LLM with S/4HANA integration
✅ ux_design.py - Full LLM with Fiori floorplan selection

## Pattern to Follow

Each agent upgrade follows this exact structure:

### 1. Imports
```python
import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)
```

### 2. System Prompt
```python
AGENT_SYSTEM_PROMPT = """You are an expert in [domain].
[Describe expertise and task]

[List key concepts/patterns]

OUTPUT FORMAT:
Return valid JSON:
{
  "field1": "value",
  "field2": ["list"],
  "field3": {"nested": "object"}
}

Return ONLY valid JSON."""
```

### 3. Generation Prompt
```python
AGENT_PROMPT = """[Task description]

Project: {project_name}
Description: {description}

[Context fields]:
{context_json}

Tasks:
1. [Task 1]
2. [Task 2]
3. [Task 3]

Respond with ONLY valid JSON."""
```

### 4. Agent Function
```python
async def agent_name_agent(state: BuilderState) -> BuilderState:
    """Agent description"""
    logger.info("Starting Agent Name")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "agent_name"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting agent phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    # ... other context
    
    # Check if work needed
    if not some_condition:
        log_progress(state, "No work needed - using minimal spec")
        result_spec = {/* minimal */}
    else:
        # Retrieve RAG docs
        rag_docs = await retrieve_for_agent("agent_name", f"query about {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        # Build prompt
        prompt = AGENT_PROMPT.format(
            project_name=project_name,
            description=description or "No description",
            context_json=json.dumps(context, indent=2),
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, f"Processing...")
        
        # Generate with retry
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=AGENT_SYSTEM_PROMPT,
            state=state,
            required_keys=["key1", "key2"],
            max_retries=3,
            agent_name="agent_name",
        )
        
        if result:
            result_spec = result
            log_progress(state, f"✅ Generated {len(result.get('items', []))} items")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal spec")
            result_spec = {/* minimal fallback */}
    
    # Update state
    state["agent_output_field"] = result_spec
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "agent_name",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Agent complete.")
    return state
```

## Remaining Agents to Upgrade (10/13)

### High Priority
1. **compliance_check.py** - GDPR, data privacy scan
   - System prompt: GDPR expert, data privacy specialist
   - Check: Personal data fields, consent management, data retention
   - Output: compliance_report with checks and recommendations

2. **performance_review.py** - Query optimization, HANA indexes
   - System prompt: SAP HANA performance expert
   - Analyze: CDS queries, N+1 patterns, missing indexes
   - Output: performance_report with recommendations

3. **error_handling.py** - Global error handlers
   - System prompt: Error handling architect
   - Generate: Error handler code, custom exceptions, error codes
   - Output: error_handling_spec + srv/lib/error-handler.js file

### Medium Priority
4. **audit_logging.py** - @changelog annotations
   - System prompt: Audit trail expert
   - Generate: @changelog annotations, history entities
   - Output: audit_logging_spec

5. **api_governance.py** - API versioning, catalog
   - System prompt: API governance specialist
   - Generate: Versioning strategy, deprecation policy
   - Output: api_governance_spec + docs/API_CATALOG.md

6. **multitenancy.py** - cds-mtxs configuration
   - System prompt: SAP multitenancy expert
   - Generate: mtxs config, tenant onboarding
   - Output: multitenancy_config

### Low Priority (Template-Based)
7. **i18n.py** - Translation bundles
   - Extract labels from entities/fields
   - Generate i18n.properties files
   - Output: i18n_bundles + i18n/i18n.properties

8. **feature_flags.py** - Feature toggles
   - Define feature flags for optional features
   - Output: feature_flags_config

9. **ci_cd.py** - GitHub Actions pipeline
   - Generate workflow YAML
   - Output: ci_cd_config + .github/workflows/ci.yml

10. **observability.py** - Monitoring setup
    - Generate monitoring config
    - Output: observability_config

## Quick Upgrade Commands

For each agent, follow these steps:

1. Open the agent file (e.g., `backend/agents/compliance_check.py`)
2. Replace the stub with the full pattern above
3. Customize the system prompt for the agent's domain
4. Define the generation prompt with relevant context
5. Set the correct state output field
6. Test with: `python -c "from backend.agents.compliance_check import compliance_check_agent; print('OK')"`

## Testing

After upgrading each agent:
```bash
# Test import
python -c "from backend.agents.{agent_name} import {agent_name}_agent; print('✅ Import OK')"

# Test graph compilation
python -c "from backend.agents.graph import create_builder_graph; g = create_builder_graph(); print(f'✅ Graph OK: {len(g.nodes)} nodes')"
```

## Notes

- All agents use model routing automatically (Sonnet/Haiku selection)
- RAG integration is optional but recommended
- Always provide a minimal fallback if LLM fails
- Log progress at key steps for SSE streaming
- Set needs_correction = False on success
- Record execution in agent_history
