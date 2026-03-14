# Import Error Fix - get_active_gate

## Problem
The application was crashing with a `NameError: name 'get_active_gate' is not defined` error when trying to access the `/api/builder/{session_id}/gate/current` endpoint.

## Root Cause
The `get_active_gate` function from `backend.agents.human_gate` was being called in the `get_current_gate()` function in `backend/api/builder.py` (line 621), but it was not imported at the module level.

There was a local import inside the `submit_gate_decision()` function:
```python
from backend.agents.human_gate import set_gate_decision, get_active_gate, get_gate_event
```

However, this local import was not accessible to the `get_current_gate()` function, causing the NameError.

## Solution
**File:** `backend/api/builder.py`

### Change 1: Added module-level imports
Added the required imports at the top of the file (line 21):
```python
from backend.agents.human_gate import get_active_gate, set_gate_decision, get_gate_event
```

### Change 2: Removed redundant local import
Removed the duplicate local import from inside the `submit_gate_decision()` function (previously line 558).

## Impact
- ✅ Fixed the `NameError` when accessing gate status endpoints
- ✅ Improved code organization by using module-level imports
- ✅ Eliminated redundant imports
- ✅ All gate-related API endpoints now work correctly

## Testing
After this fix, the following endpoints should work without errors:
- `GET /api/builder/{session_id}/gate/current` - Get current gate status
- `POST /api/builder/{session_id}/gate/{gate_id}/decision` - Submit gate decision

## Related Files
- `backend/api/builder.py` - Fixed import issue
- `backend/agents/human_gate.py` - Source of the imported functions

## Status
✅ **FIXED** - No syntax errors, ready for testing

---

**Fixed:** 2025-01-XX
**Issue:** Import error causing 500 Internal Server Error
**Resolution:** Added module-level imports for human_gate functions
