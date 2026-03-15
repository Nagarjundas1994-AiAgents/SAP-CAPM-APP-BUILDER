#!/usr/bin/env python3
"""
Fix return statements in migrated agents.
Converts old state mutations to new partial dict returns with proper exception handling.
"""

import re
from pathlib import Path
from typing import List, Tuple

# All agents that need return statement fixes
AGENTS_TO_FIX = [
    "backend/agents/security.py",
    "backend/agents/multitenancy.py",
    "backend/agents/feature_flags.py",
    "backend/agents/compliance_check.py",
    "backend/agents/performance_review.py",
    "backend/agents/testing.py",
    "backend/agents/ci_cd.py",
    "backend/agents/deployment.py",
    "backend/agents/observability.py",
    "backend/agents/db_migration.py",
    "backend/agents/extension.py",
    "backend/agents/documentation.py",
    "backend/agents/project_assembly.py",
    "backend/agents/project_verification.py",
    "backend/agents/requirements.py",
]


def fix_agent_returns(filepath: str) -> Tuple[bool, str]:
    """
    Fix return statements and add exception handling.
    Returns (success, message)
    """
    path = Path(filepath)
    
    if not path.exists():
        return False, f"File not found: {filepath}"
    
    try:
        content = path.read_text(encoding='utf-8')
        original_content = content
        
        # Find agent name
        match = re.search(r'agent_name = "(\w+)"', content)
        if not match:
            return False, f"Could not find agent_name in {filepath}"
        
        agent_name = match.group(1)
        
        # Check if already has exception handling at the end
        if "except Exception as e:" in content and "logger.exception" in content:
            # Already has exception handling, just need to fix the success return
            
            # Find the last "return state" before the exception handler
            lines = content.split("\n")
            
            # Find where to insert success return logic
            for i in range(len(lines) - 1, -1, -1):
                if "return state" in lines[i] and "except Exception" not in "\n".join(lines[max(0, i-10):i+1]):
                    # This is the success return, replace it
                    indent = len(lines[i]) - len(lines[i].lstrip())
                    
                    success_return = f'''{" " * indent}# Success path
{" " * indent}completed_at = datetime.utcnow().isoformat()
{" " * indent}duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
{" " * indent}
{" " * indent}new_retry_counts = state.get("retry_counts", {{}}).copy()
{" " * indent}new_retry_counts[agent_name] = retry_count + 1
{" " * indent}
{" " * indent}log_progress(state, "{agent_name.replace('_', ' ').title()} complete.")
{" " * indent}
{" " * indent}return {{'''
                    
                    # Find what state fields are being set before this return
                    # Look backwards to find state assignments
                    state_assignments = []
                    for j in range(i-1, max(0, i-50), -1):
                        if 'state["' in lines[j] or "state['" in lines[j]:
                            # Extract the key being assigned
                            key_match = re.search(r'state\["([^"]+)"\]|state\[\'([^\']+)\'\]', lines[j])
                            if key_match:
                                key = key_match.group(1) or key_match.group(2)
                                if key not in ["current_agent", "updated_at", "current_logs", "needs_correction"]:
                                    state_assignments.append(key)
                    
                    # Build return dict
                    return_dict_lines = []
                    for key in reversed(state_assignments[:5]):  # Take last 5 assignments
                        return_dict_lines.append(f'{" " * (indent + 4)}"{key}": {key},')
                    
                    # Add standard fields
                    return_dict_lines.extend([
                        f'{" " * (indent + 4)}"agent_history": [{{',
                        f'{" " * (indent + 8)}"agent_name": agent_name,',
                        f'{" " * (indent + 8)}"status": "completed",',
                        f'{" " * (indent + 8)}"started_at": started_at,',
                        f'{" " * (indent + 8)}"completed_at": completed_at,',
                        f'{" " * (indent + 8)}"duration_ms": duration_ms,',
                        f'{" " * (indent + 8)}"error": None,',
                        f'{" " * (indent + 8)}"logs": state.get("current_logs", []),',
                        f'{" " * (indent + 4)}}}],',
                        f'{" " * (indent + 4)}"retry_counts": new_retry_counts,',
                        f'{" " * (indent + 4)}"needs_correction": False,',
                        f'{" " * (indent + 4)}"current_agent": agent_name,',
                        f'{" " * (indent + 4)}"updated_at": completed_at,',
                        f'{" " * indent}}}',
                    ])
                    
                    # Replace the return state line
                    lines[i] = success_return + "\n" + "\n".join(return_dict_lines)
                    content = "\n".join(lines)
                    break
        
        else:
            # Need to add exception handling
            # Find the last return state
            lines = content.split("\n")
            
            for i in range(len(lines) - 1, -1, -1):
                if "return state" in lines[i]:
                    indent = len(lines[i]) - len(lines[i].lstrip())
                    
                    # Add exception handler after this return
                    exception_handler = f'''
{" " * indent}
{" " * (indent - 4)}except Exception as e:
{" " * indent}logger.exception(f"[{{agent_name}}] Failed with error: {{e}}")
{" " * indent}
{" " * indent}completed_at = datetime.utcnow().isoformat()
{" " * indent}duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
{" " * indent}
{" " * indent}new_retry_counts = state.get("retry_counts", {{}}).copy()
{" " * indent}new_retry_counts[agent_name] = retry_count + 1
{" " * indent}
{" " * indent}return {{
{" " * (indent + 4)}"agent_history": [{{
{" " * (indent + 8)}"agent_name": agent_name,
{" " * (indent + 8)}"status": "failed",
{" " * (indent + 8)}"started_at": started_at,
{" " * (indent + 8)}"completed_at": completed_at,
{" " * (indent + 8)}"duration_ms": duration_ms,
{" " * (indent + 8)}"error": str(e),
{" " * (indent + 8)}"logs": None,
{" " * (indent + 4)}}}],
{" " * (indent + 4)}"retry_counts": new_retry_counts,
{" " * (indent + 4)}"needs_correction": True,
{" " * (indent + 4)}"validation_errors": [{{
{" " * (indent + 8)}"agent": agent_name,
{" " * (indent + 8)}"code": "AGENT_ERROR",
{" " * (indent + 8)}"message": str(e),
{" " * (indent + 8)}"field": None,
{" " * (indent + 8)}"severity": "error",
{" " * (indent + 4)}}}],
{" " * (indent + 4)}"current_agent": agent_name,
{" " * (indent + 4)}"updated_at": completed_at,
{" " * indent}}}'''
                    
                    lines.insert(i + 1, exception_handler)
                    content = "\n".join(lines)
                    break
        
        # Write if changed
        if content != original_content:
            path.write_text(content, encoding='utf-8')
            return True, f"Fixed returns in {path.name}"
        else:
            return False, f"No changes needed for {path.name}"
            
    except Exception as e:
        return False, f"Error fixing {filepath}: {str(e)}"


def main():
    """Main function."""
    print("🔧 Fixing agent return statements...")
    print(f"📊 Total agents to fix: {len(AGENTS_TO_FIX)}\n")
    
    results: List[Tuple[str, bool, str]] = []
    
    for filepath in AGENTS_TO_FIX:
        print(f"📝 Processing {Path(filepath).name}...")
        success, message = fix_agent_returns(filepath)
        results.append((filepath, success, message))
        
        if success:
            print(f"  ✅ {message}")
        else:
            print(f"  ⚠️  {message}")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Fix Summary")
    print(f"{'='*60}")
    
    success_count = sum(1 for _, success, _ in results if success)
    
    print(f"✅ Successfully fixed: {success_count}/{len(results)}")
    print(f"\n{'='*60}")
    print("✨ Fix script complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
