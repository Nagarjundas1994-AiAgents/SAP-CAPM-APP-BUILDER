"""
Fix all except blocks that have incorrect indentation.
Pattern: except Exception as e: followed by unindented logger.exception()
"""

import os
import re

def fix_except_block(filepath):
    """Fix except block indentation in a file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern: except Exception as e: followed by logger.exception at wrong indent
    # The logger.exception should be indented 4 more spaces than the except line
    pattern = r'(    except Exception as e:)\n(    logger\.exception)'
    replacement = r'\1\n        logger.exception'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

# List of files that need fixing based on grep results
files_to_fix = [
    'backend/agents/performance_review.py',
    'backend/agents/observability.py',
    'backend/agents/extension.py',
    'backend/agents/documentation.py',
    'backend/agents/ci_cd.py',
]

print("Fixing except block indentation...")
fixed_count = 0

for filepath in files_to_fix:
    if os.path.exists(filepath):
        if fix_except_block(filepath):
            print(f"✓ Fixed: {filepath}")
            fixed_count += 1
        else:
            print(f"- No changes needed: {filepath}")
    else:
        print(f"✗ File not found: {filepath}")

print(f"\nFixed {fixed_count} files")
