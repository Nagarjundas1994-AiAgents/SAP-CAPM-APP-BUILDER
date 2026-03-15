#!/usr/bin/env python3
"""Final script to fix all return statements in migrated agents."""

import re
from pathlib import Path

agents = [
    'security', 'multitenancy', 'feature_flags', 'compliance_check',
    'performance_review', 'testing', 'ci_cd', 'deployment', 'observability',
    'db_migration', 'extension', 'documentation', 'project_assembly',
    'project_verification', 'requirements'
]

print("🔧 Final fix for agent return statements...")
print(f"📊 Processing {len(agents)} agents\n")

for agent in agents:
    filepath = f'backend/agents/{agent}.py'
    path = Path(filepath)
    if not path.exists():
        print(f"⚠️  Skipping {agent}.py (not found)")
        continue
    
    content = path.read_text(encoding='utf-8')
    original = content
    
    # Replace 'return state' with proper dict return at the end of try block
    lines = content.split('\n')
    
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if 'return state' in line and 'except Exception' not in '\n'.join(lines[max(0,i-5):i+5]):
            # Get indentation
            indent = len(line) - len(line.lstrip())
            
            # Check if this is inside the try block
            has_try_before = any('try:' in lines[j] for j in range(max(0, i-100), i))
            
            if has_try_before:
                # This is the main success return - replace it
                new_lines = [
                    f'{" " * indent}# Success path',
                    f'{" " * indent}completed_at = datetime.utcnow().isoformat()',
                    f'{" " * indent}duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)',
                    f'{" " * indent}',
                    f'{" " * indent}new_retry_counts = state.get("retry_counts", {{}}).copy()',
                    f'{" " * indent}new_retry_counts[agent_name] = retry_count + 1',
                    f'{" " * indent}',
                    f'{" " * indent}return {{',
                    f'{" " * (indent+4)}"agent_history": [{{',
                    f'{" " * (indent+8)}"agent_name": agent_name,',
                    f'{" " * (indent+8)}"status": "completed",',
                    f'{" " * (indent+8)}"started_at": started_at,',
                    f'{" " * (indent+8)}"completed_at": completed_at,',
                    f'{" " * (indent+8)}"duration_ms": duration_ms,',
                    f'{" " * (indent+8)}"error": None,',
                    f'{" " * (indent+8)}"logs": state.get("current_logs", []),',
                    f'{" " * (indent+4)}}}],',
                    f'{" " * (indent+4)}"retry_counts": new_retry_counts,',
                    f'{" " * (indent+4)}"needs_correction": False,',
                    f'{" " * (indent+4)}"current_agent": agent_name,',
                    f'{" " * (indent+4)}"updated_at": completed_at,',
                    f'{" " * indent}}}',
                ]
                
                # Replace the line
                lines[i] = '\n'.join(new_lines)
                
                # Now add exception handler if not present
                if not any('except Exception as e:' in lines[j] for j in range(i, min(len(lines), i+20))):
                    exception_lines = [
                        '',
                        f'{" " * (indent-4)}except Exception as e:',
                        f'{" " * indent}logger.exception(f"[{{agent_name}}] Failed with error: {{e}}")',
                        f'{" " * indent}',
                        f'{" " * indent}completed_at = datetime.utcnow().isoformat()',
                        f'{" " * indent}duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)',
                        f'{" " * indent}',
                        f'{" " * indent}new_retry_counts = state.get("retry_counts", {{}}).copy()',
                        f'{" " * indent}new_retry_counts[agent_name] = retry_count + 1',
                        f'{" " * indent}',
                        f'{" " * indent}return {{',
                        f'{" " * (indent+4)}"agent_history": [{{',
                        f'{" " * (indent+8)}"agent_name": agent_name,',
                        f'{" " * (indent+8)}"status": "failed",',
                        f'{" " * (indent+8)}"started_at": started_at,',
                        f'{" " * (indent+8)}"completed_at": completed_at,',
                        f'{" " * (indent+8)}"duration_ms": duration_ms,',
                        f'{" " * (indent+8)}"error": str(e),',
                        f'{" " * (indent+8)}"logs": None,',
                        f'{" " * (indent+4)}}}],',
                        f'{" " * (indent+4)}"retry_counts": new_retry_counts,',
                        f'{" " * (indent+4)}"needs_correction": True,',
                        f'{" " * (indent+4)}"validation_errors": [{{',
                        f'{" " * (indent+8)}"agent": agent_name,',
                        f'{" " * (indent+8)}"code": "AGENT_ERROR",',
                        f'{" " * (indent+8)}"message": str(e),',
                        f'{" " * (indent+8)}"field": None,',
                        f'{" " * (indent+8)}"severity": "error",',
                        f'{" " * (indent+4)}}}],',
                        f'{" " * (indent+4)}"current_agent": agent_name,',
                        f'{" " * (indent+4)}"updated_at": completed_at,',
                        f'{" " * indent}}}',
                    ]
                    
                    # Find where to insert (after the return block)
                    insert_idx = i + len(new_lines)
                    for line_to_add in exception_lines:
                        lines.insert(insert_idx, line_to_add)
                        insert_idx += 1
                
                # Write back
                content = '\n'.join(lines)
                if content != original:
                    path.write_text(content, encoding='utf-8')
                    print(f'✅ Fixed {agent}.py')
                else:
                    print(f'⚠️  No changes for {agent}.py')
                break

print("\n✨ Final fix complete!")
