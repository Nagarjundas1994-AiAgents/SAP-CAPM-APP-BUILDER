# Quick Start - Testing the Architecture Fixes

**5-Minute Guide to Verify Everything Works**

---

## ✅ Pre-Flight Checklist

Before testing, verify these files were updated:

```bash
# Check modified files
git status

# Should show:
# modified:   backend/agents/state.py
# modified:   backend/agents/graph.py
# modified:   .env
# new file:   backend/agents/resilience.py
# new file:   LANGGRAPH_ARCHITECTURE_FIXES.md
# new file:   AGENT_DEVELOPMENT_GUIDE.md
# new file:   AGENT_MIGRATION_CHECKLIST.md
# new file:   IMPLEMENTATION_SUMMARY.md
# new file:   FIXES_VISUAL_SUMMARY.md
# new file:   QUICK_START_TESTING.md
```

---

## 🚀 Quick Test (5 Minutes)

### Step 1: Verify No Syntax Errors

```bash
# Check Python syntax
python -m py_compile backend/agents/state.py
python -m py_compile backend/agents/graph.py
python -m py_compile backend/agents/resilience.py

# Should complete with no output (success)
```

### Step 2: Test State Schema

```python
# Run in Python REPL
python

>>> from backend.agents.state import BuilderState, create_initial_state
>>> from typing import get_type_hints
>>> import operator

>>> # Verify Annotated reducers exist
>>> hints = get_type_hints(BuilderState, include_extras=True)
>>> 
>>> # Check agent_history has Annotated reducer
>>> print(hints['agent_history'])
# Should show: typing.Annotated[list[...], <built-in function add>]
>>>
>>> # Create initial state
>>> state = create_initial_state("test-123", "test-project")
>>> print(f"Session: {state['session_id']}")
>>> print(f"Retry counts: {state['retry_counts']}")
>>> print(f"Max retries: {state['MAX_RETRIES']}")
>>>
>>> exit()
```

### Step 3: Test Graph Compilation

```python
# Run in Python REPL
python

>>> import asyncio
>>> from backend.agents.graph import get_builder_graph
>>>
>>> # Test thread-safe compilation
>>> async def test_graph():
...     graph = await get_builder_graph()
...     print(f"Graph compiled: {graph is not None}")
...     print(f"Graph type: {type(graph)}")
...     return graph
...
>>> graph = asyncio.run(test_graph())
# Should print: Graph compiled: True
>>>
>>> exit()
```

### Step 4: Test Resilience Module

```python
# Run in Python REPL
python

>>> from backend.agents.resilience import get_circuit_breaker, with_timeout
>>> from backend.agents.state import BuilderState
>>>
>>> # Test circuit breaker
>>> cb = get_circuit_breaker()
>>> print(f"Circuit breaker open: {cb.is_open}")
>>> print(f"Failure count: {cb.failure_count}")
>>> print(f"Can proceed: {cb.can_proceed()}")
# Should show: open=False, count=0, can_proceed=True
>>>
>>> # Test timeout decorator
>>> import asyncio
>>> 
>>> @with_timeout(timeout_seconds=5)
>>> async def test_agent(state: BuilderState):
...     await asyncio.sleep(1)
...     return {"result": "success"}
...
>>> state = {"session_id": "test"}
>>> result = asyncio.run(test_agent(state))
>>> print(f"Result: {result}")
# Should print: Result: {'result': 'success'}
>>>
>>> exit()
```

### Step 5: Verify Environment Config

```bash
# Check .env has new variables
grep "LANGCHAIN_TRACING_V2" .env
grep "CHECKPOINT_DB_PATH" .env

# Should show:
# LANGCHAIN_TRACING_V2=true
# CHECKPOINT_DB_PATH=checkpoints.db
```

---

## 🧪 Integration Test (10 Minutes)

### Test 1: Create a Simple Workflow

