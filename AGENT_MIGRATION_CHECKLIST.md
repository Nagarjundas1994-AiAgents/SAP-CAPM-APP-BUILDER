# Agent Migration Checklist

**Checklist for updating existing agents to new architecture patterns**

---

## Overview

This checklist helps you migrate existing agents to the new architecture with:
- ✅ Annotated reducers (no data loss)
- ✅ Proper retry counter increments (no infinite loops)
- ✅ Partial state returns (better performance)
- ✅ Timeout wrappers (no hanging)
- ✅ Circuit breaker support (fail-fast)

---

## Migration Steps (Per Agent)

### Step 1: Add Timeout Wrapper

**Before**:
```python
async def my_agent(state: BuilderState) -> BuilderState:
    # agent logic
    return state
```

**After**:
```python
from backend.agents.resilience import with_timeout

@with_timeout(timeout_seconds=180)  # Adjust timeout as needed
async def my_agent(state: BuilderState) -> dict[str, Any]:
    # agent logic
    return {"key": "value"}  # Return partial state
```

**Checklist**:
- [ ] Import `with_timeout` from `backend.agents.resilience`
- [ ] Add `@with_timeout()` decorator above function
- [ ] Set appropriate timeout (120s default, 180s for LLM-heavy, 300s for complex)
- [ ] Change return type from `BuilderState` to `dict[str, Any]`

---

### Step 2: Add Retry Counter Check

**Add at the start of the agent**:
```python
async def my_agent(state: BuilderState) -> dict[str, Any]:
    agent_name = "my_agent"  # Use actual agent name
    
    # Check retry count
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
    
    # Rest of agent logic...
```

**Checklist**:
- [ ] Add `agent_name` variable with correct agent name
- [ ] Add retry count check at start of function
- [ ] Return `agent_failed: True` if max retries exhausted
- [ ] Add validation error with appropriate message

---

### Step 3: Increment Retry Counter in Return

**Before**:
```python
return {
    **state,
    "my_output": result,
}
```

**After**:
```python
# Increment retry counter
new_retry_counts = state.get("retry_counts", {}).copy()
new_retry_counts[agent_name] = retry_count + 1

return {
    "my_output": result,
    "retry_counts": new_retry_counts,
    "needs_correction": False,
}
```

**Checklist**:
- [ ] Copy `retry_counts` dict from state
- [ ] Increment counter for this agent
- [ ] Include `retry_counts` in return dict
- [ ] Set `needs_correction: False` on success
- [ ] Set `needs_correction: True` on failure

---

### Step 4: Return Partial State (Not Full Copy)

**Before**:
```python
return {
    **state,  # ❌ Copies entire state
    "my_output": result,
    "needs_correction": False,
}
```

**After**:
```python
return {
    # Only return changed keys
    "my_output": result,
    "retry_counts": new_retry_counts,
    "needs_correction": False,
    "agent_history": [execution_record],
    "current_agent": agent_name,
}
```

**Checklist**:
- [ ] Remove `{**state, ...}` pattern
- [ ] Return only keys that changed
- [ ] Include `agent_history` entry
- [ ] Include `retry_counts` update
- [ ] Include `needs_correction` flag
- [ ] Include `current_agent` name

---

### Step 5: Use Annotated Reducers for Lists

**Before**:
```python
# Manual list append
existing_errors = state.get("validation_errors", [])
new_errors = existing_errors + [new_error]

return {
    **state,
    "validation_errors": new_errors,
}
```

**After**:
```python
# Annotated reducer auto-appends
return {
    "validation_errors": [new_error],  # Automatically appends
}
```

**Checklist**:
- [ ] Remove manual list concatenation
- [ ] Return only new items to append
- [ ] Trust Annotated reducer to merge correctly
- [ ] Applies to: `agent_history`, `validation_errors`, `current_logs`, `artifacts_*`, etc.

---

### Step 6: Add Agent History Tracking

**Add to success path**:
```python
from datetime import datetime

started_at = datetime.utcnow().isoformat()

# ... do work ...

completed_at = datetime.utcnow().isoformat()
duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)

return {
    "agent_history": [{
        "agent_name": agent_name,
        "status": "completed",
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_ms": duration_ms,
        "error": None,
        "logs": None,
    }],
    # ... other keys ...
}
```

