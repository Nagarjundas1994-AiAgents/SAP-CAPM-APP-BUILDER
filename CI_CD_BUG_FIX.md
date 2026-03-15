# CI/CD Agent UnboundLocalError - FIXED

## Problem
The ci_cd agent had the exact same bug as the multitenancy and feature_flags agents - causing an infinite retry loop that hit the recursion limit (300 retries):

```
UnboundLocalError: cannot access local variable 'prompt' where it is not associated with a value
```

## Root Cause
When `ci_cd_enabled` was False, the code structure was:

```python
if not ci_cd_enabled:
    log_progress(state, "CI/CD not enabled, skipping...")
    ci_cd_config = {"enabled": False}
else:
    # Define prompt here
    prompt = CI_CD_PROMPT.format(...)

# BUG: These were OUTSIDE the if/else block
if rag_context:
    prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"

log_progress(state, f"Generating {ci_cd_platform} pipeline...")
result = await generate_with_retry(
    prompt=prompt,  # ❌ UnboundLocalError when ci_cd_enabled=False
    ...
)
```

The `generate_with_retry` call, `if rag_context:` block, and workflow file generation were outside the if/else block, so when CI/CD was disabled:
1. `prompt` was never defined
2. `if rag_context:` tried to access undefined `prompt` → `UnboundLocalError`
3. Exception handler set `needs_correction=True`
4. Graph retried the agent
5. Same error occurred again → infinite loop
6. Hit recursion limit after 300 retries

## Solution
Moved the entire LLM generation logic and file generation INSIDE the `else` block:

```python
if not ci_cd_enabled:
    log_progress(state, "CI/CD not enabled, skipping...")
    ci_cd_config = {"enabled": False}
    generated_files = []
else:
    # Retrieve RAG context
    rag_docs = await retrieve_for_agent("ci_cd", ...)
    rag_context = "\n\n".join(rag_docs) if rag_docs else ""
    
    # Define prompt
    prompt = CI_CD_PROMPT.format(...)
    
    # ✅ Now INSIDE the else block
    if rag_context:
        prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
    
    log_progress(state, f"Generating {ci_cd_platform} pipeline...")
    result = await generate_with_retry(
        prompt=prompt,  # ✅ prompt is always defined here
        ...
    )
    
    if result:
        ci_cd_config = result
        workflow_content = result.get("github_actions_workflow", "")
        log_progress(state, f"✅ Configured {len(result.get('quality_gates', []))} quality gates")
    else:
        log_progress(state, "⚠️ LLM generation failed - using minimal CI/CD config")
        ci_cd_config = {
            "enabled": True,
            "platform": ci_cd_platform,
            "quality_gates": ["lint", "test", "security-scan"],
            "deployment_stages": ["dev", "staging", "production"]
        }
        workflow_content = """..."""
    
    # Generate workflow file
    generated_files = [{
        "path": ".github/workflows/ci.yml",
        "content": workflow_content,
        "file_type": "yml"
    }]

# Continue with common code
state["artifacts_deployment"] = state.get("artifacts_deployment", []) + generated_files
state["ci_cd_config"] = ci_cd_config
```

## Changes Made
**File**: `backend/agents/ci_cd.py`

**Lines Changed**: 120-195

**Key Changes**:
1. Moved `if rag_context:` block inside the `else` block
2. Moved `log_progress(state, f"Generating {ci_cd_platform} pipeline...")` inside the `else` block
3. Moved entire `generate_with_retry` call inside the `else` block
4. Moved result handling (`if result:` block) inside the `else` block
5. Moved workflow file generation inside the `else` block
6. Added `generated_files = []` in the disabled branch
7. Fixed indentation in the workflow YAML template
8. Now both `ci_cd_config` and `generated_files` are set in both branches before continuing

## Verification
```bash
python -c "from backend.agents.ci_cd import ci_cd_agent; print('✓ Import successful')"
# ✓ Import successful
```

## Impact

### Before Fix:
- ❌ Infinite retry loop when CI/CD disabled
- ❌ Recursion limit error after 300 retries
- ❌ Workflow completely blocked
- ❌ No way to proceed past ci_cd agent

### After Fix:
- ✅ When CI/CD disabled: skips LLM generation, sets config to `{"enabled": False}`, no files generated
- ✅ When CI/CD enabled: generates full configuration via LLM with workflow file
- ✅ No more UnboundLocalError
- ✅ No more infinite retry loop
- ✅ Workflow proceeds normally

## Testing Recommendations

### Test Case 1: CI/CD Disabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "ci_cd_enabled": False,  # Disabled
}
result = await ci_cd_agent(state)
# Expected: {"enabled": False} without calling LLM, no workflow files
```

### Test Case 2: CI/CD Enabled
```python
state = {
    "project_name": "Test",
    "project_description": "Test app",
    "ci_cd_enabled": True,  # Enabled
    "ci_cd_platform": "github_actions",
}
result = await ci_cd_agent(state)
# Expected: Full config with quality_gates, deployment_stages, and .github/workflows/ci.yml file
```

## Related Issues
This bug was introduced by the same automated indentation fix script that broke the multitenancy and feature_flags agents. The script moved code outside the else block when it should have stayed inside.

## Status
- [x] Bug identified
- [x] Root cause analyzed
- [x] Fix implemented
- [x] Import verification passed
- [ ] Server restart required
- [ ] End-to-end testing pending

## Next Steps
1. **Restart the server** to load the fixed code
2. Test with a project that has `ci_cd_enabled: false`
3. Verify the workflow completes without hitting recursion limit
4. Test with `ci_cd_enabled: true` to ensure LLM generation and workflow file creation still works
