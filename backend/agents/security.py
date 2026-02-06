"""
Agent 6: Security & Authorization Agent

Generates SAP BTP security configurations including xs-security.json,
CDS @requires annotations, and mock user configurations.
"""

import logging
import json
from datetime import datetime
from typing import Any

from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    RoleDefinition,
    RestrictionDefinition,
    GeneratedFile,
    ValidationError,
    AuthType,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Default Security Configuration
# =============================================================================

DEFAULT_ROLES = [
    {
        "name": "Viewer",
        "description": "Read-only access to all data",
        "scopes": ["read"],
    },
    {
        "name": "Editor",
        "description": "Read and write access to data",
        "scopes": ["read", "write"],
    },
    {
        "name": "Admin",
        "description": "Full access including delete",
        "scopes": ["read", "write", "delete", "admin"],
    },
]


# =============================================================================
# Security Generation
# =============================================================================

def generate_xs_security_json(state: BuilderState) -> str:
    """Generate xs-security.json for XSUAA configuration."""
    project_name = state.get("project_name", "App")
    namespace = state.get("project_namespace", "com.company.app")
    roles = state.get("roles", []) or DEFAULT_ROLES
    
    # XSUAA app name (must be unique)
    xsapp_name = project_name.lower().replace(" ", "-").replace("_", "-")
    
    # Build scopes
    scopes = []
    all_scope_names = set()
    
    for role in roles:
        for scope in role.get("scopes", []):
            scope_name = f"$XSAPPNAME.{scope}"
            if scope not in all_scope_names:
                all_scope_names.add(scope)
                scopes.append({
                    "name": scope_name,
                    "description": f"{scope.title()} scope"
                })
    
    # Build role templates
    role_templates = []
    for role in roles:
        scope_refs = [f"$XSAPPNAME.{s}" for s in role.get("scopes", [])]
        role_templates.append({
            "name": role.get("name", "Role"),
            "description": role.get("description", ""),
            "scope-references": scope_refs
        })
    
    # Build role collections
    role_collections = []
    for role in roles:
        role_collections.append({
            "name": f"{project_name}{role.get('name', 'Role')}",
            "description": f"{role.get('name', 'Role')} role collection",
            "role-template-references": [
                f"$XSAPPNAME.{role.get('name', 'Role')}"
            ]
        })
    
    xs_security = {
        "xsappname": xsapp_name,
        "tenant-mode": "dedicated",
        "description": f"Security configuration for {project_name}",
        "scopes": scopes,
        "role-templates": role_templates,
        "role-collections": role_collections,
        "oauth2-configuration": {
            "redirect-uris": [
                "https://*.cfapps.*.hana.ondemand.com/**",
                "https://*.hana.ondemand.com/**",
                "http://localhost:*/**"
            ]
        }
    }
    
    return json.dumps(xs_security, indent=4)


def generate_auth_annotations_cds(state: BuilderState) -> str:
    """Generate CDS authorization annotations."""
    entities = state.get("entities", [])
    roles = state.get("roles", []) or DEFAULT_ROLES
    restrictions = state.get("restrictions", [])
    
    lines = []
    lines.append("// Authorization Annotations")
    lines.append("// Apply @requires and @restrict for entity-level security")
    lines.append("")
    lines.append("using from './service';")
    lines.append("")
    
    # If no custom restrictions, generate default based on roles
    if not restrictions:
        for entity in entities:
            entity_name = entity.get("name", "Entity")
            
            lines.append(f"annotate {entity_name} with @(restrict: [")
            
            # Generate restrictions based on default roles
            for i, role in enumerate(roles):
                role_name = role.get("name", "Role")
                scopes = role.get("scopes", [])
                
                grants = []
                if "read" in scopes:
                    grants.append("READ")
                if "write" in scopes:
                    grants.extend(["CREATE", "UPDATE"])
                if "delete" in scopes or "admin" in scopes:
                    grants.append("DELETE")
                
                grants_str = ", ".join(grants)
                comma = "," if i < len(roles) - 1 else ""
                lines.append(f"    {{ grant: [{grants_str}], to: '{role_name}' }}{comma}")
            
            lines.append("]);")
            lines.append("")
    else:
        # Use custom restrictions
        for restriction in restrictions:
            entity = restriction.get("entity", "")
            grants = restriction.get("grants", [])
            to_role = restriction.get("to_role", "")
            where_cond = restriction.get("where_condition", "")
            
            grants_str = ", ".join(grants)
            
            lines.append(f"annotate {entity} with @(restrict: [")
            if where_cond:
                lines.append(f"    {{ grant: [{grants_str}], to: '{to_role}', where: '{where_cond}' }}")
            else:
                lines.append(f"    {{ grant: [{grants_str}], to: '{to_role}' }}")
            lines.append("]);")
            lines.append("")
    
    return "\n".join(lines)


