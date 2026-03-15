"""
Agent utility functions for common patterns.
"""

import logging
from typing import Any
from backend.agents.state import BuilderState

logger = logging.getLogger(__name__)


def check_and_increment_retry(state: BuilderState, agent_name: str) -> tuple[dict | None, int]:
    """
    Check retry count and increment it. Returns (failure_dict, retry_count).
    
    If failure_dict is not None, the agent should return it immediately (max retries exceeded).
    Otherwise, the agent should proceed with its work and include the retry_count in its return.
    
    Args:
        state: Current builder state
        agent_name: Name of the agent (e.g., "data_modeling")
    
    Returns:
        tuple: (failure_dict or None, current_retry_count)
        
    Example usage:
        async def my_agent(state: BuilderState) -> dict:
            from backend.agents.utils import check_and_increment_retry
            
            failure, attempt = check_and_increment_retry(state, "my_agent")
            if failure:
                return failure
            
            counts = dict(state.get("retry_counts", {}))
            counts["my_agent"] = attempt
            
            # ... do your LLM work ...
            
            return {
                "retry_counts": counts,
                "needs_correction": False,  # Always reset on success
                "my_result": result,
            }
    """
    counts = dict(state.get("retry_counts", {}))
    current_count = counts.get(agent_name, 0)
    new_count = current_count + 1
    counts[agent_name] = new_count
    
    max_retries = state.get("MAX_RETRIES", 5)
    
    if new_count > max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exceeded (attempt {new_count})")
        return {
            "agent_failed": True,
            "needs_correction": False,
            "retry_counts": counts,
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXCEEDED",
                "message": f"{agent_name} exceeded {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }, new_count
    
    logger.info(f"[{agent_name}] Attempt {new_count}/{max_retries}")
    return None, new_count
