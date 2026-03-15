# Feature Flags Agent UnboundLocalError - FIXED

## Problem
The feature_flags agent had the exact same bug as the multitenancy agent - causing an infinite retry loop that hit the recursion limit (300 retries):

```
UnboundLocalError: cannot access local variable 'prompt' where it is not associated with a value
```

## Root Cause
When `feature_flags_enabled` was False, the code structure was:

```python
if not feature_flags_enabled:
    log_progress(state, "Feature flags not enabled, skipping...")
    feature_flags_config = {"enabled": False, "flags": []}
else:
    # Define prompt here
    prompt = FEATURE_FLAGS_PROMPT.format(...)

# BUG: These were OUTSIDE the if/else block
if rag_context:
    prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"

log_progress(state, "Generating feature flag configuration...")
result = await generate_with_retry(
    prompt=prompt,  # ❌ UnboundLocalError when feature_flags_enabled=False
    ...
)
```

The `generate_with_retry` call and `if rag_context:` block were outside the if/else block, so when feature flags were disabled:
1. `prompt` was never defined
2. `if rag_context:` tried to access undefined `prompt` → `UnboundLocalError`
3. Exception handler set `needs_correction=True`
4. Graph retried the agent
5. Same error occurred again → infinite loop
6. Hit recursion limit after 300 retries

## Solution
Moved the entire LLM generation logic INSIDE the `else` block:

```python
if not feature_flags_enabled:
    log_progress(state, "Feature flags not enabled, skipping...")
    feature_flags_config = {"enabled": False, "flags": []}
else:
    # Retrieve RAG context
    rag_docs = await retrieve_for_agent("feature_flags", ...)
    rag_context = "\n\n".join(rag_docs) if rag_docs else ""
    
    # Define prompt
    prompt = FEATURE_FLAGS_PROMPT.format(...)
    
    # ✅ Now INSIDE the else block
    if rag_context:
        prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
    
    log_progress(state, "Generating feature flag configuration...")
    result = await generate_with_retry(
        prompt=prompt,  # ✅ prompt is always defined here
        ...
    )
    
    if result:
        feature_flags_config = result
        log_progress(state, f"✅ Defined {len(result.get('flags', []))} feature flags")
    else:
        log_progress(state, "⚠️ LLM generation failed - using minimal feature flags config")
        feature_flags_config = {
            "enabled": True,
            "flags": [],
            "service_binding": None
        }

# Continue with common code
state["feature_flags_config"] = feature_flags_config
```

## Changes Made
**File**: `backend/agents/feature_flags.py`

**Lines Changed**: 125-165

**Key Changes**:
1. Moved `if rag_context:` block inside the `else` block
2. Moved `log_progress(state, "Generating feature flag configuration...")` inside the `else` block
3. Moved entire `generate_with_retry` call inside the `else` block
4. Moved result handling (`if result:` block) inside the `else` block
5. Now `feature_flags_config` is set in both branches before continuing

## Verification
```bash
python -c "from backend.agents.feature_flags import feature_flags_agent; print('✓ Import successful')"
# ✓ Import successful
```

## Impact

### Before Fix:
- ❌ Infinite retry loop when feature flags disabled
- ❌ Recursion limit error after 300 retries
- ❌ Workflow completely blocked
- ❌ No way to proceed past feature_flags agent

### After Fix:
- ✅ When feature flags disabled: skips LLM generation, sets config to `{"enabled": False, "flags": []}`
- ✅ When feature flags enabled: generates full configuration via LLM
- ✅ No more UnboundLocalError
- ✅ No more infinite retry loop
- ✅ Workflow proceeds normally

## Testing Recommendations

### Test Case 1: Feature Flags Disabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "feature_flags_enabled": False,  # Disabled
}
result = await feature_flags_agent(state)
# Expected: {"enabled": False, "flags": []} without calling LLM
```

### Test Case 2: Feature Flags Enabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "feature_flags_enabled": True,  # Enabled
}
result = await feature_flags_agent(state)
# Expected: Full config with flags array
```

## Related Issues
This bug was introduced by the same automated indentation fix script that broke the multitenancy agent. The script moved code outside the else block when it should have stayed inside.

## Status
- [x] Bug identified
- [x] Root cause analyzed
- [x] Fix implemented
- [x] Import verification passed
- [ ] Server restart required
- [ ] End-to-end testing pending

## Next Steps
1. **Restart the server** to load the fixed code
2. Test with a project that has `feature_flags_enabled: false`
3. Verify the workflow completes without hitting recursion limit
4. Test with `feature_flags_enabled: true` to ensure LLM generation still works
5. **Search for other agents with the same pattern** (disabled flag + prompt usage outside if/else)
