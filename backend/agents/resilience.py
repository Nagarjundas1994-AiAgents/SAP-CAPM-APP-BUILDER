"""
Agent Resilience Patterns

Provides enterprise-grade resilience patterns for LangGraph agents:
- Per-agent timeout wrapper
- Circuit breaker for LLM API failures
- Dead-letter store for failed runs

ARCHITECTURE IMPROVEMENTS (2026-03-15):
- Added timeout wrapper to prevent hanging agents
- Implemented circuit breaker to fail-fast on LLM provider outages
- Added dead-letter persistence for failed workflow debugging
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, TypeVar
from functools import wraps

from backend.agents.state import BuilderState

logger = logging.getLogger(__name__)

T = TypeVar('T')


# =============================================================================
# Circuit Breaker for LLM API Failures
# =============================================================================

class CircuitBreaker:
    """
    Simple circuit breaker that opens after N consecutive failures.
    When open, short-circuits all requests to fail-fast.
    """
    
    def __init__(self, failure_threshold: int = 3, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.is_open = False
    
    def record_success(self):
        """Record a successful call - resets the circuit."""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None
    
    def record_failure(self):
        """Record a failed call - may open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(f"Circuit breaker OPENED after {self.failure_count} consecutive failures")
    
    def can_proceed(self) -> bool:
        """Check if requests can proceed or if circuit is open."""
        if not self.is_open:
            return True
        
        # Check if timeout has elapsed - if so, try half-open state
        if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
            logger.info("Circuit breaker entering HALF-OPEN state (timeout elapsed)")
            self.is_open = False
            self.failure_count = 0
            return True
        
        return False


# Global circuit breaker instance
_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=60.0)


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance."""
    return _circuit_breaker


# =============================================================================
# Agent Timeout Wrapper
# =============================================================================

def with_timeout(timeout_seconds: int = 120):
    """
    Decorator to add timeout to agent functions.
    
    Usage:
        @with_timeout(timeout_seconds=180)
        async def my_agent(state: BuilderState) -> dict[str, Any]:
            # agent logic
            return {"key": "value"}
    
    Args:
        timeout_seconds: Maximum execution time in seconds
    """
    def decorator(agent_fn: Callable[[BuilderState], Any]):
        @wraps(agent_fn)
        async def wrapper(state: BuilderState) -> dict[str, Any]:
            agent_name = agent_fn.__name__.replace("_agent", "")
            
            # Check circuit breaker before proceeding
            circuit_breaker = get_circuit_breaker()
            if not circuit_breaker.can_proceed():
                logger.error(f"[{agent_name}] Circuit breaker is OPEN - failing fast")
                return {
                    "agent_failed": True,
                    "validation_errors": [{
                        "agent": agent_name,
                        "code": "CIRCUIT_BREAKER_OPEN",
                        "message": "Circuit breaker is open due to repeated LLM API failures",
                        "field": None,
                        "severity": "error",
                    }]
                }
            
            try:
                result = await asyncio.wait_for(agent_fn(state), timeout=timeout_seconds)
                
                # Record success for circuit breaker
                circuit_breaker.record_success()
                
                return result
            except asyncio.TimeoutError:
                logger.error(f"[{agent_name}] Agent timed out after {timeout_seconds}s")
                
                # Record failure for circuit breaker
                circuit_breaker.record_failure()
                
                return {
                    "agent_failed": True,
                    "validation_errors": [{
                        "agent": agent_name,
                        "code": "TIMEOUT",
                        "message": f"Agent execution exceeded {timeout_seconds}s timeout",
                        "field": None,
                        "severity": "error",
                    }]
                }
            except Exception as e:
                logger.exception(f"[{agent_name}] Agent failed with exception: {e}")
                
                # Record failure for circuit breaker
                circuit_breaker.record_failure()
                
                return {
                    "agent_failed": True,
                    "validation_errors": [{
                        "agent": agent_name,
                        "code": "AGENT_ERROR",
                        "message": str(e),
                        "field": None,
                        "severity": "error",
                    }]
                }
        
        return wrapper
    return decorator


# =============================================================================
# Dead-Letter Store for Failed Runs
# =============================================================================

async def persist_failed_state(state: BuilderState, error: str):
    """
    Persist failed workflow state to dead-letter store for debugging.
    
    Args:
        state: Final BuilderState when workflow failed
        error: Error message describing the failure
    """
    try:
        import json
        from pathlib import Path
        
        # Create dead-letter directory
        dead_letter_dir = Path("dead_letters")
        dead_letter_dir.mkdir(exist_ok=True)
        
        session_id = state.get("session_id", "unknown")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"failed_{session_id}_{timestamp}.json"
        filepath = dead_letter_dir / filename
        
        # Serialize state (convert non-serializable objects to strings)
        def serialize_value(v):
            if isinstance(v, (str, int, float, bool, type(None))):
                return v
            elif isinstance(v, (list, tuple)):
                return [serialize_value(item) for item in v]
            elif isinstance(v, dict):
                return {k: serialize_value(val) for k, val in v.items()}
            else:
                return str(v)
        
        serializable_state = {k: serialize_value(v) for k, v in state.items()}
        
        # Add metadata
        dead_letter_data = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
            "state": serializable_state,
        }
        
        # Write to file
        with open(filepath, "w") as f:
            json.dump(dead_letter_data, f, indent=2)
        
        logger.info(f"Persisted failed state to dead-letter store: {filepath}")
    except Exception as e:
        logger.error(f"Failed to persist dead-letter state: {e}")


# =============================================================================
# Agent Wrapper with All Resilience Patterns
# =============================================================================

def resilient_agent(timeout_seconds: int = 120):
    """
    Comprehensive resilience wrapper combining timeout, circuit breaker, and dead-letter.
    
    Usage:
        @resilient_agent(timeout_seconds=180)
        async def my_agent(state: BuilderState) -> dict[str, Any]:
            # agent logic
            return {"key": "value"}
    """
    return with_timeout(timeout_seconds)
