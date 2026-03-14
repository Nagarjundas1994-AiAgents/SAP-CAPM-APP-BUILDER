"""
Agent: Observability

Dynatrace APM config, SLOs, alerting rules, tracing setup.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


OBSERVABILITY_SYSTEM_PROMPT = """You are an observability and monitoring expert for SAP BTP applications.
Your task is to design comprehensive monitoring with SLOs, alerting, and distributed tracing.

OBSERVABILITY PRINCIPLES:
1. Monitoring: Application metrics, health checks, performance
2. Tracing: Distributed tracing for request flows
3. SLOs: Service Level Objectives (availability, latency, error rate)
4. Alerting: Proactive alerts for SLO violations
5. Dashboards: Real-time visibility into system health

OUTPUT FORMAT:
Return valid JSON:
{
  "monitoring_enabled": true,
  "tracing_enabled": true,
  "slos": [
    {
      "name": "string",
      "metric": "availability/latency/error_rate",
      "target": "99.9%/200ms/1%",
      "window": "30d"
    }
  ],
  "alerts": [
    {
      "name": "string",
      "condition": "string",
      "severity": "critical/warning/info",
      "notification_channel": "email/slack/pagerduty"
    }
  ],
  "dashboards": [
    {
      "name": "string",
      "widgets": ["metric1", "metric2"]
    }
  ]
}

Return ONLY valid JSON."""


OBSERVABILITY_PROMPT = """Design an observability strategy for this SAP CAP application.

Project: {project_name}
Description: {description}

Services:
{services_json}

Tasks:
1. Define SLOs (availability, latency, error rate targets)
2. Configure alerting rules for SLO violations
3. Set up distributed tracing
4. Design monitoring dashboards

Respond with ONLY valid JSON."""


async def observability_agent(state: BuilderState) -> BuilderState:
    """
    Observability Agent - Dynatrace, alerting, SLOs, tracing.
    
    Generates:
    - Dynatrace configuration
    - SLO definitions
    - Alerting rules
    - Distributed tracing setup
    - Monitoring dashboards
    """
    logger.info("Starting Observability Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "observability"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting observability phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    services = state.get("services", [])
    
    # Retrieve RAG context
    rag_docs = await retrieve_for_agent("observability", f"Dynatrace monitoring SLO alerting {project_name}")
    rag_context = "\n\n".join(rag_docs) if rag_docs else ""
    
    prompt = OBSERVABILITY_PROMPT.format(
        project_name=project_name,
        description=description or "No description provided",
        services_json=json.dumps(services[:5], indent=2) if services else "[]",
    )
    
    if rag_context:
        prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
    
    log_progress(state, "Generating observability configuration...")
    
    result = await generate_with_retry(
        prompt=prompt,
        system_prompt=OBSERVABILITY_SYSTEM_PROMPT,
        state=state,
        required_keys=["monitoring_enabled", "slos"],
        max_retries=3,
        agent_name="observability",
    )
    
    if result:
        observability_config = result
        log_progress(state, f"✅ Defined {len(result.get('slos', []))} SLOs")
        log_progress(state, f"✅ Configured {len(result.get('alerts', []))} alerting rules")
    else:
        log_progress(state, "⚠️ LLM generation failed - using minimal observability config")
        observability_config = {
            "monitoring_enabled": True,
            "tracing_enabled": True,
            "slos": [
                {"name": "Availability", "metric": "availability", "target": "99.9%", "window": "30d"},
                {"name": "Latency", "metric": "latency", "target": "200ms", "window": "30d"}
            ],
            "alerts": [],
            "dashboards": []
        }
    
    state["observability_config"] = observability_config
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "observability",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Observability complete.")
    return state
