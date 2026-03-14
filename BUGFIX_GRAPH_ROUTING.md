# Bug Fix: Graph Routing KeyError

## Issue
```
KeyError: 'data_modeling'
During task with name 'requirements'
```

The workflow was failing immediately after the requirements agent completed, trying to route to 'data_modeling' instead of 'enterprise_architecture'.

## Root Cause
Duplicate function definitions in `backend/agents/graph.py`:
- `should_retry_agent()` was defined twice (lines ~85 and ~225)
- `should_self_heal()` was defined twice (lines ~108 and ~236)

The second definitions were overwriting the first ones. The second `should_self_heal()` had a limited set of valid targets that didn't match the comprehensive routing needed.

## Fix
Removed the duplicate "Legacy" function definitions (lines 220-247) that were overwriting the correct implementations.

## Files Changed
- `backend/agents/graph.py` - Removed duplicate routing functions

## Testing
Restart the backend server and test a new generation to verify the workflow proceeds correctly from requirements → enterprise_architecture.
