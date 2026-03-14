"""
Test script to verify human gate bug fixes.

Run this script to validate that all three bugs are fixed:
1. needs_correction reset on approval
2. Multi-process diagnostic logging
3. Invalid correction_agent validation

Usage:
    python test_human_gate_fixes.py
"""

import asyncio
import logging
from datetime import datetime

# Configure logging to see DEBUG messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from backend.agents.state import BuilderState, create_initial_state
from backend.agents.human_gate import (
    human_gate,
    set_gate_decision,
    get_gate_decision,
    clear_gate,
    create_gate_event,
)
from backend.agents.graph import should_continue_after_gate


async def test_bug_1_needs_correction_reset():
    """Test Bug #1: needs_correction is reset on approval."""
    print("\n" + "="*80)
    print("TEST 1: Bug #1 - needs_correction Reset on Approval")
    print("="*80)
    
    # Create initial state with needs_correction=True (simulating prior refinement)
    state = create_initial_state(
        session_id="test-session-1",
        project_name="test-project"
    )
    state["needs_correction"] = True
    state["correction_agent"] = "requirements"
    state["correction_context"] = {"issues": ["test issue"]}
    
    print(f"Initial state: needs_correction={state.get('needs_correction')}, "
          f"correction_agent={state.get('correction_agent')}")
    
    # Simulate gate approval in background
    async def approve_gate():
        await asyncio.sleep(0.5)  # Wait for gate to start
        set_gate_decision("test-session-1", "gate_1_requirements", {
            "decision": "approved",
            "notes": "Looks good!",
            "target_agent": None,
        })
    
    # Run gate and approval concurrently
    gate_task = asyncio.create_task(human_gate(
        state=state,
        gate_id="gate_1_requirements",
        gate_name="Gate 1: Requirements Sign-off",
        context_summary="Test gate",
        reviewing_agent="requirements",
        timeout_hours=1,
    ))
    approve_task = asyncio.create_task(approve_gate())
    
    # Wait for both
    updated_state = await gate_task
    await approve_task
    
    # Verify flags are reset
    print(f"After approval: needs_correction={updated_state.get('needs_correction')}, "
          f"correction_agent={updated_state.get('correction_agent')}, "
          f"correction_context={updated_state.get('correction_context')}")
    
    assert updated_state.get("needs_correction") == False, "❌ needs_correction not reset!"
    assert updated_state.get("correction_agent") is None, "❌ correction_agent not reset!"
    assert updated_state.get("correction_context") is None, "❌ correction_context not reset!"
    
    print("✅ Bug #1 FIX VERIFIED: All correction flags reset on approval")
    
    # Cleanup
    clear_gate("test-session-1", "gate_1_requirements")


async def test_bug_2_diagnostic_logging():
    """Test Bug #2: Diagnostic logging for multi-process debugging."""
    print("\n" + "="*80)
    print("TEST 2: Bug #2 - Diagnostic Logging (Check logs for PID messages)")
    print("="*80)
    
    state = create_initial_state(
        session_id="test-session-2",
        project_name="test-project"
    )
    
    print("Starting gate - check logs for '[GATE DEBUG]' messages with PID...")
    
    # Simulate gate approval
    async def approve_gate():
        await asyncio.sleep(0.5)
        print("Submitting gate decision - check logs for PID...")
        set_gate_decision("test-session-2", "gate_2_architecture", {
            "decision": "approved",
            "notes": "Architecture approved",
            "target_agent": None,
        })
    
    gate_task = asyncio.create_task(human_gate(
        state=state,
        gate_id="gate_2_architecture",
        gate_name="Gate 2: Architecture Sign-off",
        context_summary="Test gate",
        reviewing_agent="enterprise_architecture",
        timeout_hours=1,
    ))
    approve_task = asyncio.create_task(approve_gate())
    
    await gate_task
    await approve_task
    
    print("✅ Bug #2 DIAGNOSTIC LOGGING ADDED: Check logs above for PID messages")
    print("   If PIDs differ, you have a multi-process issue!")
    
    # Cleanup
    clear_gate("test-session-2", "gate_2_architecture")


def test_bug_3_invalid_correction_agent():
    """Test Bug #3: Invalid correction_agent validation."""
    print("\n" + "="*80)
    print("TEST 3: Bug #3 - Invalid correction_agent Validation")
    print("="*80)
    
    # Test case 1: correction_agent doesn't match refine_node
    state1 = {
        "needs_correction": True,
        "correction_agent": "invalid_agent",  # Not in edge map
    }
    
    result1 = should_continue_after_gate(state1, "domain_modeling", "enterprise_architecture")
    print(f"Test 1 - Invalid agent: correction_agent='invalid_agent', result='{result1}'")
    assert result1 == "enterprise_architecture", "❌ Should fallback to refine_node!"
    print("✅ Correctly fell back to refine_node")
    
    # Test case 2: correction_agent is None
    state2 = {
        "needs_correction": True,
        "correction_agent": None,
    }
    
    result2 = should_continue_after_gate(state2, "domain_modeling", "enterprise_architecture")
    print(f"Test 2 - None agent: correction_agent=None, result='{result2}'")
    assert result2 == "enterprise_architecture", "❌ Should use refine_node!"
    print("✅ Correctly used refine_node")
    
    # Test case 3: correction_agent matches refine_node (valid)
    state3 = {
        "needs_correction": True,
        "correction_agent": "enterprise_architecture",
    }
    
    result3 = should_continue_after_gate(state3, "domain_modeling", "enterprise_architecture")
    print(f"Test 3 - Valid agent: correction_agent='enterprise_architecture', result='{result3}'")
    assert result3 == "enterprise_architecture", "❌ Should use correction_agent!"
    print("✅ Correctly used correction_agent")
    
    # Test case 4: No correction needed (approved)
    state4 = {
        "needs_correction": False,
    }
    
    result4 = should_continue_after_gate(state4, "domain_modeling", "enterprise_architecture")
    print(f"Test 4 - Approved: needs_correction=False, result='{result4}'")
    assert result4 == "domain_modeling", "❌ Should continue to next_node!"
    print("✅ Correctly continued to next_node")
    
    print("✅ Bug #3 FIX VERIFIED: All validation cases passed")


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("HUMAN GATE BUG FIXES - VERIFICATION TESTS")
    print("="*80)
    
    try:
        # Test Bug #1
        await test_bug_1_needs_correction_reset()
        
        # Test Bug #2
        await test_bug_2_diagnostic_logging()
        
        # Test Bug #3 (synchronous)
        test_bug_3_invalid_correction_agent()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nSummary:")
        print("  ✅ Bug #1: needs_correction reset on approval - FIXED")
        print("  ✅ Bug #2: Diagnostic logging added - CHECK LOGS FOR PID")
        print("  ✅ Bug #3: Invalid correction_agent validation - FIXED")
        print("\nNext Steps:")
        print("  1. For production multi-process deployment, implement Redis pub/sub")
        print("  2. Add integration tests to CI/CD pipeline")
        print("  3. Monitor gate timeout metrics in production")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