def generate_mock_users_csv(state: BuilderState) -> str:
    """Generate mock users for local testing."""
    roles = state.get("roles", []) or DEFAULT_ROLES
    
    lines = []
    lines.append("username;password;roles")
    
    # Create a user for each role
    for role in roles:
        role_name = role.get("name", "Role")
        username = role_name.lower()
        lines.append(f"{username};{username}123;{role_name}")
    
    # Add admin user with all roles
    all_roles = ",".join([r.get("name", "") for r in roles])
    lines.append(f"admin;admin123;{all_roles}")
    
    return "\n".join(lines)


def generate_auth_cds(state: BuilderState) -> str:
    """Generate auth.cds for require annotations."""
    auth_type = state.get("auth_type", AuthType.MOCK.value)
    
    lines = []
    lines.append("// Authentication Configuration")
    lines.append("")
    
    if auth_type == AuthType.MOCK.value:
        lines.append("// Using mock authentication for development")
        lines.append("// Configure .cdsrc.json with [requires].auth.kind = 'mock'")
    else:
        lines.append("// Using XSUAA authentication")
        lines.append("// Ensure xs-security.json is deployed to BTP")
    
    lines.append("")
    lines.append("using from './service';")
    lines.append("")
    lines.append("// Require authentication for all service endpoints")
    lines.append("annotate CatalogService with @(requires: 'authenticated-user');")
    
    return "\n".join(lines)


def generate_cdsrc_json(state: BuilderState) -> str:
    """Generate .cdsrc.json with auth configuration."""
    auth_type = state.get("auth_type", AuthType.MOCK.value)
    
    config = {
        "requires": {
            "auth": {
                "kind": "mock" if auth_type == AuthType.MOCK.value else "xsuaa"
            }
        }
    }
    
    if auth_type == AuthType.MOCK.value:
        config["requires"]["auth"]["users"] = {
            "viewer": {"roles": ["Viewer"]},
            "editor": {"roles": ["Editor"]},
            "admin": {"roles": ["Admin"]}
        }
    
    return json.dumps(config, indent=4)


# =============================================================================
# Main Agent Function
# =============================================================================

async def security_agent(state: BuilderState) -> BuilderState:
    """
    Security & Authorization Agent
    
    Generates:
    1. xs-security.json - XSUAA configuration
    2. srv/auth.cds - Authentication annotations
    3. srv/auth-annotations.cds - Authorization restrictions
    4. .cdsrc.json - CDS runtime auth config
    5. test/data/mock-users.csv - Mock users for testing
    
    Returns updated state with security configuration files.
    """
    logger.info("Starting Security Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    generated_files: list[GeneratedFile] = []
    
    # Update state
    state["current_agent"] = "security"
    state["updated_at"] = now
    
    # Ensure default roles exist
    if not state.get("roles"):
        state["roles"] = DEFAULT_ROLES
    
    # ==========================================================================
    # Generate xs-security.json
    # ==========================================================================
    try:
        xs_security = generate_xs_security_json(state)
        generated_files.append({
            "path": "xs-security.json",
            "content": xs_security,
            "file_type": "json",
        })
        logger.info("Generated xs-security.json")
    except Exception as e:
        logger.error(f"Failed to generate xs-security.json: {e}")
        errors.append({
            "agent": "security",
            "code": "XS_SECURITY_ERROR",
            "message": f"Failed to generate xs-security.json: {str(e)}",
            "field": None,
            "severity": "error",
        })
    
    # ==========================================================================
    # Generate auth annotations
    # ==========================================================================
    try:
        auth_annotations = generate_auth_annotations_cds(state)
        generated_files.append({
            "path": "srv/auth-annotations.cds",
            "content": auth_annotations,
            "file_type": "cds",
        })
        logger.info("Generated srv/auth-annotations.cds")
    except Exception as e:
        logger.error(f"Failed to generate auth annotations: {e}")
    
    # ==========================================================================
    # Generate .cdsrc.json
    # ==========================================================================
    try:
        cdsrc = generate_cdsrc_json(state)
        generated_files.append({
            "path": ".cdsrc.json",
            "content": cdsrc,
            "file_type": "json",
        })
        logger.info("Generated .cdsrc.json")
    except Exception as e:
        logger.error(f"Failed to generate .cdsrc.json: {e}")
    
    # ==========================================================================
    # Generate mock users (for development)
    # ==========================================================================
    try:
        mock_users = generate_mock_users_csv(state)
        generated_files.append({
            "path": "test/data/mock-users.csv",
            "content": mock_users,
            "file_type": "csv",
        })
        logger.info("Generated test/data/mock-users.csv")
    except Exception as e:
        logger.error(f"Failed to generate mock users: {e}")
    
    # ==========================================================================
    # Update state
    # ==========================================================================
    state["artifacts_deployment"] = state.get("artifacts_deployment", []) + generated_files
    state["validation_errors"] = state.get("validation_errors", []) + errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "security",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
    }]
    
    logger.info(f"Security Agent completed. Generated {len(generated_files)} files.")
    
    return state