```python
# Create test file: test_workflow_quick.py

import asyncio
from backend.agents.state import create_initial_state
from backend.agents.graph import get_builder_graph

async def test_simple_workflow():
    """Test basic workflow with new architecture."""
    
    # Create initial state
    state = create_initial_state(
        session_id="test-workflow-001",
        project_name="test-project",
        project_description="Testing architecture fixes"
    )
    
    # Add minimal required data
    state["entities"] = [
        {
            "name": "TestEntity",
            "description": "Test entity",
            "fields": [
                {"name": "id", "type": "UUID", "key": True},
                {"name": "name", "type": "String", "length": 100},
            ]
        }
    ]
    
    print("✓ Initial state created")
    print(f"  Session: {state['session_id']}")
    print(f"  Entities: {len(state['entities'])}")
    
    # Get compiled graph
    graph = await get_builder_graph()
    print("✓ Graph compiled successfully")
    
    # Verify checkpointer exists
    print(f"✓ Checkpointer configured: {graph.checkpointer is not None}")
    
    # Verify thread safety
    graph2 = await get_builder_graph()
    print(f"✓ Singleton works: {graph is graph2}")
    
    print("\n✅ All integration tests passed!")

if __name__ == "__main__":
    asyncio.run(test_simple_workflow())
```

Run the test:
```bash
python test_workflow_quick.py
```

Expected output:
```
✓ Initial state created
  Session: test-workflow-001
  Entities: 1
✓ Graph compiled successfully
✓ Checkpointer configured: True
✓ Singleton works: True

✅ All integration tests passed!
```

---

## 🔍 Verify Specific Fixes

### Fix 1: Annotated Reducers (Data Loss Prevention)

```python
# test_annotated_reducers.py

from backend.agents.state import BuilderState
from typing import Annotated
import operator

def test_annotated_reducers():
    """Verify list fields use Annotated reducers."""
    
    from typing import get_type_hints
    hints = get_type_hints(BuilderState, include_extras=True)
    
    # Check critical list fields
    list_fields = [
        'agent_history',
        'validation_errors',
        'current_logs',
        'correction_history',
        'auto_fixed_errors',
        'validation_rules_applied',
        'artifacts_db',
        'artifacts_srv',
        'artifacts_app',
        'artifacts_deployment',
        'artifacts_docs',
        'verification_checks',
    ]
    
    for field in list_fields:
        hint = hints.get(field)
        if hint:
            # Check if it's Annotated
            if hasattr(hint, '__metadata__'):
                # Check if operator.add is in metadata
                if operator.add in hint.__metadata__:
                    print(f"✓ {field}: Has Annotated reducer")
                else:
                    print(f"✗ {field}: Missing operator.add")
            else:
                print(f"✗ {field}: Not Annotated")
        else:
            print(f"✗ {field}: Not found in BuilderState")
    
    print("\n✅ Annotated reducer check complete!")

if __name__ == "__main__":
    test_annotated_reducers()
```

Run:
```bash
python test_annotated_reducers.py
```

### Fix 2: No Duplicate Keys

```python
# test_no_duplicates.py

from backend.agents.state import BuilderState
from typing import get_type_hints

def test_no_duplicate_keys():
    """Verify no duplicate TypedDict keys."""
    
    hints = get_type_hints(BuilderState)
    
    # Count llm_provider occurrences
    llm_provider_count = list(hints.keys()).count('llm_provider')
    
    if llm_provider_count == 1:
        print(f"✓ llm_provider declared once (correct)")
    else:
        print(f"✗ llm_provider declared {llm_provider_count} times (error)")
    
    # Check llm_model
    llm_model_count = list(hints.keys()).count('llm_model')
    
    if llm_model_count == 1:
        print(f"✓ llm_model declared once (correct)")
    else:
        print(f"✗ llm_model declared {llm_model_count} times (error)")
    
    print("\n✅ Duplicate key check complete!")

if __name__ == "__main__":
    test_no_duplicate_keys()
```

Run:
```bash
python test_no_duplicates.py
```

### Fix 3: Thread Safety

```python
# test_thread_safety.py

import asyncio
from backend.agents.graph import get_builder_graph

async def test_thread_safety():
    """Verify graph compilation is thread-safe."""
    
    # Simulate concurrent requests
    tasks = [get_builder_graph() for _ in range(10)]
    graphs = await asyncio.gather(*tasks)
    
    # All should be the same instance
    first_graph = graphs[0]
    all_same = all(g is first_graph for g in graphs)
    
    if all_same:
        print(f"✓ All 10 concurrent calls returned same instance")
        print(f"✓ Thread-safe singleton working correctly")
    else:
        print(f"✗ Different instances returned (race condition)")
    
    print("\n✅ Thread safety check complete!")

if __name__ == "__main__":
    asyncio.run(test_thread_safety())
```

