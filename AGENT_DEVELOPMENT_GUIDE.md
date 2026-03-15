# Agent Development Guide

**Quick Reference for Developing LangGraph Agents**

---

## Agent Template (Correct Pattern)

```python
"""
Agent Name: my_agent
Purpose: Brief description of what this agent does
"""

import logging
from datetime import datetime
from backend.agents.state import BuilderState
from backend.agents.resilience import with_timeout
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


@with_timeout(timeout_seconds=180)  # Add timeout wrapper
async def my_agent(state: BuilderState) -> dict[str, Any]:
    """
    Agent description.
    
    Args:
        state: Current BuilderState
        
    Returns:
        Partial state dict with only changed keys
    """
    agent_name = "my_agent"
    log_progress(state, f"[{agent_name}] Starting...")
    
    # =========================================================================
    # 1. Check retry count and fail if max retries exhausted
    # =========================================================================
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{agent_name}] Max retries ({max_retries}) exhausted")
        return {
            "agent_failed": True,
            "validation_errors": [{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {max_retries} retries",
                "field": None,
                "severity": "error",
            }]
        }
    
    # =========================================================================
    # 2. Record agent start in agent_history
    # =========================================================================
    started_at = datetime.utcnow().isoformat()
    
    # =========================================================================
    # 3. Do the actual work
    # =========================================================================
    try:
        # Your agent logic here
        result = await do_agent_work(state)
        
        # =========================================================================
        # 4. Record agent completion
        # =========================================================================
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        log_progress(state, f"[{agent_name}] Completed successfully")
        
        # =========================================================================
        # 5. Return ONLY changed keys (not full state copy)
        # =========================================================================
        # Increment retry counter
        new_retry_counts = state.get("retry_counts", {}).copy()
        new_retry_counts[agent_name] = retry_count + 1
        
        return {
            # Agent outputs
            "my_output_key": result,
            
            # Agent execution tracking
            "agent_history": [{
                "agent_name": agent_name,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": None,
                "logs": None,
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": False,
            
            # Current agent
            "current_agent": agent_name,
        }
    
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed with error: {e}")
        
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
                "logs": None,
            }],
            
            # Retry tracking
            "retry_counts": new_retry_counts,
            "needs_correction": True,  # Trigger retry
            
            # Validation errors
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
            
            # Current agent
            "current_agent": agent_name,
        }


async def do_agent_work(state: BuilderState) -> Any:
    """Helper function with actual agent logic."""
    # Your implementation here
    pass
```

---

## Critical Rules

### ✅ DO

1. **Return only changed keys** - Don't copy full state with `{**state, ...}`
2. **Increment retry_counts** - Always increment on every execution
3. **Use Annotated reducers** - Lists automatically append, don't manually merge
4. **Add timeout wrapper** - Use `@with_timeout()` decorator
5. **Record agent_history** - Track start, completion, duration, errors
6. **Set needs_correction** - Set to `True` on failure to trigger retry
7. **Log progress** - Use `log_progress()` for real-time SSE updates
8. **Handle exceptions** - Catch and return error state, don't raise

### ❌ DON'T

1. **Don't mutate state in routers** - Routers are pure functions
2. **Don't return full state copy** - Return only `{"changed_key": value}`
3. **Don't forget retry_counts** - Causes infinite loops
4. **Don't manually append to lists** - Use Annotated reducers
5. **Don't use fire-and-forget tasks** - Use `await` for side effects
6. **Don't hardcode timeouts** - Use `@with_timeout()` decorator
7. **Don't skip agent_history** - Required for progress tracking
8. **Don't raise exceptions** - Return error state instead

---

## State Fields Reference

### Fields with Annotated Reducers (Auto-Append)
These fields automatically append when you return them:

```python
agent_history: Annotated[list[AgentExecution], operator.add]
validation_errors: Annotated[list[ValidationError], operator.add]
current_logs: Annotated[list[str], operator.add]
correction_history: Annotated[list[dict[str, Any]], operator.add]
auto_fixed_errors: Annotated[list[dict[str, Any]], operator.add]
validation_rules_applied: Annotated[list[str], operator.add]
artifacts_db: Annotated[list[GeneratedFile], operator.add]
artifacts_srv: Annotated[list[GeneratedFile], operator.add]
artifacts_app: Annotated[list[GeneratedFile], operator.add]
artifacts_deployment: Annotated[list[GeneratedFile], operator.add]
artifacts_docs: Annotated[list[GeneratedFile], operator.add]
verification_checks: Annotated[list[VerificationCheck], operator.add]
```

**Usage**:
```python
# Just return the new item(s) - they'll be appended automatically
return {
    "agent_history": [new_execution],  # Appends to existing list
    "validation_errors": [new_error],  # Appends to existing list
}
```

### Fields with Manual Merge (Dicts)
These fields need manual merging:

```python
retry_counts: dict[str, int]
gate_decisions: dict[str, str]
retrieved_docs: dict[str, list]
parallel_phase_results: dict[str, dict]
model_tier: dict[str, str]
```

**Usage**:
```python
# Copy dict, update, and return
new_retry_counts = state.get("retry_counts", {}).copy()
new_retry_counts["my_agent"] = retry_count + 1

return {
    "retry_counts": new_retry_counts,  # Replaces entire dict
}
```

---

## Common Patterns

