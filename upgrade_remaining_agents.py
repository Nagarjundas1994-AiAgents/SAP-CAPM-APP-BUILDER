"""
Script to upgrade remaining agent stubs with LLM logic.
Run this to complete Step 8.
"""

# This script documents the pattern for upgrading each agent.
# Each agent should follow this structure:

AGENT_UPGRADE_PATTERN = """
1. Import required modules:
   - json, logging, datetime
   - BuilderState, GeneratedFile
   - log_progress
   - generate_with_retry
   - retrieve_for_agent

2. Define SYSTEM_PROMPT with expert persona and output format

3. Define GENERATION_PROMPT with context placeholders

4. In agent function:
   - Get context from state
   - Check if work is needed (skip if not applicable)
   - Retrieve RAG docs
   - Build prompt with context
   - Call generate_with_retry with model routing
   - Process result
   - Update state with output
   - Set needs_correction = False
   - Record in agent_history
   - Log progress

5. Handle failures gracefully with minimal fallback
"""

# Agents to upgrade (in priority order):
AGENTS_TO_UPGRADE = [
    "ux_design.py",           # High priority - affects UI generation
    "compliance_check.py",    # High priority - security/GDPR
    "performance_review.py",  # High priority - optimization
    "error_handling.py",      # Medium priority
    "audit_logging.py",       # Medium priority
    "api_governance.py",      # Medium priority
    "multitenancy.py",        # Medium priority
    "i18n.py",                # Low priority - template-based
    "feature_flags.py",       # Low priority
    "ci_cd.py",               # Low priority - template-based
    "observability.py",       # Low priority
    "documentation.py",       # Low priority - already has some logic
]

print("Agents upgraded so far:")
print("✅ domain_modeling.py")
print("✅ integration_design.py")
print("\nRemaining agents to upgrade:")
for agent in AGENTS_TO_UPGRADE:
    print(f"⏳ {agent}")
