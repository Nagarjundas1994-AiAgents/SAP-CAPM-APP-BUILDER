# Multitenancy Agent UnboundLocalError - FIXED

## Problem
The multitenancy agent was causing an infinite retry loop that hit the recursion limit (300 retries):

```
UnboundLocalError: cannot access local variable 'prompt' where it is not associated with a value
```

### Error Pattern
```
2026-03-16 02:18:55,001 - backend.agents.multitenancy - ERROR - [multitenancy] Failed with error: cannot access local variable 'prompt' where it is not associated with a value
2026-03-16 02:18:55,004 - backend.agents.multitenancy - INFO - [multitenancy] Starting Multitenancy Agent
... (repeated 300+ times)
2026-03-16 02:18:55,616 - langgraph.errors.GraphRecursionError: Recursion limit of 300 reached without hitting a stop condition.
```

## Root Cause
When `multitenancy_enabled` was False, the code structure was:

```python
if not multitenancy_enabled:
    log_progress(state, "Multitenancy not enabled, skipping...")
    multitenancy_config = {"enabled": False}
else:
    # Define prompt here
    prompt = MULTITENANCY_PROMPT.format(...)

# BUG: This was OUTSIDE the if/else block
log_progress(state, "Generating multitenancy configuration...")
result = await generate_with_retry(
    prompt=prompt,  # ❌ UnboundLocalError when multitenancy_enabled=False
    ...
)
```

The `generate_with_retry` call was outside the if/else block, so when multitenancy was disabled:
1. `prompt` was never defined
2. `generate_with_retry(prompt=prompt)` raised `UnboundLocalError`
3. Exception handler set `needs_correction=True`
4. Graph retried the agent
5. Same error occurred again → infinite loop
6. Hit recursion limit after 300 retries

## Solution
Moved the `generate_with_retry` call INSIDE the `else` block:

```python
if not multitenancy_enabled:
    log_progress(state, "Multitenancy not enabled, skipping...")
    multitenancy_config = {"enabled": False}
else:
    # Define prompt
    prompt = MULTITENANCY_PROMPT.format(...)
    
    # ✅ Now INSIDE the else block
    log_progress(state, "Generating multitenancy configuration...")
    result = await generate_with_retry(
        prompt=prompt,  # ✅ prompt is always defined here
        ...
    )
    
    if result:
        multitenancy_config = result
    else:
        multitenancy_config = {
            "enabled": True,
            "mtxs_enabled": True,
            "tenant_isolation": "schema",
            "onboarding_api": "/mtx/v1/provisioning/tenant"
        }

# Continue with common code
state["multitenancy_config"] = multitenancy_config
```

## Changes Made
**File**: `backend/agents/multitenancy.py`

**Lines Changed**: 125-165

**Key Changes**:
1. Moved `log_progress(state, "Generating multitenancy configuration...")` inside the `else` block
2. Moved entire `generate_with_retry` call inside the `else` block
3. Moved result handling (`if result:` block) inside the `else` block
4. Now `multitenancy_config` is set in both branches before continuing

## Verification
```bash
python -c "from backend.agents.multitenancy import multitenancy_agent; print('✓ Import successful')"
# ✓ Import successful
```

## Impact

### Before Fix:
- ❌ Infinite retry loop when multitenancy disabled
- ❌ Recursion limit error after 300 retries
- ❌ Workflow completely blocked
- ❌ No way to proceed past multitenancy agent

### After Fix:
- ✅ When multitenancy disabled: skips LLM generation, sets config to `{"enabled": False}`
- ✅ When multitenancy enabled: generates full configuration via LLM
- ✅ No more UnboundLocalError
- ✅ No more infinite retry loop
- ✅ Workflow proceeds normally

## Testing Recommendations

### Test Case 1: Multitenancy Disabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "multitenancy_enabled": False,  # Disabled
}
result = await multitenancy_agent(state)
# Expected: {"enabled": False} without calling LLM
```

### Test Case 2: Multitenancy Enabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "multitenancy_enabled": True,  # Enabled
}
result = await multitenancy_agent(state)
# Expected: Full config with tenant_isolation, mtxs_enabled, etc.
```

## Related Issues
This bug was introduced by the automated indentation fix script that didn't properly handle the if/else block structure. The script moved code outside the else block when it should have stayed inside.

## Status
- [x] Bug identified
- [x] Root cause analyzed
- [x] Fix implemented
- [x] Import verification passed
- [ ] Server restart required
- [ ] End-to-end testing pending

## Next Steps
1. **Restart the server** to load the fixed code
2. Test with a project that has `multitenancy_enabled: false`
3. Verify the workflow completes without hitting recursion limit
4. Test with `multitenancy_enabled: true` to ensure LLM generation still works
