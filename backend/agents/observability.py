"""
Agent: Observability

Dynatrace APM config, SLOs, alerting rules, tracing setup.
"""

import json
import logging
from datetime import datetime
from typing import Any

from backend.agents.state import BuilderState, GeneratedFile
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent
from backend.agents.resilience import with_timeout

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


@with_timeout(timeout_seconds=120)
async def observability_agent(state: BuilderState) -> dict[str, Any]:
    """
    Observability Agent - Dynatrace, alerting, SLOs, tracing.
    
    Generates:
    - Dynatrace configuration
    - SLO definitions
    - Alerting rules
    - Distributed tracing setup
    - Monitoring dashboards
    """
    agent_name = "observability"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{agent_name}] Starting Observability Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "observability"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting observability phase...")
    
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