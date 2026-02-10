"""
Agent 6: Security & Authorization Agent

Generates SAP BTP security configurations including xs-security.json,
CDS @requires annotations, and mock user configurations.

Uses LLM to generate production-quality security configs with fallback to templates.
"""

import logging
import json
import re
from datetime import datetime
from typing import Any

from backend.agents.llm_providers import get_llm_manager
from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    GeneratedFile,
    ValidationError,
    AuthType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts for LLM
# =============================================================================

SECURITY_SYSTEM_PROMPT = """You are an expert SAP BTP security architect specializing in XSUAA, CAP authorization, and Cloud Foundry security models.
Your task is to generate production-ready security configurations for SAP CAP applications.

STRICT RULES:
1. xs-security.json must follow SAP XSUAA schema with proper xsappname, tenant-mode, scopes, role-templates, role-collections
2. Scopes must follow naming convention "$XSAPPNAME.<scope>" 
3. Role templates must reference scopes correctly
4. CDS auth annotations must use @requires, @restrict with proper grant/to syntax
5. Use RBAC (Role-Based Access Control) with Viewer, Editor, Admin roles minimum
6. For draft-enabled entities, include proper draft authorization
7. Mock users must cover all roles for testing
8. .cdsrc.json must enable authentication for production
9. Add instance-based authorization where entity ownership applies
10. Follow SAP's principle of least privilege

OUTPUT FORMAT:
Return your response as valid JSON:
{
  "xs_security_json": { ... complete xs-security.json object ... },
  "auth_cds": "... full content of srv/auth.cds ...",
  "auth_annotations_cds": "... full content of srv/auth-annotations.cds ...", 
  "cdsrc_json": { ... complete .cdsrc.json object ... },
  "mock_users_csv": "... CSV content for test users ..."
}

Do NOT include markdown code fences in the JSON values. Return ONLY the JSON object."""


SECURITY_GENERATION_PROMPT = """Generate complete security configuration for this SAP CAP project.

Project Name: {project_name}
Project Namespace: {namespace}
Auth Type: {auth_type}

Service Definition:
```
{service_content}
```

Schema:
```
{schema_content}
```

Entities:
{entities_json}

Business Rules:
{business_rules_json}

Requirements:
1. xs-security.json:
   - xsappname: "{xsappname}"
   - tenant-mode: "dedicated"
   - Scopes: Read, Write, Delete, Admin (each with $XSAPPNAME prefix)
   - Role Templates: Viewer (Read), Editor (Read+Write), Admin (all)
   - Role Collections mapped to role templates

2. srv/auth.cds:
   - using from './service'
   - @requires annotations for the service
   - Entity-level @restrict with grant/to for fine-grained access

3. srv/auth-annotations.cds:
   - Detailed @restrict annotations per entity
   - READ -> Viewer role, WRITE/UPDATE -> Editor, DELETE -> Admin
   - For entities with status fields: restrict status changes to appropriate roles

4. .cdsrc.json:
   - Authentication strategy for CAP
   - Mock users configuration for development

5. Mock users CSV with columns: username;password;roles
   - viewer-user, editor-user, admin-user with appropriate roles

Respond with ONLY valid JSON."""


# =============================================================================
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


def _parse_llm_response(response_text: str) -> dict | None:
    try:
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None


# =============================================================================
# Template Fallback Functions
# =============================================================================

DEFAULT_ROLES = [
    {"name": "Viewer", "description": "Read-only access", "scopes": ["read"]},
    {"name": "Editor", "description": "Read and write access", "scopes": ["read", "write"]},
    {"name": "Admin", "description": "Full access", "scopes": ["read", "write", "delete", "admin"]},
]


def generate_xs_security_json(state: BuilderState) -> str:
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    xsappname = project_name.lower().replace(" ", "-").replace("_", "-")
    
    scopes = []
    for scope in ["read", "write", "delete", "admin"]:
        scopes.append({"name": f"$XSAPPNAME.{scope}", "description": f"{scope.capitalize()} access"})
    
    role_templates = []
    role_collections = []
    for role in DEFAULT_ROLES:
        role_templates.append({
            "name": role["name"],
            "description": role["description"],
            "scope-references": [f"$XSAPPNAME.{s}" for s in role["scopes"]]
        })
        role_collections.append({
            "name": f"{project_name}_{role['name']}",
            "description": role["description"],
            "role-template-references": [f"$XSAPPNAME.{role['name']}"]
        })
    
    xs_security = {
        "xsappname": xsappname,
        "tenant-mode": "dedicated",
        "scopes": scopes,
        "role-templates": role_templates,
        "role-collections": role_collections
    }
    return json.dumps(xs_security, indent=4)


def generate_auth_annotations_cds(state: BuilderState) -> str:
    entities = state.get("entities", [])
    lines = ["// Authorization Annotations", "", "using from './service';", ""]
    for entity in entities:
        name = entity.get("name", "Entity")
        lines.append(f"annotate {name} with @(restrict: [")
        lines.append("    { grant: 'READ', to: 'Viewer' },")
        lines.append("    { grant: ['READ', 'WRITE'], to: 'Editor' },")
        lines.append("    { grant: '*', to: 'Admin' }")
        lines.append("]);")
        lines.append("")
    return "\n".join(lines)


def generate_mock_users_csv() -> str:
    return """username;password;roles
viewer-user;pass123;Viewer
editor-user;pass123;Editor
admin-user;pass123;Admin"""


