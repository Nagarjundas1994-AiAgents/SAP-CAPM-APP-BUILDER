"""
Fix all indentation errors in agent files after try: statements.
"""

import re
from pathlib import Path

def fix_try_indentation(filepath):
    """Fix indentation after try: statements."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        fixed_lines.append(line)
        
        # Check if this is a try: statement
        if line.strip() == 'try:':
            try_indent = len(line) - len(line.lstrip())
            expected_body_indent = try_indent + 4
            
            # Skip empty lines after try:
            i += 1
            while i < len(lines) and not lines[i].strip():
                fixed_lines.append(lines[i])
                i += 1
            
            # Now we should be at the first line of the try body
            # Continue until we hit except/finally
            while i < len(lines):
                curr_line = lines[i]
                
                # Check if this is except or finally
                if curr_line.strip().startswith(('except ', 'except:', 'finally:')):
                    # This should be at try_indent level
                    curr_indent = len(curr_line) - len(curr_line.lstrip())
                    if curr_indent != try_indent:
                        fixed_lines.append(' ' * try_indent + curr_line.lstrip())
                    else:
                        fixed_lines.append(curr_line)
                    i += 1
                    break
                
                # This is part of the try body
                if curr_line.strip():  # Non-empty line
                    curr_indent = len(curr_line) - len(curr_line.lstrip())
                    if curr_indent < expected_body_indent:
                        # Need to indent this line
                        fixed_lines.append(' ' * expected_body_indent + curr_line.lstrip())
                    else:
                        # Already properly indented or more indented (nested block)
                        fixed_lines.append(curr_line)
                else:
                    # Empty line
                    fixed_lines.append(curr_line)
                
                i += 1
        else:
            i += 1
    
    fixed_content = '\n'.join(fixed_lines)
    
    if fixed_content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        return True
    return False

# Find all agent files
agent_dir = Path('backend/agents')
agent_files = list(agent_dir.glob('*.py'))

print("Fixing indentation in all agent files...")
print("=" * 70)

fixed_count = 0
for filepath in sorted(agent_files):
    if filepath.name.startswith('__'):
        continue
    
    try:
        if fix_try_indentation(filepath):
            print(f"✅ Fixed: {filepath.name}")
            fixed_count += 1
        else:
            print(f"⏭️  OK: {filepath.name}")
    except Exception as e:
        print(f"❌ Error in {filepath.name}: {e}")

print("=" * 70)
print(f"Fixed {fixed_count} file(s)")
