"""
Agent: Domain Modeling (DDD)

Applies Domain-Driven Design principles to define bounded contexts,
aggregates, entities, value objects, and ubiquitous language.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
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


async def domain_modeling_agent(state: BuilderState) -> BuilderState:
    """
    Domain Modeling Agent - Applies DDD principles.
    
    Generates:
    - Bounded contexts
    - Aggregates and aggregate roots
    - Entity vs Value Object classification
    - Ubiquitous language glossary
    - Domain events
    """
    logger.info("Starting Domain Modeling Agent (DDD)")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "domain_modeling"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting domain modeling phase (DDD)...")
    
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
    
    state["domain_model"] = domain_model
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "domain_modeling",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Domain modeling complete.")
    return state
