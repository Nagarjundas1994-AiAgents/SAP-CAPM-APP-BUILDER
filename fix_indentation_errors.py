"""
Fix indentation errors in agent files where try blocks have unindented code.
"""

import re
from pathlib import Path

def fix_agent_file(filepath):
    """Fix indentation issues in an agent file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern: try: followed by newline(s) and then unindented code
    # We need to indent everything after try: until we hit except/finally
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        fixed_lines.append(line)
        
        # Check if this line is a try statement
        if line.strip() == 'try:':
            # Get the indentation level of the try statement
            try_indent = len(line) - len(line.lstrip())
            expected_indent = try_indent + 4
            
            # Look ahead to find the next line that should be indented
            i += 1
            while i < len(lines):
                next_line = lines[i]
                
                # Skip empty lines
                if not next_line.strip():
                    fixed_lines.append(next_line)
                    i += 1
                    continue
                
                # Check if this is except or finally (end of try block)
                if next_line.strip().startswith(('except ', 'except:', 'finally:')):
                    # This line should be at try_indent level
                    current_indent = len(next_line) - len(next_line.lstrip())
                    if current_indent != try_indent:
                        # Fix the indentation
                        fixed_lines.append(' ' * try_indent + next_line.lstrip())
                    else:
                        fixed_lines.append(next_line)
                    i += 1
                    break
                
                # This line should be indented inside the try block
                current_indent = len(next_line) - len(next_line.lstrip())
                if current_indent < expected_indent:
                    # Need to add indentation
                    fixed_lines.append(' ' * expected_indent + next_line.lstrip())
                else:
                    # Already properly indented
                    fixed_lines.append(next_line)
                
                i += 1
        else:
            i += 1
    
    fixed_content = '\n'.join(fixed_lines)
    
    if fixed_content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print(f"✅ Fixed: {filepath}")
        return True
    else:
        print(f"⏭️  No changes needed: {filepath}")
        return False

# Fix all agent files
agent_dir = Path('backend/agents')
agent_files = [
    'db_migration.py',
    'security.py',
]

print("Fixing indentation errors in agent files...")
print("=" * 60)

fixed_count = 0
for filename in agent_files:
    filepath = agent_dir / filename
    if filepath.exists():
        if fix_agent_file(filepath):
            fixed_count += 1
    else:
        print(f"⚠️  File not found: {filepath}")

print("=" * 60)
print(f"Fixed {fixed_count} file(s)")
