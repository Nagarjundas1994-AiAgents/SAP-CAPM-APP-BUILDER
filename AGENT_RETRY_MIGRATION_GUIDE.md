# Agent Retry Migration Guide

## Quick Reference: How to Update Each Agent

Every agent needs to follow this pattern to properly handle retries and prevent infinite loops.

---

## The Pattern

### Before (Broken)
```python
async def my_agent(state: BuilderState) -> dict[str, Any]:
    agent_name = "my_agent"
    
    # ❌ Checks retry count but never increments it
    retry_count = state.get("retry_counts", {}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        return {"agent_failed": True}
    
    try:
        # ... do work ...
        
        return {
            # ❌ Never increments retry_count
            # ❌ Never resets needs_correction
            "my_result": result,
        }
    except Exception as e:
        return {
            "agent_failed": True,
            # ❌ Never increments retry_count
        }
```

### After (Fixed)
```python
async def my_agent(state: BuilderState) -> dict[str, Any]:
    from backend.agents.utils import check_and_increment_retry
    
    agent_name = "my_agent"
    
    # ✅ Check and increment retry count
    failure, attempt = check_and_increment_retry(state, agent_name)
    if failure:
        return failure
    
    # ✅ Update retry counts dict
    counts = dict(state.get("retry_counts", {}))
    counts[agent_name] = attempt
    
    try:
        # ... do work ...
        
        return {
            "retry_counts": counts,           # ✅ Include updated counts
            "needs_correction": False,        # ✅ Reset flag on success
            "my_result": result,
        }
    except Exception as e:
        logger.exception(f"[{agent_name}] Failed: {e}")
        return {
            "retry_counts": counts,           # ✅ Include updated counts
            "needs_correction": True,         # ✅ Trigger retry
            "validation_errors": [{
                "agent": agent_name,
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }]
        }
```

---

## Step-by-Step Migration

### Step 1: Add Import
At the top of the agent function:
```python
from backend.agents.utils import check_and_increment_retry
```

### Step 2: Replace Retry Check
Replace this:
```python
retry_count = state.get("retry_counts", {}).get(agent_name, 0)
max_retries = state.get("MAX_RETRIES", 5)

if retry_count >= max_retries:
    return {"agent_failed": True, ...}
```

With this:
```python
failure, attempt = check_and_increment_retry(state, agent_name)
if failure:
    return failure

counts = dict(state.get("retry_counts", {}))
counts[agent_name] = attempt
```

### Step 3: Update Success Return
Add these two keys to your success return:
```python
return {
    "retry_counts": counts,        # ✅ Add this
    "needs_correction": False,     # ✅ Add this
    # ... your other keys ...
}
```

### Step 4: Update Error Return
Add these keys to your error return:
```python
return {
    "retry_counts": counts,        # ✅ Add this
    "needs_correction": True,      # ✅ Add this (triggers retry)
    "validation_errors": [{...}],  # Keep existing error reporting
}
```

---

## Agent Priority List

### Phase 1: Core Workflow (CRITICAL)
These agents are in the main sequential flow and must be fixed first:

1. ✅ `requirements.py` - Already has retry logic
2. ⏳ `data_modeling.py` - Generates schema
3. ⏳ `domain_modeling.py` - DDD patterns
4. ⏳ `service_exposure.py` - Generates services
5. ⏳ `business_logic.py` - Generates handlers
6. ⏳ `ux_design.py` - UX planning
7. ⏳ `fiori_ui.py` - Generates UI
8. ⏳ `security.py` - Security config
9. ⏳ `deployment.py` - Deployment config
10. ⏳ `validation.py` - Final validation
11. ⏳ `project_verification.py` - Verification checks

### Phase 2: Parallel Phase 1
12. ⏳ `integration_design.py` - Integration planning

### Phase 3: Parallel Phase 2
13. ⏳ `error_handling.py` - Error handling strategy
14. ⏳ `audit_logging.py` - Audit logging
15. ⏳ `api_governance.py` - API governance

### Phase 4: Parallel Phase 3
16. ✅ `multitenancy.py` - Already fixed (UnboundLocalError)
17. ⏳ `i18n.py` - Internationalization
18. ✅ `feature_flags.py` - Already fixed (UnboundLocalError)

