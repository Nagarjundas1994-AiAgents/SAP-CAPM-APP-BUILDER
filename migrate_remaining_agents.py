#!/usr/bin/env python3
"""
Script to migrate remaining agents to new architecture pattern.
Automates the repetitive parts of the migration.
"""

import re
from pathlib import Path

# Template for the migration
MIGRATION_TEMPLATE = """
# Add to imports
from backend.agents.resilience import with_timeout
from typing import Any

# Replace function signature
@with_timeout(timeout_seconds={timeout})
async def {agent_name}_agent(state: BuilderState) -> dict[str, Any]:

# Add at start of function
    agent_name = "{agent_name}"
    started_at = datetime.utcnow().isoformat()
    
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
"""

# List of agents to migrate with their timeout values
AGENTS_TO_MIGRATE = [
    ("ux_design", 120),
    ("testing", 180),
    ("security", 180),
    ("project_assembly", 60),
    ("project_verification", 120),
    ("performance_review", 120),
    ("observability", 120),
    ("multitenancy", 120),
    ("integration", 120),
    ("i18n", 60),
    ("feature_flags", 60),
    ("fiori_ui", 240),
    ("extension", 120),
    ("error_handling", 120),
    ("documentation", 120),
    ("deployment", 180),
    ("db_migration", 60),
    ("compliance_check", 120),
    ("ci_cd", 120),
    ("audit_logging", 120),
    ("business_logic", 240),
    ("api_governance", 120),
]

def main():
    print("Agent Migration Script")
    print("=" * 60)
    print(f"Found {len(AGENTS_TO_MIGRATE)} agents to migrate")
    print()
    
    for agent_name, timeout in AGENTS_TO_MIGRATE:
        agent_file = Path(f"backend/agents/{agent_name}.py")
        if not agent_file.exists():
            print(f"❌ {agent_name}: File not found")
            continue
        
        print(f"📝 {agent_name}: Ready for migration (timeout={timeout}s)")
    
    print()
    print("=" * 60)
    print("Manual migration required for each agent:")
    print("1. Add resilience import")
    print("2. Add @with_timeout decorator")
    print("3. Add retry count check")
    print("4. Wrap in try/except")
    print("5. Return partial state dict")
    print("6. Test with getDiagnostics")

if __name__ == "__main__":
    main()
