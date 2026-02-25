"""
Agent 9: Automated Testing Agent (LLM-Driven)

Generates test scaffolding for SAP CAP applications including:
- Unit tests (Jest + cds.test) for service handlers
- Integration tests for OData endpoints
- Test configuration (jest.config.js)
- Test fixtures and sample data

COMPLEXITY-AWARE:
- starter: SKIP (no tests generated)
- standard: Unit tests + jest.config.js
- enterprise: Unit + integration tests + fixtures
- full_stack: Unit + integration + OPA5 stubs + full config

FULLY LLM-DRIVEN with inter-agent context.
"""

import json
import logging
from datetime import datetime

from backend.agents.llm_utils import (
    generate_with_retry,
    get_full_context,
    get_schema_context,
    get_service_context,
    get_handler_context,
)
from backend.agents.state import (
    BuilderState,
    GeneratedFile,
    ValidationError,
)
from backend.agents.progress import log_progress

logger = logging.getLogger(__name__)


TESTING_SYSTEM_PROMPT = """You are an SAP CAP testing expert.
Generate production-ready test files for SAP CAP applications using Jest and @sap/cds testing utilities.

STRICT RULES:

1. jest.config.js:
   - Use `@sap/cds/jest` preset
   - Set testTimeout to 20000 for integration tests
   - Coverage thresholds: branches 60%, functions 70%, lines 70%

2. Unit Tests (test/unit/*.test.js):
   - Use `cds.test(__dirname + '/../..')` for bootstrapping
   - Test EVERY custom action and event handler
   - Test input validations (reject bad data, accept good data)
   - Test calculated fields and auto-numbering
   - Test status transitions (valid and invalid)
   - Use `beforeAll` for CDS bootstrap, `afterEach` for cleanup
   - Use descriptive `describe`/`it` blocks

3. Integration Tests (test/integration/*.test.js):
   - Use `const { GET, POST, PUT, PATCH, DELETE, expect } = cds.test(__dirname + '/../..')`
   - Test OData CRUD endpoints with proper payloads
   - Test Draft lifecycle: POST (new) → PATCH (edit) → POST draftActivate
   - Test query options: $filter, $select, $expand, $orderby, $top, $skip
   - Test error scenarios: missing required fields, invalid status transitions
   - Test authorization: access with different mock users

4. Test structure:
   ```
   test/
   ├── unit/
   │   └── service.test.js
   ├── integration/
   │   └── odata.test.js
   └── fixtures/
       └── test-data.json
   ```

OUTPUT FORMAT:
{
    "jest_config_js": "... jest.config.js content ...",
    "unit_test_js": "... test/unit/service.test.js ...",
    "integration_test_js": "... test/integration/odata.test.js ...",
    "test_fixtures_json": "... test/fixtures/test-data.json ..."
}
Return ONLY valid JSON."""


TESTING_GENERATION_PROMPT = """Generate test files for this SAP CAP application.

Project: {project_name}
Namespace: {namespace}

{schema_context}
{service_context}
{handler_context}

ENTITIES:
{entities_json}

BUSINESS RULES:
{business_rules_json}

{scope_instructions}

Generate comprehensive tests covering:
1. jest.config.js — Jest configuration with @sap/cds preset
2. test/unit/service.test.js — Unit tests for all handlers and validations
3. test/integration/odata.test.js — OData endpoint integration tests
4. test/fixtures/test-data.json — Reusable test payloads

Respond with ONLY valid JSON."""