### Phase 5: Parallel Phase 4
19. ⏳ `testing.py` - Test generation
20. ⏳ `documentation.py` - Documentation
21. ⏳ `observability.py` - Monitoring

### Phase 6: Optional/Enhancement Agents
22. ⏳ `compliance_check.py` - Compliance scanning
23. ⏳ `performance_review.py` - Performance analysis
24. ✅ `ci_cd.py` - Already fixed (UnboundLocalError)
25. ⏳ `extension.py` - Extension points
26. ⏳ `integration.py` - Integration implementation
27. ⏳ `db_migration.py` - Database migrations
28. ⏳ `human_gate.py` - Human approval gates

---

## Common Patterns by Agent Type

### Pattern A: Simple Agent (No LLM)
```python
async def simple_agent(state: BuilderState) -> dict:
    from backend.agents.utils import check_and_increment_retry
    
    failure, attempt = check_and_increment_retry(state, "simple_agent")
    if failure:
        return failure
    
    counts = dict(state.get("retry_counts", {}))
    counts["simple_agent"] = attempt
    
    # Do simple work (no LLM calls)
    result = do_work(state)
    
    return {
        "retry_counts": counts,
        "needs_correction": False,
        "result": result,
    }
```

### Pattern B: LLM Agent with generate_with_retry
```python
async def llm_agent(state: BuilderState) -> dict:
    from backend.agents.utils import check_and_increment_retry
    
    failure, attempt = check_and_increment_retry(state, "llm_agent")
    if failure:
        return failure
    
    counts = dict(state.get("retry_counts", {}))
    counts["llm_agent"] = attempt
    
    try:
        # generate_with_retry handles LLM retries internally
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            state=state,
            required_keys=["key1", "key2"],
            max_retries=3,
            agent_name="llm_agent",
        )
        
        if result:
            return {
                "retry_counts": counts,
                "needs_correction": False,
                "my_config": result,
            }
        else:
            # LLM failed after retries
            return {
                "retry_counts": counts,
                "needs_correction": True,
                "validation_errors": [{
                    "agent": "llm_agent",
                    "code": "LLM_GENERATION_FAILED",
                    "message": "LLM generation failed after retries",
                    "field": None,
                    "severity": "error",
                }]
            }
    except Exception as e:
        logger.exception(f"[llm_agent] Failed: {e}")
        return {
            "retry_counts": counts,
            "needs_correction": True,
            "validation_errors": [{
                "agent": "llm_agent",
                "code": "AGENT_ERROR",
                "message": str(e),
                "field": None,
                "severity": "error",
            }]
        }
```

### Pattern C: Conditional Agent (Feature Flag)
```python
async def conditional_agent(state: BuilderState) -> dict:
    from backend.agents.utils import check_and_increment_retry
    
    failure, attempt = check_and_increment_retry(state, "conditional_agent")
    if failure:
        return failure
    
    counts = dict(state.get("retry_counts", {}))
    counts["conditional_agent"] = attempt
    
    feature_enabled = state.get("feature_enabled", False)
    
    if not feature_enabled:
        # Feature disabled - skip work
        return {
            "retry_counts": counts,
            "needs_correction": False,
            "my_config": {"enabled": False},
        }
    
    # Feature enabled - do work
    try:
        result = await do_work(state)
        return {
            "retry_counts": counts,
            "needs_correction": False,
            "my_config": result,
        }
    except Exception as e:
        return {
            "retry_counts": counts,
            "needs_correction": True,
            "validation_errors": [{...}]
        }
```

---

## Testing Your Migration

### Test 1: First Attempt Success
```python
state = {
    "retry_counts": {},
    "MAX_RETRIES": 5,
}
result = await my_agent(state)

assert result["retry_counts"]["my_agent"] == 1
assert result["needs_correction"] is False
print("✅ First attempt success")
```

### Test 2: Retry After Failure
```python
state = {
    "retry_counts": {"my_agent": 1},
    "MAX_RETRIES": 5,
    "needs_correction": True,
}
result = await my_agent(state)

assert result["retry_counts"]["my_agent"] == 2
print("✅ Retry increments counter")
```

