"""
Agent: Domain Modeling (DDD)

Applies Domain-Driven Design principles to define bounded contexts,
aggregates, entities, value objects, and ubiquitous language.

ARCHITECTURE IMPROVEMENTS (2026-03-15):
- Added timeout wrapper
- Proper retry counter increment
- Returns partial state
- Records agent_history
- Handles exceptions properly
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


DOMAIN_MODELING_SYSTEM_PROMPT = """You are a Domain-Driven Design (DDD) expert with 15+ years of experience.
Your task is to analyze business requirements and apply DDD principles to create a robust domain model.

DDD PRINCIPLES:
1. Bounded Contexts: Identify clear boundaries between different parts of the domain
2. Aggregates: Group entities that must be consistent together
3. Aggregate Roots: Identify the main entity that controls access to the aggregate
4. Entities vs Value Objects: Distinguish between objects with identity vs immutable values
5. Ubiquitous Language: Define a common vocabulary for the domain
6. Domain Events: Identify significant business events

OUTPUT FORMAT:
Return valid JSON:
{
  "bounded_contexts": [
    {
      "name": "string",
      "description": "string",
      "aggregates": ["aggregate_name"],
      "responsibilities": ["responsibility"]
    }
  ],
  "aggregates": [
    {
      "name": "string",
      "root_entity": "string",
      "entities": ["entity_name"],
      "value_objects": ["value_object_name"],
      "invariants": ["business_rule"]
    }
  ],
  "ubiquitous_language": {
    "term": "definition"
  },
  "domain_events": [
    {
      "name": "string",
      "description": "string",
      "aggregate": "string"
    }
  ]
}

Return ONLY valid JSON."""


DOMAIN_MODELING_PROMPT = """Analyze the following business requirements and apply Domain-Driven Design principles.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Relationships:
{relationships_json}

Business Rules:
{business_rules_json}

Tasks:
1. Identify bounded contexts (logical boundaries in the domain)
2. Define aggregates (groups of entities that must be consistent)
3. Identify aggregate roots (main entities that control access)
4. Classify entities vs value objects
5. Create ubiquitous language glossary
6. Identify domain events

Respond with ONLY valid JSON."""


@with_timeout(timeout_seconds=120)  # 2 minutes for DDD analysis
async def domain_modeling_agent(state: BuilderState) -> dict[str, Any]:
    """
    Domain Modeling Agent - Applies DDD principles.
    
    Generates:
    - Bounded contexts
    - Aggregates and aggregate roots
    - Entity vs Value Object classification
    - Ubiquitous language glossary
    - Domain events
    """
    agent_name = "domain_modeling"
    logger.info(f"Starting {agent_name} Agent (DDD)")
    
    started_at = datetime.utcnow().isoformat()
    
    # =========================================================================
    # Check retry count and fail if max retries exhausted
    # =========================================================================
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
    
    log_progress(state, "Starting domain modeling phase (DDD)...")
    
    try:
        # Get context
        project_name = state.get("project_name", "App")
        description = state.get("project_description", "")
        entities = state.get("entities", [])
        relationships = state.get("relationships", [])
        business_rules = state.get("business_rules", [])
        
        if not entities:
            log_progress(state, "No entities found - using minimal domain model")
            domain_model = {
                "bounded_contexts": [{"name": "Core", "description": "Core business domain", "aggregates": []}],
                "ubiquitous_language": {},
                "domain_events": [],
                "aggregates": []
            }
        else:
            # Retrieve RAG context
            rag_docs = await retrieve_for_agent("domain_modeling", f"DDD bounded contexts aggregates {project_name}")
            rag_context = "\n\n".join(rag_docs) if rag_docs else ""
            
            prompt = DOMAIN_MODELING_PROMPT.format(
                project_name=project_name,
                description=description or "No description provided",
                entities_json=json.dumps(entities, indent=2),
                relationships_json=json.dumps(relationships, indent=2),
                business_rules_json=json.dumps(business_rules, indent=2),
            )
            
            if rag_context:
                prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
            
            log_progress(state, f"Analyzing {len(entities)} entities for DDD patterns...")
            
            result = await generate_with_retry(
                prompt=prompt,
                system_prompt=DOMAIN_MODELING_SYSTEM_PROMPT,
                state=state,
                required_keys=["bounded_contexts", "aggregates"],
                max_retries=3,
                agent_name="domain_modeling",
            )
            
            if result:
                domain_model = result
                log_progress(state, f"✅ Identified {len(result.get('bounded_contexts', []))} bounded contexts")
                log_progress(state, f"✅ Defined {len(result.get('aggregates', []))} aggregates")
            else:
                log_progress(state, "⚠️ LLM generation failed - using minimal domain model")
                domain_model = {
                    "bounded_contexts": [{"name": "Core", "description": "Core business domain", "aggregates": []}],
                    "ubiquitous_language": {},
                    "domain_events": [],
                    "aggregates": []
                }
        
        # Success path
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        log_progress(state, "Domain modeling complete.")
        
        # Return only changed keys
        return {
            # Agent outputs
            "domain_model": domain_model,
            
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with exception: {e}")
        
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": str(e),
                "logs": state.get("current_logs", []),
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": True,
            
            # Validation errors
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            
            # Metadata
            "current_agent": agent_name,
            "updated_at": completed_at,
        }
