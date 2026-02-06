"""
Jinja2 Template Engine for SAP Code Generation

Provides template rendering for all SAP CAP + Fiori artifacts.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "jinja_templates"


@lru_cache()
def get_template_engine() -> Environment:
    """Get or create the Jinja2 template environment."""
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_template(template_name: str, context: dict[str, Any]) -> str:
    """
    Render a template with the given context.
    
    Args:
        template_name: Name of the template file (e.g., 'cds/schema.cds.j2')
        context: Dictionary of variables to pass to the template
        
    Returns:
        Rendered template content as string
    """
    env = get_template_engine()
    template = env.get_template(template_name)
    return template.render(**context)


def render_cds_schema(
    namespace: str,
    entities: list[dict[str, Any]],
    aspects: list[dict[str, Any]] | None = None,
) -> str:
    """Render CDS schema template."""
    return render_template(
        "cds/schema.cds.j2",
        {
            "namespace": namespace,
            "entities": entities,
            "aspects": aspects or [],
        },
    )


def render_service_cds(
    namespace: str,
    service_name: str,
    entities: list[str],
    odata_version: str = "v4",
    draft_enabled: bool = True,
) -> str:
    """Render service.cds template."""
    return render_template(
        "cds/service.cds.j2",
        {
            "namespace": namespace,
            "service_name": service_name,
            "entities": entities,
            "odata_version": odata_version,
            "draft_enabled": draft_enabled,
        },
    )


def render_manifest_json(
    app_id: str,
    app_title: str,
    service_path: str,
    main_entity: str,
    theme: str = "sap_horizon",
) -> str:
    """Render Fiori manifest.json template."""
    return render_template(
        "fiori/manifest.json.j2",
        {
            "app_id": app_id,
            "app_title": app_title,
            "service_path": service_path,
            "main_entity": main_entity,
            "theme": theme,
        },
    )


def render_mta_yaml(
    project_id: str,
    project_name: str,
    modules: list[dict[str, Any]],
    resources: list[dict[str, Any]],
) -> str:
    """Render mta.yaml template."""
    return render_template(
        "deployment/mta.yaml.j2",
        {
            "project_id": project_id,
            "project_name": project_name,
            "modules": modules,
            "resources": resources,
        },
    )


def render_xs_security(
    xsappname: str,
    scopes: list[dict[str, str]],
    roles: list[dict[str, Any]],
) -> str:
    """Render xs-security.json template."""
    return render_template(
        "security/xs-security.json.j2",
        {
            "xsappname": xsappname,
            "scopes": scopes,
            "roles": roles,
        },
    )
