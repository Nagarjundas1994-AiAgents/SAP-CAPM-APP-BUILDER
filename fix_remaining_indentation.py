"""
Fix remaining indentation errors in agent files.
The automated script broke if/else and try/except blocks by not indenting their bodies.
"""

import os
import re

def fix_file_indentation(filepath):
    """Fix indentation errors in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        fixed_lines.append(line)
        
        # Check if this is an if/else/except/try line that should have an indented block
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        
        # Pattern: if/else/except/try/finally followed by colon
        if stripped and (
            stripped.startswith('if ') or 
            stripped.startswith('else:') or 
            stripped.startswith('elif ') or
            stripped.startswith('except ') or
            stripped.startswith('try:') or
            stripped.startswith('finally:')
        ) and stripped.endswith(':'):
            # Check next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.lstrip()
                next_indent = len(next_line) - len(next_stripped)
                
                # If next line is not indented more than current line, it's an error
                if next_stripped and next_indent <= indent:
                    # Need to indent the next line and all following lines at same level
                    j = i + 1
                    expected_indent = indent + 4
                    
                    while j < len(lines):
                        check_line = lines[j]
                        check_stripped = check_line.lstrip()
                        check_indent = len(check_line) - len(check_stripped)
                        
                        if not check_stripped:  # Empty line
                            fixed_lines.append(check_line)
                            j += 1
                            continue
                        
                        # If this line is at the same level as the if/else/except, stop
                        if check_indent == indent and (
                            check_stripped.startswith('else:') or
                            check_stripped.startswith('elif ') or
                            check_stripped.startswith('except ') or
                            check_stripped.startswith('finally:')
                        ):
                            break
                        
                        # If this line is less indented than expected, stop
                        if check_indent < indent:
                            break
                        
                        # If this line is at the wrong indent level, fix it
                        if check_indent == indent:
                            # Add 4 spaces
                            fixed_lines.append(' ' * expected_indent + check_stripped)
                        else:
                            # Keep relative indentation
                            relative_indent = check_indent - indent
                            fixed_lines.append(' ' * (expected_indent + relative_indent) + check_stripped)
                        
                        j += 1
                    
                    i = j
                    continue
        
        i += 1
    
    fixed_content = '\n'.join(fixed_lines)
    
    if fixed_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        return True
    return False

# Find all agent files
agent_dir = 'backend/agents'
files_to_check = []

for filename in os.listdir(agent_dir):
    if filename.endswith('.py') and filename not in ['__init__.py', 'state.py', 'llm_utils.py', 'model_router.py', 'progress.py']:
        filepath = os.path.join(agent_dir, filename)
        files_to_check.append(filepath)

print(f"Checking {len(files_to_check)} agent files...")

fixed_count = 0
for filepath in files_to_check:
    try:
        if fix_file_indentation(filepath):
            print(f"✓ Fixed: {filepath}")
            fixed_count += 1
    except Exception as e:
        print(f"✗ Error in {filepath}: {e}")

print(f"\nFixed {fixed_count} files")