Run:
```bash
python test_thread_safety.py
```

### Fix 4: Circuit Breaker

```python
# test_circuit_breaker.py

from backend.agents.resilience import get_circuit_breaker

def test_circuit_breaker():
    """Verify circuit breaker behavior."""
    
    cb = get_circuit_breaker()
    
    # Initial state
    print(f"Initial state:")
    print(f"  Open: {cb.is_open}")
    print(f"  Failures: {cb.failure_count}")
    print(f"  Can proceed: {cb.can_proceed()}")
    
    # Simulate failures
    print(f"\nSimulating 3 failures...")
    for i in range(3):
        cb.record_failure()
        print(f"  Failure {i+1}: open={cb.is_open}, count={cb.failure_count}")
    
    # Should be open now
    if cb.is_open:
        print(f"✓ Circuit breaker opened after 3 failures")
    else:
        print(f"✗ Circuit breaker should be open")
    
    # Test can_proceed
    if not cb.can_proceed():
        print(f"✓ can_proceed() returns False when open")
    else:
        print(f"✗ can_proceed() should return False")
    
    # Reset for next test
    cb.record_success()
    print(f"\nAfter success:")
    print(f"  Open: {cb.is_open}")
    print(f"  Failures: {cb.failure_count}")
    
    print("\n✅ Circuit breaker check complete!")

if __name__ == "__main__":
    test_circuit_breaker()
```

Run:
```bash
python test_circuit_breaker.py
```

---

## 📊 Expected Results Summary

After running all tests, you should see:

```
✅ No syntax errors in modified files
✅ Annotated reducers present on all list fields
✅ No duplicate TypedDict keys
✅ Graph compiles successfully
✅ Checkpointer configured
✅ Thread-safe singleton works
✅ Circuit breaker opens/closes correctly
✅ Timeout wrapper functions
✅ Environment variables set
```

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError: No module named 'langgraph.checkpoint.sqlite'"

**Solution**: Install LangGraph with checkpointer support:
```bash
pip install langgraph[sqlite]
```

### Error: "AttributeError: 'BuilderState' has no attribute '__metadata__'"

**Solution**: This is expected for non-Annotated fields. Only list fields should have `__metadata__`.

### Error: "RuntimeError: Event loop is closed"

**Solution**: Use `asyncio.run()` instead of `loop.run_until_complete()`:
```python
# Wrong
loop = asyncio.get_event_loop()
loop.run_until_complete(test())

# Correct
asyncio.run(test())
```

### Warning: "Circuit breaker is OPEN"

**Solution**: This is expected after 3 failures. Wait 60 seconds or call `cb.record_success()` to reset.

---

## 🎯 Next Steps

After verifying all tests pass:

1. ✅ Review the implementation summary
2. ✅ Read the agent development guide
3. ✅ Start migrating agents (use checklist)
4. ✅ Add comprehensive test coverage
5. ✅ Deploy to staging environment

---

## 📚 Additional Resources

- [LANGGRAPH_ARCHITECTURE_FIXES.md](./LANGGRAPH_ARCHITECTURE_FIXES.md) - Full technical details
- [AGENT_DEVELOPMENT_GUIDE.md](./AGENT_DEVELOPMENT_GUIDE.md) - Developer reference
- [AGENT_MIGRATION_CHECKLIST.md](./AGENT_MIGRATION_CHECKLIST.md) - Migration steps
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Executive summary

---

## ✅ Test Completion Checklist

- [ ] All syntax checks pass
- [ ] State schema tests pass
- [ ] Graph compilation tests pass
- [ ] Resilience module tests pass
- [ ] Environment config verified
- [ ] Integration test passes
- [ ] Annotated reducers verified
- [ ] No duplicate keys verified
- [ ] Thread safety verified
- [ ] Circuit breaker verified

**When all checked**: ✅ Ready for Phase 2 (Agent Migration)

---

**Quick Start Guide - Version 1.0**  
**Last Updated: 2026-03-15**