async def testing_agent(state: BuilderState) -> BuilderState:
    """Automated Testing Agent (LLM-Driven)"""
    logger.info("Starting Testing Agent (LLM-Driven)")

    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []

    state["current_agent"] = "testing"
    state["updated_at"] = now
    state["current_logs"] = []
    log_progress(state, "Starting testing phase...")

    # Check complexity level — skip for starter
    complexity = state.get("complexity_level", "standard")
    if complexity == "starter":
        log_progress(state, "⏭️ Skipping tests (Starter complexity). No tests generated.")
        state["agent_history"] = state.get("agent_history", []) + [{
            "agent_name": "testing",
            "status": "skipped",
            "started_at": now,
            "completed_at": datetime.utcnow().isoformat(),
            "duration_ms": None,
            "error": None,
            "logs": ["Skipped: Starter complexity level does not generate tests."],
        }]
        return state

    entities = state.get("entities", [])
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    business_rules = state.get("business_rules", [])

    schema_context = get_schema_context(state) or "(schema not available)"
    service_context = get_service_context(state) or "(service not available)"
    handler_context = get_handler_context(state) or "(handlers not available)"

    # Scope instructions based on complexity
    if complexity == "standard":
        scope_instructions = """SCOPE: Generate UNIT TESTS ONLY.
- jest.config.js
- test/unit/service.test.js (handler tests, validation tests)
- test/fixtures/test-data.json
Do NOT generate integration tests."""
    elif complexity == "enterprise":
        scope_instructions = """SCOPE: Generate UNIT + INTEGRATION TESTS.
- jest.config.js
- test/unit/service.test.js (handler tests, validation tests, workflow tests)
- test/integration/odata.test.js (CRUD, draft lifecycle, auth, query options)
- test/fixtures/test-data.json"""
    else:  # full_stack
        scope_instructions = """SCOPE: Generate COMPREHENSIVE test suite.
- jest.config.js
- test/unit/service.test.js (all handlers, validations, calculations, workflows)
- test/integration/odata.test.js (full CRUD, draft, auth, batch, error scenarios)
- test/fixtures/test-data.json (comprehensive fixtures for all entities)
Include inline comments explaining test strategy for each section."""

    prompt = TESTING_GENERATION_PROMPT.format(
        project_name=project_name,
        namespace=namespace,
        schema_context=schema_context,
        service_context=service_context,
        handler_context=handler_context,
        entities_json=json.dumps(entities, indent=2),
        business_rules_json=json.dumps(business_rules, indent=2),
        scope_instructions=scope_instructions,
    )

    # Self-Healing: Inject correction context if present
    correction_context = state.get("correction_context")
    if state.get("needs_correction") and state.get("correction_agent") == "testing" and correction_context:
        log_progress(state, "Applying self-healing correction context...")
        correction_prompt = correction_context.get("correction_prompt", "")
        if correction_prompt:
            prompt = f"CRITICAL CORRECTION REQUIRED:\n{correction_prompt}\n\nORIGINAL INSTRUCTIONS:\n{prompt}"

    log_progress(state, f"Calling LLM for test generation ({complexity} complexity)...")

    result = await generate_with_retry(
        prompt=prompt,
        system_prompt=TESTING_SYSTEM_PROMPT,
        state=state,
        required_keys=["jest_config_js"],
        max_retries=3,
        agent_name="testing",
    )

    if result:
        file_map = {
            "jest_config_js": ("jest.config.js", "javascript"),
            "unit_test_js": ("test/unit/service.test.js", "javascript"),
            "integration_test_js": ("test/integration/odata.test.js", "javascript"),
            "test_fixtures_json": ("test/fixtures/test-data.json", "json"),
        }
        for key, (path, file_type) in file_map.items():
            content = result.get(key, "")
            if content:
                generated_files.append({"path": path, "content": content, "file_type": file_type})

        log_progress(state, f"✅ Generated {len(generated_files)} test files.")
    else:
        log_progress(state, "⚠️ LLM failed. Generating minimal test config.")
        generated_files.extend(_minimal_tests(project_name, entities))
        errors.append({
            "agent": "testing",
            "code": "LLM_FAILED",
            "message": "LLM test generation failed. Minimal config generated.",
            "field": None,
            "severity": "warning",
        })

    # Store test files under artifacts_srv (alongside service code)
    existing = state.get("artifacts_srv", [])
    state["artifacts_srv"] = existing + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    state["needs_correction"] = False

    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "testing",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]

    log_progress(state, f"Testing complete. Generated {len(generated_files)} files.")
    return state


def _minimal_tests(project_name, entities):
    """Minimal test configuration."""
    jest_config = """module.exports = {
  preset: '@sap/cds/jest',
  testTimeout: 20000,
  collectCoverage: true,
  coverageReporters: ['text', 'lcov'],
};
"""
    entity_names = [e.get("name", "Entity") for e in entities]
    test_lines = [
        "'use strict';",
        "",
        "const cds = require('@sap/cds/lib');",
        "const { expect } = cds.test(__dirname + '/../..');",
        "",
        f"describe('{project_name} - Service Tests', () => {{",
        "",
        "  it('should serve the service', async () => {",
        "    const srv = await cds.connect.to('MainService');",
        "    expect(srv).toBeDefined();",
        "  });",
        "",
    ]
    for name in entity_names:
        test_lines.extend([
            f"  it('should read {name}', async () => {{",
            f"    const {{ data }} = await GET('/{name}');",
            f"    expect(data.value).toBeDefined();",
            "  });",
            "",
        ])
    test_lines.append("});")

    return [
        {"path": "jest.config.js", "content": jest_config, "file_type": "javascript"},
        {"path": "test/unit/service.test.js", "content": "\n".join(test_lines), "file_type": "javascript"},
    ]