### Test 3: Max Retries Exceeded
```python
state = {
    "retry_counts": {"my_agent": 5},
    "MAX_RETRIES": 5,
}
result = await my_agent(state)

assert result["agent_failed"] is True
assert result["retry_counts"]["my_agent"] == 6
print("✅ Max retries enforced")
```

---

## Common Mistakes to Avoid

### ❌ Mistake 1: Forgetting to Reset needs_correction
```python
return {
    "retry_counts": counts,
    # ❌ Missing needs_correction: False
    "result": result,
}
```
**Impact**: Next agent will see `needs_correction=True` and enter retry loop

### ❌ Mistake 2: Not Including retry_counts in Return
```python
return {
    # ❌ Missing retry_counts
    "needs_correction": False,
    "result": result,
}
```
**Impact**: Retry count never updates, max retries never enforced

### ❌ Mistake 3: Incrementing Twice
```python
failure, attempt = check_and_increment_retry(state, "my_agent")
if failure:
    return failure

counts = dict(state.get("retry_counts", {}))
counts["my_agent"] = attempt + 1  # ❌ Don't add 1, already incremented
```
**Impact**: Retry count increases by 2 each time

### ❌ Mistake 4: Using Old Retry Check Pattern
```python
# ❌ Don't do this anymore
retry_count = state.get("retry_counts", {}).get(agent_name, 0)
if retry_count >= max_retries:
    return {"agent_failed": True}
```
**Impact**: Counter never increments, infinite retries possible

---

## Verification Checklist

For each agent you migrate, verify:

- [ ] Import `check_and_increment_retry` at top of function
- [ ] Call `check_and_increment_retry` before doing work
- [ ] Return failure dict immediately if max retries exceeded
- [ ] Create `counts` dict and set `counts[agent_name] = attempt`
- [ ] Include `retry_counts: counts` in success return
- [ ] Include `needs_correction: False` in success return
- [ ] Include `retry_counts: counts` in error return
- [ ] Include `needs_correction: True` in error return
- [ ] Test with first attempt success
- [ ] Test with retry after failure
- [ ] Test with max retries exceeded

---

## Bulk Migration Script (Optional)

If you want to migrate all agents at once, you can create a script:

```python
# migrate_all_agents.py
import os
import re

AGENT_FILES = [
    "backend/agents/data_modeling.py",
    "backend/agents/service_exposure.py",
    # ... add all agent files
]

for filepath in AGENT_FILES:
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add import if not present
    if "from backend.agents.utils import check_and_increment_retry" not in content:
        # Add import after other imports
        content = re.sub(
            r'(from backend\.agents\.resilience import.*\n)',
            r'\1from backend.agents.utils import check_and_increment_retry\n',
            content
        )
    
    # Replace retry check pattern
    # ... add regex replacements ...
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Migrated {filepath}")
```

**Warning**: Automated migration is risky. Review each change carefully!

---

## Status Tracking

Track your progress here:

### Core Workflow
- [ ] data_modeling.py
- [ ] domain_modeling.py
- [ ] service_exposure.py
- [ ] business_logic.py
- [ ] ux_design.py
- [ ] fiori_ui.py
- [ ] security.py
- [ ] deployment.py
- [ ] validation.py
- [ ] project_verification.py

### Parallel Phases
- [ ] integration_design.py
- [ ] error_handling.py
- [ ] audit_logging.py
- [ ] api_governance.py
- [x] multitenancy.py (already fixed)
- [ ] i18n.py
- [x] feature_flags.py (already fixed)
- [ ] testing.py
- [ ] documentation.py
- [ ] observability.py

### Optional
- [ ] compliance_check.py
- [ ] performance_review.py
- [x] ci_cd.py (already fixed)
- [ ] extension.py
- [ ] integration.py
- [ ] db_migration.py
- [ ] human_gate.py

---

## Questions?

If you're unsure about how to migrate a specific agent:
1. Check the pattern that matches your agent type (Simple, LLM, Conditional)
2. Look at a similar agent that's already been migrated
3. Test your changes with the verification checklist
4. Check LangSmith traces to verify retry behavior

---

## Related Documentation

- `CRITICAL_BUGS_FIXED.md` - Overview of all 3 critical bugs
- `backend/agents/utils.py` - Retry utility implementation
- `UNBOUNDLOCALERROR_FIXES_SUMMARY.md` - Related bug fixes
