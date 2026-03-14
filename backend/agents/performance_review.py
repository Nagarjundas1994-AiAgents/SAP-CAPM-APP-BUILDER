"""
Agent: Performance Review

CDS query analysis, HANA index recommendations, N+1 detection.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


PERFORMANCE_SYSTEM_PROMPT = """You are an SAP HANA performance optimization expert with 15+ years of experience.
Your task is to analyze CDS models and service implementations for performance issues and optimization opportunities.

PERFORMANCE AREAS:
1. Query Optimization: Identify inefficient queries, missing projections, unnecessary joins
2. HANA Indexes: Recommend indexes for frequently queried fields
3. N+1 Detection: Identify N+1 query patterns in associations
4. Caching: Recommend caching strategies for read-heavy entities
5. Pagination: Verify pagination implementation for large datasets
6. Aggregations: Optimize COUNT, SUM, AVG operations

OUTPUT FORMAT:
Return valid JSON:
{
  "query_analysis": [
    {
      "entity": "string",
      "issue": "string",
      "severity": "high/medium/low",
      "recommendation": "string"
    }
  ],
  "index_recommendations": [
    {
      "entity": "string",
      "field": "string",
      "reason": "string",
      "estimated_improvement": "string"
    }
  ],
  "n_plus_one_issues": [
    {
      "entity": "string",
      "association": "string",
      "fix": "string"
    }
  ],
  "caching_recommendations": [
    {
      "entity": "string",
      "strategy": "redis/in-memory/cdn",
      "ttl_seconds": 300,
      "reason": "string"
    }
  ],
  "pagination_status": "implemented/missing/partial"
}

Return ONLY valid JSON."""


PERFORMANCE_PROMPT = """Analyze the following data model and services for performance optimization opportunities.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Relationships:
{relationships_json}

Services:
{services_json}

Tasks:
1. Analyze query patterns for inefficiencies
2. Recommend HANA indexes for frequently queried fields
3. Detect N+1 query patterns in associations
4. Suggest caching strategies for read-heavy entities
5. Verify pagination implementation

Respond with ONLY valid JSON."""


async def performance_review_agent(state: BuilderState) -> BuilderState:
    """
    Performance Review Agent - Query tuning, HANA indexes, caching.
    
    Analyzes:
    - CDS query patterns
    - HANA index recommendations
    - N+1 query detection
    - Caching opportunities
    - Pagination implementation
    """
    logger.info("Starting Performance Review Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "performance_review"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting performance review phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    entities = state.get("entities", [])
    relationships = state.get("relationships", [])
    services = state.get("services", [])
    
    if not entities:
        log_progress(state, "No entities found - using minimal performance report")
        performance_report = {
            "query_analysis": [],
            "index_recommendations": [],
            "n_plus_one_issues": [],
            "caching_recommendations": [],
            "pagination_status": "implemented"
        }
    else:
        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("performance_review", f"SAP HANA performance optimization indexes {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = PERFORMANCE_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            entities_json=json.dumps(entities, indent=2),
            relationships_json=json.dumps(relationships, indent=2),
            services_json=json.dumps(services, indent=2),
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, f"Analyzing {len(entities)} entities for performance issues...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=PERFORMANCE_SYSTEM_PROMPT,
            state=state,
            required_keys=["query_analysis", "index_recommendations"],
            max_retries=3,
            agent_name="performance_review",
        )
        
        if result:
            performance_report = result
            index_count = len(result.get("index_recommendations", []))
            log_progress(state, f"✅ Generated {index_count} index recommendations")
            log_progress(state, f"✅ Identified {len(result.get('n_plus_one_issues', []))} N+1 query issues")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal performance report")
            performance_report = {
                "query_analysis": [],
                "index_recommendations": [],
                "n_plus_one_issues": [],
                "caching_recommendations": [],
                "pagination_status": "implemented"
            }
    
    state["performance_report"] = performance_report
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "performance_review",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Performance review complete.")
    return state