def generate_auth_cds(state: BuilderState) -> str:
    return """// Authentication Configuration
using from './service';

// Require authentication for the service
// annotate <ServiceName> with @(requires: 'authenticated-user');
"""


def generate_cdsrc_json(state: BuilderState) -> str:
    return json.dumps({
        "[production]": {
            "requires": {
                "auth": {"kind": "xsuaa"}
            }
        },
        "[development]": {
            "requires": {
                "auth": {"kind": "mocked", "users": {
                    "admin-user": {"password": "pass123", "roles": ["Admin", "Viewer", "Editor"]},
                    "editor-user": {"password": "pass123", "roles": ["Editor", "Viewer"]},
                    "viewer-user": {"password": "pass123", "roles": ["Viewer"]}
                }}
            }
        }
    }, indent=4)


# =============================================================================
# Main Agent Function
# =============================================================================

async def security_agent(state: BuilderState) -> BuilderState:
    """
    Security & Authorization Agent (LLM-Driven)
    
    Uses LLM to generate production-quality security configurations.
    Falls back to template-based generation if LLM fails.
    """
    logger.info("Starting Security Agent (LLM-Driven)")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    state["current_agent"] = "security"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting security configuration generation...")
    
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    auth_type = state.get("auth_type", AuthType.XSUAA.value)
    entities = state.get("entities", [])
    business_rules = state.get("business_rules", [])
    provider = state.get("llm_provider")
    xsappname = project_name.lower().replace(" ", "-").replace("_", "-")
    
    schema_content = ""
    service_content = ""
    for artifact in state.get("artifacts_db", []):
        if artifact.get("path") == "db/schema.cds":
            schema_content = artifact.get("content", "")
    for artifact in state.get("artifacts_srv", []):
        if artifact.get("path") == "srv/service.cds":
            service_content = artifact.get("content", "")
    
    llm_success = False
    
    # ==========================================================================
    # Attempt LLM-driven generation
    # ==========================================================================
    try:
        llm_manager = get_llm_manager()
        
        prompt = SECURITY_GENERATION_PROMPT.format(
            project_name=project_name,
            namespace=namespace,
            auth_type=auth_type,
            service_content=service_content or "(not available)",
            schema_content=schema_content or "(not available)",
            entities_json=json.dumps(entities, indent=2),
            business_rules_json=json.dumps(business_rules, indent=2),
            xsappname=xsappname,
        )
        
        log_progress(state, "Calling LLM for security configuration generation...")
        
        response = await llm_manager.generate(
            prompt=prompt,
            system_prompt=SECURITY_SYSTEM_PROMPT,
            provider=provider,
            temperature=0.1,
        )
        
        parsed = _parse_llm_response(response)
        
        if parsed and parsed.get("xs_security_json"):
            xs_data = parsed["xs_security_json"]
            if isinstance(xs_data, dict):
                generated_files.append({"path": "xs-security.json", "content": json.dumps(xs_data, indent=4), "file_type": "json"})
            else:
                generated_files.append({"path": "xs-security.json", "content": str(xs_data), "file_type": "json"})
            
            if parsed.get("auth_cds"):
                generated_files.append({"path": "srv/auth.cds", "content": parsed["auth_cds"], "file_type": "cds"})
            if parsed.get("auth_annotations_cds"):
                generated_files.append({"path": "srv/auth-annotations.cds", "content": parsed["auth_annotations_cds"], "file_type": "cds"})
            if parsed.get("cdsrc_json"):
                cdsrc = parsed["cdsrc_json"]
                generated_files.append({"path": ".cdsrc.json", "content": json.dumps(cdsrc, indent=4) if isinstance(cdsrc, dict) else str(cdsrc), "file_type": "json"})
            if parsed.get("mock_users_csv"):
                generated_files.append({"path": "test/data/mock-users.csv", "content": parsed["mock_users_csv"], "file_type": "csv"})
            
            log_progress(state, "LLM-generated security configuration accepted.")
            llm_success = True
        else:
            log_progress(state, "Could not parse LLM response. Falling back to template.")
    
    except Exception as e:
        logger.warning(f"LLM generation failed for security: {e}")
        log_progress(state, f"LLM call failed ({str(e)[:80]}). Falling back to template.")
    
    # ==========================================================================
    # Fallback: Template-based generation
    # ==========================================================================
    if not llm_success:
        log_progress(state, "Generating security config via template fallback...")
        try:
            generated_files.append({"path": "xs-security.json", "content": generate_xs_security_json(state), "file_type": "json"})
            generated_files.append({"path": "srv/auth.cds", "content": generate_auth_cds(state), "file_type": "cds"})
            generated_files.append({"path": "srv/auth-annotations.cds", "content": generate_auth_annotations_cds(state), "file_type": "cds"})
            generated_files.append({"path": ".cdsrc.json", "content": generate_cdsrc_json(state), "file_type": "json"})
            generated_files.append({"path": "test/data/mock-users.csv", "content": generate_mock_users_csv(), "file_type": "csv"})
        except Exception as e:
            logger.error(f"Template fallback failed for security: {e}")
            errors.append({"agent": "security", "code": "SECURITY_ERROR", "message": f"Security generation failed: {str(e)}", "field": None, "severity": "error"})
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_security"] = state.get("artifacts_security", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "security",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    generation_method = "LLM" if llm_success else "template fallback"
    log_progress(state, f"Security configuration complete ({generation_method}).")
    logger.info(f"Security Agent completed via {generation_method}. Generated {len(generated_files)} files.")
    
    return state
