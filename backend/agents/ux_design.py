"""
Agent: UX Design

Fiori floorplan selection, wireframes, UX patterns, and navigation design.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
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


async def ux_design_agent(state: BuilderState) -> BuilderState:
    """
    UX Design Agent - Floorplan selection, wireframes, UX patterns.
    
    Generates:
    - Fiori floorplan recommendations
    - Navigation structure
    - UX pattern guidelines
    - Wireframe specifications
    """
    logger.info("Starting UX Design Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "ux_design"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting UX design phase...")
    
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
        agent_name="ux_design",
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
    
    state["ux_design_spec"] = ux_design_spec
    state["needs_correction"] = False
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "ux_design",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "UX design complete.")
    return state
