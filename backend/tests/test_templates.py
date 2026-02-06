"""
Tests for Jinja2 Template Engine
"""

import pytest
import json

from backend.templates import (
    render_cds_schema,
    render_service_cds,
    render_manifest_json,
    render_mta_yaml,
    render_xs_security,
)


class TestCDSTemplates:
    """Tests for CDS template rendering."""

    def test_render_schema_basic(self):
        """Test rendering basic CDS schema."""
        entities = [
            {
                "name": "Customer",
                "description": "Customer entity",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True},
                    {"name": "name", "type": "String(100)", "nullable": False},
                ]
            }
        ]
        
        result = render_cds_schema("com.test", entities)
        
        assert "namespace com.test" in result
        assert "entity Customer" in result
        assert "key ID : UUID" in result

    def test_render_schema_with_associations(self):
        """Test rendering schema with associations."""
        entities = [
            {
                "name": "Order",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True},
                ],
                "associations": [
                    {"name": "customer", "target": "Customer"}
                ]
            }
        ]
        
        result = render_cds_schema("com.test", entities)
        
        assert "Association to Customer" in result

    def test_render_service_cds(self):
        """Test rendering service definition."""
        result = render_service_cds(
            namespace="com.test",
            service_name="CatalogService",
            entities=["Customer", "Order"],
            draft_enabled=True,
        )
        
        assert "CatalogService" in result
        assert "projection on db.Customer" in result
        assert "@odata.draft.enabled" in result


class TestFioriTemplates:
    """Tests for Fiori template rendering."""

    def test_render_manifest_json(self):
        """Test rendering Fiori manifest.json."""
        result = render_manifest_json(
            app_id="com.test.app",
            app_title="Test App",
            service_path="/odata/v4/catalog",
            main_entity="Customer",
            theme="sap_horizon",
        )
        
        # Parse as JSON to validate
        manifest = json.loads(result)
        
        assert manifest["sap.app"]["id"] == "com.test.app"
        assert "Customer" in str(manifest["sap.ui5"]["routing"])


class TestDeploymentTemplates:
    """Tests for deployment template rendering."""

    def test_render_mta_yaml(self):
        """Test rendering mta.yaml."""
        modules = [
            {
                "name": "test-srv",
                "type": "nodejs",
                "path": "gen/srv",
            }
        ]
        resources = [
            {
                "name": "test-db",
                "type": "com.sap.xs.hdi-container",
            }
        ]
        
        result = render_mta_yaml(
            project_id="test-project",
            project_name="Test Project",
            modules=modules,
            resources=resources,
        )
        
        assert "ID: test-project" in result
        assert "test-srv" in result

    def test_render_xs_security(self):
        """Test rendering xs-security.json."""
        scopes = [
            {"name": "Read", "description": "Read access"},
            {"name": "Write", "description": "Write access"},
        ]
        roles = [
            {"name": "Viewer", "description": "Viewer role", "scopes": ["Read"]},
            {"name": "Editor", "description": "Editor role", "scopes": ["Read", "Write"]},
        ]
        
        result = render_xs_security(
            xsappname="test-app",
            scopes=scopes,
            roles=roles,
        )
        
        # Parse as JSON to validate
        security = json.loads(result)
        
        assert security["xsappname"] == "test-app"
        assert len(security["scopes"]) == 2
        assert len(security["role-templates"]) == 2