### Pattern 1: LLM Generation with Retry
```python
from backend.agents.llm_utils import generate_with_llm

result = await generate_with_llm(
    state=state,
    agent_name="my_agent",
    prompt="Generate something...",
    schema=MySchema,
    max_retries=3,
)

if result is None:
    # LLM generation failed after retries
    return {
        "needs_correction": True,
        "validation_errors": [{"agent": "my_agent", ...}],
    }
```

### Pattern 2: Validation with Self-Healing
```python
validation_errors = validate_output(result)

if validation_errors:
    return {
        "needs_correction": True,
        "correction_agent": "my_agent",  # Loop back to this agent
        "validation_errors": validation_errors,
    }
```

### Pattern 3: Conditional Logic Based on Complexity
```python
complexity = state.get("complexity_level", "standard")

if complexity in ["enterprise", "full_stack"]:
    # Do advanced work
    result = await advanced_generation(state)
else:
    # Do basic work
    result = await basic_generation(state)
```

### Pattern 4: Accessing Previous Agent Outputs
```python
# Read outputs from previous agents
schema_cds = state.get("generated_schema_cds", "")
service_cds = state.get("generated_service_cds", "")

# Use them in your logic
combined_context = f"{schema_cds}\n\n{service_cds}"
```

---

## Testing Your Agent

### Unit Test Template
```python
import pytest
from backend.agents.my_agent import my_agent
from backend.agents.state import create_initial_state

@pytest.mark.asyncio
async def test_my_agent_success():
    """Test agent succeeds with valid input."""
    state = create_initial_state(
        session_id="test-123",
        project_name="test-project",
    )
    state["entities"] = [...]  # Add required inputs
    
    result = await my_agent(state)
    
    assert "my_output_key" in result
    assert result["needs_correction"] is False
    assert len(result["agent_history"]) == 1
    assert result["agent_history"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_my_agent_retry():
    """Test agent retries on failure."""
    state = create_initial_state(
        session_id="test-123",
        project_name="test-project",
    )
    state["retry_counts"] = {"my_agent": 2}  # Simulate 2 prior retries
    
    result = await my_agent(state)
    
    assert result["retry_counts"]["my_agent"] == 3  # Incremented


@pytest.mark.asyncio
async def test_my_agent_max_retries():
    """Test agent fails after max retries."""
    state = create_initial_state(
        session_id="test-123",
        project_name="test-project",
    )
    state["retry_counts"] = {"my_agent": 5}  # At max retries
    state["MAX_RETRIES"] = 5
    
    result = await my_agent(state)
    
    assert result["agent_failed"] is True
    assert len(result["validation_errors"]) > 0
```

---

## Debugging Tips

### 1. Enable LangSmith Tracing
Set in `.env`:
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key-here
```

View traces at: https://smith.langchain.com/

### 2. Check Agent History
```python
agent_history = state.get("agent_history", [])
for execution in agent_history:
    print(f"{execution['agent_name']}: {execution['status']} ({execution['duration_ms']}ms)")
```

### 3. Inspect Validation Errors
```python
errors = state.get("validation_errors", [])
for error in errors:
    print(f"[{error['agent']}] {error['code']}: {error['message']}")
```

### 4. Check Retry Counts
```python
retry_counts = state.get("retry_counts", {})
for agent, count in retry_counts.items():
    print(f"{agent}: {count} retries")
```

### 5. Monitor Circuit Breaker
```python
from backend.agents.resilience import get_circuit_breaker

cb = get_circuit_breaker()
print(f"Circuit breaker: {'OPEN' if cb.is_open else 'CLOSED'}")
print(f"Failure count: {cb.failure_count}")
```

---

## Performance Best Practices

1. **Return minimal state** - Only changed keys, not full copy
2. **Use async/await** - Don't block the event loop
3. **Batch LLM calls** - Combine multiple prompts when possible
4. **Cache expensive operations** - Store in state for reuse
5. **Log sparingly** - Use `log_progress()` for user-facing updates only
6. **Validate early** - Fail fast on invalid inputs
7. **Use timeouts** - Prevent hanging on slow LLM APIs
8. **Monitor circuit breaker** - Fail fast when LLM provider is down

---

## Common Errors and Solutions

### Error: "Infinite loop detected"
**Cause**: Agent not incrementing `retry_counts`  
**Solution**: Always increment `retry_counts` in return value

### Error: "List field overwrites previous values"
**Cause**: Field not using Annotated reducer  
**Solution**: Add `Annotated[list[T], operator.add]` to state.py

### Error: "Agent timeout after 120s"
**Cause**: Agent taking too long  
**Solution**: Increase timeout with `@with_timeout(timeout_seconds=300)`

### Error: "Circuit breaker is OPEN"
**Cause**: LLM provider had 3+ consecutive failures  
**Solution**: Wait 60s for auto-reset, or check LLM provider status

### Error: "State mutation in router discarded"
**Cause**: Trying to mutate state in router function  
**Solution**: Move mutation to agent, router should only return string

---

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [State Reducers Guide](https://langchain-ai.github.io/langgraph/how-tos/state-reducers/)
- [Checkpointing Guide](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
- [LangSmith Tracing](https://docs.smith.langchain.com/)
- [Architecture Fixes Document](./LANGGRAPH_ARCHITECTURE_FIXES.md)

---

**Happy Agent Development! 🚀**
