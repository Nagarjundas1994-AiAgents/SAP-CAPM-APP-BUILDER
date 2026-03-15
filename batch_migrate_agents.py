#!/usr/bin/env python3
"""
Batch migration script for remaining agents.
Applies the Phase 2 migration pattern to all remaining agents.
"""

import re
from pathlib import Path

# Agent files to migrate with their timeout values
AGENTS_TO_MIGRATE = [
    ("backend/agents/error_handling.py", 120),
    ("backend/agents/audit_logging.py", 120),
    ("backend/agents/api_governance.py", 120),
    ("backend/agents/security.py", 180),
    ("backend/agents/multitenancy.py", 120),
    ("backend/agents/feature_flags.py", 60),
    ("backend/agents/compliance_check.py", 120),
    ("backend/agents/performance_review.py", 120),
    ("backend/agents/testing.py", 180),
    ("backend/agents/ci_cd.py", 120),
    ("backend/agents/deployment.py", 180),
    ("backend/agents/observability.py", 120),
    ("backend/agents/db_migration.py", 60),
    ("backend/agents/extension.py", 120),
    ("backend/agents/documentation.py", 120),
    ("backend/agents/project_assembly.py", 60),
    ("backend/agents/project_verification.py", 120),
]


def add_imports(content: str) -> str:
    """Add required imports if not present."""
    if "from typing import Any" not in content:
        content = content.replace(
            "from datetime import datetime",
            "from datetime import datetime\nfrom typing import Any"
        )
    
    if "from backend.agents.resilience import with_timeout" not in content:
        # Find the last import line
        lines = content.split("\n")
        last_import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                last_import_idx = i
        
        lines.insert(last_import_idx + 1, "from backend.agents.resilience import with_timeout")
        content = "\n".join(lines)
    
    return content


def migrate_agent_function(content: str, timeout: int) -> str:
    """Migrate agent function to new pattern."""
    
    # Find the agent function
    pattern = r"async def (\w+_agent)\(state: BuilderState\) -> BuilderState:"
    match = re.search(pattern, content)
    
    if not match:
        print(f"  ⚠️  Could not find agent function")
        return content
    
    agent_func_name = match.group(1)
    agent_name = agent_func_name.replace("_agent", "")
    
    # Add decorator before function
    content = content.replace(
        f"async def {agent_func_name}(state: BuilderState) -> BuilderState:",
        f"@with_timeout(timeout_seconds={timeout})\nasync def {agent_func_name}(state: BuilderState) -> dict[str, Any]:"
    )
    
    # Replace the function body start
    old_start = f'''    logger.info("Starting'''
    new_start = f'''    agent_name = "{agent_name}"
    started_at = datetime.utcnow().isoformat()
    
    logger.info(f"[{{agent_name}}] Starting'''
    
    content = content.replace(old_start, new_start, 1)
    
    # Add retry check after log_progress
    retry_check = f'''
    # Check retry count
    retry_count = state.get("retry_counts", {{}}).get(agent_name, 0)
    max_retries = state.get("MAX_RETRIES", 5)
    
    if retry_count >= max_retries:
        logger.error(f"[{{agent_name}}] Max retries ({{max_retries}}) exhausted")
        completed_at = datetime.utcnow().isoformat()
        duration_ms = int((datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000)
        
        return {{
            "agent_failed": True,
            "agent_history": [{{
                "agent_name": agent_name,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "error": f"Max retries ({{max_retries}}) exhausted",
                "logs": None,
            }}],
            "validation_errors": [{{
                "agent": agent_name,
                "code": "MAX_RETRIES_EXHAUSTED",
                "message": f"Agent failed after {{max_retries}} retries",
                "field": None,
                "severity": "error",
            }}]
        }}
    
    try:'''
    
    # Find where to insert retry check (after first log_progress)
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if 'log_progress(state, "Starting' in line and agent_name in line:
            # Insert retry check after this line
            lines.insert(i + 1, retry_check)
            break
    
    content = "\n".join(lines)
    
    return content


def migrate_agent_file(filepath: str, timeout: int) -> bool:
    """Migrate a single agent file."""
    path = Path(filepath)
    
    if not path.exists():
        print(f"  ⚠️  File not found: {filepath}")
        return False
    
    print(f"  📝 Migrating {path.name}...")
    
    content = path.read_text()
    
    # Step 1: Add imports
    content = add_imports(content)
    
    # Step 2: Migrate function signature and add retry logic
    content = migrate_agent_function(content, timeout)
    
    # Write back
    path.write_text(content)
    
    print(f"  ✅ Migrated {path.name}")
    return True


def main():
    """Main migration function."""
    print("🚀 Starting batch agent migration...")
    print(f"📊 Total agents to migrate: {len(AGENTS_TO_MIGRATE)}\n")
    
    success_count = 0
    failed_count = 0
    
    for filepath, timeout in AGENTS_TO_MIGRATE:
        try:
            if migrate_agent_file(filepath, timeout):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"  ❌ Error migrating {filepath}: {e}")
            failed_count += 1
    
    print(f"\n✨ Migration complete!")
    print(f"✅ Successfully migrated: {success_count}")
    print(f"❌ Failed: {failed_count}")


if __name__ == "__main__":
    main()