**Add to failure path**:
```python
except Exception as e:
    completed_at = datetime.utcnow().isoformat()
    duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
    
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
        "needs_correction": True,
        # ... other keys ...
    }
```

**Checklist**:
- [ ] Record `started_at` at function start
- [ ] Record `completed_at` at function end
- [ ] Calculate `duration_ms`
- [ ] Add `agent_history` entry to return dict
- [ ] Set `status: "completed"` on success
- [ ] Set `status: "failed"` on error
- [ ] Include error message in failure case

---

### Step 7: Handle Exceptions Properly

**Before**:
```python
async def my_agent(state: BuilderState) -> BuilderState:
    result = await risky_operation()  # May raise exception
    return {**state, "result": result}
```

**After**:
```python
async def my_agent(state: BuilderState) -> dict[str, Any]:
    try:
        result = await risky_operation()
        return {
            "result": result,
            "needs_correction": False,
        }
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed: {e}")
        return {
            "needs_correction": True,
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }],
        }
```

**Checklist**:
- [ ] Wrap risky operations in try/except
- [ ] Log exception with `logger.exception()`
- [ ] Return error state (don't raise)
- [ ] Set `needs_correction: True`
- [ ] Add validation error
- [ ] Include agent_history with `status: "failed"`

---

## Agent-by-Agent Migration Status

### Phase 1: Core Agents (Priority 1)
- [ ] `requirements_agent` - backend/agents/requirements.py
- [ ] `enterprise_architecture_agent` - backend/agents/enterprise_architecture.py
- [ ] `domain_modeling_agent` - backend/agents/domain_modeling.py
- [ ] `data_modeling_agent` - backend/agents/data_modeling.py
- [ ] `validation_agent` - backend/agents/validation.py

### Phase 2: Service Layer (Priority 2)
- [ ] `service_exposure_agent` - backend/agents/service_exposure.py
- [ ] `integration_design_agent` - backend/agents/integration_design.py
- [ ] `business_logic_agent` - backend/agents/business_logic.py
- [ ] `integration_agent` - backend/agents/integration.py

### Phase 3: UI Layer (Priority 3)
- [ ] `ux_design_agent` - backend/agents/ux_design.py
- [ ] `fiori_ui_agent` - backend/agents/fiori_ui.py
- [ ] `i18n_agent` - backend/agents/i18n.py

### Phase 4: Cross-Cutting Concerns (Priority 4)
- [ ] `error_handling_agent` - backend/agents/error_handling.py
- [ ] `audit_logging_agent` - backend/agents/audit_logging.py
- [ ] `api_governance_agent` - backend/agents/api_governance.py
- [ ] `security_agent` - backend/agents/security.py
- [ ] `multitenancy_agent` - backend/agents/multitenancy.py
- [ ] `feature_flags_agent` - backend/agents/feature_flags.py

### Phase 5: Quality & Deployment (Priority 5)
- [ ] `compliance_check_agent` - backend/agents/compliance_check.py
- [ ] `performance_review_agent` - backend/agents/performance_review.py
- [ ] `testing_agent` - backend/agents/testing.py
- [ ] `ci_cd_agent` - backend/agents/ci_cd.py
- [ ] `deployment_agent` - backend/agents/deployment.py
- [ ] `observability_agent` - backend/agents/observability.py

### Phase 6: Infrastructure (Priority 6)
- [ ] `db_migration_agent` - backend/agents/db_migration.py
- [ ] `extension_agent` - backend/agents/extension.py
- [ ] `documentation_agent` - backend/agents/documentation.py
- [ ] `project_assembly_agent` - backend/agents/project_assembly.py
- [ ] `project_verification_agent` - backend/agents/project_verification.py

---

## Testing After Migration

### 1. Unit Test Each Agent
```bash
pytest backend/agents/test_my_agent.py -v
```

**Verify**:
- [ ] Agent returns partial state (not full copy)
- [ ] Retry counter increments correctly
- [ ] Agent history is recorded
- [ ] Timeout wrapper works
- [ ] Max retries triggers agent_failed

### 2. Integration Test Full Workflow
```bash
pytest backend/tests/test_workflow.py -v
```

**Verify**:
- [ ] All agents execute in correct order
- [ ] State persists between agents
- [ ] Retry logic works end-to-end
- [ ] Circuit breaker opens on failures
- [ ] LangSmith traces capture all agents

### 3. Load Test Concurrent Requests
```bash
pytest backend/tests/test_concurrent.py -v
```

**Verify**:
- [ ] Thread-safe graph singleton works
- [ ] No race conditions on state
- [ ] Circuit breaker shared correctly
- [ ] Checkpointer handles concurrent writes

---

## Common Migration Issues

### Issue 1: "Agent returns full state copy"
**Symptom**: Performance degradation, large memory usage  
**Fix**: Remove `{**state, ...}` pattern, return only changed keys

### Issue 2: "Retry counter not incrementing"
**Symptom**: Infinite loops, workflow never completes  
**Fix**: Add retry counter increment in return dict

### Issue 3: "List fields overwriting"
**Symptom**: agent_history only has 1 entry, validation_errors missing  
**Fix**: Trust Annotated reducers, return only new items

### Issue 4: "Agent hangs indefinitely"
**Symptom**: Workflow stuck, no progress  
**Fix**: Add `@with_timeout()` decorator

### Issue 5: "Circuit breaker always open"
**Symptom**: All agents fail immediately  
**Fix**: Check LLM provider status, wait 60s for reset

---

## Validation Checklist (Per Agent)

After migrating an agent, verify:

- [ ] ✅ Has `@with_timeout()` decorator
- [ ] ✅ Checks retry count at start
- [ ] ✅ Increments retry counter in return
- [ ] ✅ Returns partial state (not full copy)
- [ ] ✅ Uses Annotated reducers for lists
- [ ] ✅ Records agent_history entry
- [ ] ✅ Handles exceptions with try/except
- [ ] ✅ Returns error state (doesn't raise)
- [ ] ✅ Sets needs_correction flag
- [ ] ✅ Logs progress with log_progress()
- [ ] ✅ Unit tests pass
- [ ] ✅ Integration tests pass

---

## Rollout Strategy

### Week 1: Core Agents (5 agents)
Migrate and test requirements, enterprise_architecture, domain_modeling, data_modeling, validation

### Week 2: Service Layer (4 agents)
Migrate and test service_exposure, integration_design, business_logic, integration

### Week 3: UI Layer (3 agents)
Migrate and test ux_design, fiori_ui, i18n

### Week 4: Cross-Cutting (6 agents)
Migrate and test error_handling, audit_logging, api_governance, security, multitenancy, feature_flags

### Week 5: Quality & Deployment (6 agents)
Migrate and test compliance_check, performance_review, testing, ci_cd, deployment, observability

### Week 6: Infrastructure (5 agents)
Migrate and test db_migration, extension, documentation, project_assembly, project_verification

### Week 7: Integration Testing
Full end-to-end testing with all 28 agents

### Week 8: Production Deployment
Deploy to production with monitoring

---

## Monitoring After Migration

### LangSmith Traces
- Check all 28 agents appear in traces
- Verify retry logic shows in trace tree
- Monitor token usage per agent
- Track latency per agent

### Circuit Breaker Metrics
- Monitor failure count
- Track open/close events
- Alert on circuit breaker open

### Dead-Letter Store
- Check for failed runs in `dead_letters/`
- Analyze common failure patterns
- Replay failed runs after fixes

### Performance Metrics
- Compare before/after latency
- Monitor memory usage (should decrease)
- Track workflow completion rate
- Measure retry frequency

---

## Resources

- [Agent Development Guide](./AGENT_DEVELOPMENT_GUIDE.md)
- [Architecture Fixes Document](./LANGGRAPH_ARCHITECTURE_FIXES.md)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [State Reducers Guide](https://langchain-ai.github.io/langgraph/how-tos/state-reducers/)

---

**Migration Progress**: 0/28 agents completed

**Target Completion**: Week 8

**Status**: 🟡 In Progress
