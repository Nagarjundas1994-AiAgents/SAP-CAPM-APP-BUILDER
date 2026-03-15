"""
Agent: UX Design

Fiori floorplan selection, wireframes, UX patterns, and navigation design.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.agents.resilience import with_timeout
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


UX_DESIGN_SYSTEM_PROMPT = """You are a SAP Fiori UX expert with deep knowledge of Fiori design guidelines.
Design optimal user experiences for SAP CAP applications.

FIORI FLOORPLANS:
1. List Report: Browse and filter large datasets
2. Object Page: View and edit single object details
3. Worklist: Task-oriented list with actions
4. Overview Page: Dashboard with cards
5. Analytical List Page: List with charts

UX PATTERNS:
- Responsive design (desktop, tablet, mobile)
- Flexible Column Layout for master-detail
- Draft handling for edit scenarios
- Smart filters and search
- Action buttons and toolbars

OUTPUT FORMAT:
Return valid JSON:
{
  "floorplan": "list_report|object_page|worklist|overview_page|analytical_list_page",
  "navigation_structure": {
    "type": "hierarchical|flat|tabbed",
    "levels": 2,
    "routes": [{"path": "string", "target": "string"}]
  },
  "ux_patterns": ["pattern_name"],
  "responsive_breakpoints": {"desktop": 1024, "tablet": 768, "mobile": 480},
  "wireframes": [
    {
      "screen": "string",
      "layout": "string",
      "components": ["component_name"]
    }
  ]
}

Return ONLY valid JSON."""


UX_DESIGN_PROMPT = """Design the UX architecture for the following SAP CAP application.

Project: {project_name}
Description: {description}

Main Entity: {main_entity}
All Entities: {entities_json}
App Type: {app_type}

Tasks:
1. Select optimal Fiori floorplan
2. Design navigation structure
3. Choose UX patterns
4. Define responsive breakpoints
5. Create wireframe specifications

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)
async def ux_design_agent(state: BuilderState) -> dict[str, Any]:
    """
    UX Design Agent - Floorplan selection, wireframes, UX patterns.
    
    Generates:
    - Fiori floorplan recommendations
    - Navigation structure
    - UX pattern guidelines
    - Wireframe specifications
    """
    agent_name = "ux_design"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting UX Design Agent")
    log_progress(state, "Starting UX design phase...")
    
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
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        entities = state.get("entities", [])
        main_entity = state.get("fiori_main_entity", entities[0]["name"] if entities else "")
        app_type = state.get("fiori_app_type", "list_report")
        
        rag_docs = await retrieve_for_agent("ux_design", f"Fiori floorplan UX patterns {app_type}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = UX_DESIGN_PROMPT.format(
            project_name=project_name,
            description=description or "No description",
            main_entity=main_entity,
            entities_json=json.dumps([e.get("name") for e in entities], indent=2),
            app_type=app_type,
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, f"Designing UX for {app_type} floorplan...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=UX_DESIGN_SYSTEM_PROMPT,
            state=state,
            required_keys=["floorplan", "navigation_structure"],
            max_retries=3,
            agent_name=agent_name,
        )
        
        if result:
            ux_design_spec = result
            log_progress(state, f"✅ UX design complete: {result.get('floorplan')} floorplan")
        else:
            log_progress(state, "⚠️ LLM generation failed - using default UX design")
            ux_design_spec = {
                "floorplan": app_type,
                "navigation_structure": {"type": "hierarchical", "levels": 2, "routes": []},
                "ux_patterns": ["list-detail", "object-page"],
                "responsive_breakpoints": {"desktop": 1024, "tablet": 768, "mobile": 480},
                "wireframes": []
            }
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "UX design complete.")
        
        return {
            "ux_design_spec": ux_design_spec,
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
