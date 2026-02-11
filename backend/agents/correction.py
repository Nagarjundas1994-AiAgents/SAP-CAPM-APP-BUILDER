"""
Correction Prompt Generator

Generates intelligent correction prompts for the LLM when validation fails.
Includes context from the original task, specific errors, and hints for fixing.
"""

import logging
from typing import Any

from backend.agents.state import BuilderState
from backend.agents.validator import ValidationResult, extract_error_context

logger = logging.getLogger(__name__)


CORRECTION_SYSTEM_PROMPT = """You are an expert SAP CAP developer tasked with fixing code errors.

You will receive:
1. The original task requirements
2. The code you previously generated
3. Specific validation errors found in that code

Your job is to:
- Analyze the errors carefully
- Fix ONLY the issues mentioned in the error report
- Maintain the original logic and structure where possible
- Follow SAP CAP best practices

Return the corrected code in the same JSON format as before.
"""


def generate_correction_prompt(
    agent_name: str,
    original_task: str,
    generated_output: dict[str, Any],
    validation_results: list[ValidationResult],
    state: BuilderState
) -> str:
    """
    Generate a correction prompt for the LLM to fix validation errors.
    
    Args:
        agent_name: Name of the agent that generated the code
        original_task: The original task prompt sent to the agent
        generated_output: The output that failed validation (usually a dict with file content)
        validation_results: List of validation results with errors
        state: Current builder state for context
        
    Returns:
        A detailed correction prompt
    """
    error_context = extract_error_context(validation_results)
    
    # Count errors by type
    error_count = sum(result.error_count for result in validation_results)
    warning_count = sum(result.warning_count for result in validation_results)
    
    # Build the correction prompt
    prompt_parts = [
        f"## Correction Required for {agent_name}",
        f"",
        f"Your previous generation had {error_count} error(s) and {warning_count} warning(s).",
        f"",
        f"### Original Task:",
        f"{original_task}",
        f"",
        f"### Validation Errors Found:",
        f"{error_context}",
        f"",
        f"### Instructions:",
        f"1. Fix all ERROR-level issues (these prevent the code from working)",
        f"2. Address WARNING-level issues if possible (these are best practice violations)",
        f"3. Maintain the same output structure and format",
        f"4. Do not change unrelated code",
        f"",
    ]
    
    # Add agent-specific hints
    if agent_name == "data_modeling":
        prompt_parts.extend([
            f"### CDS Best Practices Reminder:",
            f"- All entities should have a key field",
            f"- Use proper CDS types: String, Integer, Decimal, UUID, DateTime, etc.",
            f"- Include namespace declaration at the top",
            f"- Use aspects like `managed` or `cuid` for common patterns",
            f"",
        ])
    elif agent_name == "service_exposure":
        prompt_parts.extend([
            f"### Service Definition Best Practices:",
            f"- Use `@odata.draft.enabled` for editable entities",
            f"- Include proper Fiori annotations",
            f"- Expose related entities for navigation",
            f"",
        ])
    elif agent_name == "business_logic":
        prompt_parts.extend([
            f"### Business Logic Best Practices:",
            f"- Use async/await for all handlers",
            f"- Use cds.log() instead of console.log",
            f"- Validate input data before processing",
            f"- Use req.error() for user-facing errors",
            f"",
        ])
    elif agent_name == "deployment":
        prompt_parts.extend([
            f"### Deployment File Best Practices:",
            f"- Ensure valid JSON syntax",
            f"- Include all required dependencies",
            f"- Use proper version constraints (e.g., ^7 for @sap/cds)",
            f"",
        ])
    
    prompt_parts.append(f"Now, please generate the corrected code:")
    
    return "\n".join(prompt_parts)


def should_retry_agent(validation_results: list[ValidationResult], retry_count: int, max_retries: int = 3) -> bool:
    """
    Determine if an agent should retry based on validation results.
    
    Args:
        validation_results: Results from validation
        retry_count: Current retry count for this agent
        max_retries: Maximum allowed retries
        
    Returns:
        True if should retry, False otherwise
    """
    # Don't retry if we've hit the max
    if retry_count >= max_retries:
        logger.warning(f"Max retries ({max_retries}) reached")
        return False
    
    # Check if there are any errors
    has_errors = any(result.has_errors for result in validation_results)
    
    if not has_errors:
        return False
    
    # Log retry decision
    error_count = sum(result.error_count for result in validation_results)
    logger.info(f"Retry needed: {error_count} errors found, attempt {retry_count + 1}/{max_retries}")
    
    return True


def format_correction_summary(
    agent_name: str,
    original_errors: int,
    fixed_errors: int,
    retry_count: int
) -> str:
    """
    Format a human-readable summary of the correction process.
    
    This will be shown in the UI to let users know what was auto-fixed.
    """
    if fixed_errors == original_errors:
        status = "✅ All errors fixed"
    elif fixed_errors > 0:
        status = f"⚠️ {fixed_errors}/{original_errors} errors fixed"
    else:
        status = f"❌ Could not fix errors"
    
    return f"{agent_name}: {status} (after {retry_count} attempt{'' if retry_count == 1 else 's'})"
