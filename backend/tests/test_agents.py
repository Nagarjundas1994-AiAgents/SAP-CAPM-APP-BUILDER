"""
Unit Tests for Builder Agents
"""

import asyncio
from pathlib import Path
from unittest.mock import patch

from backend.agents.enterprise_architecture import enterprise_architecture_agent
from backend.agents.project_assembly import project_assembly_agent
from backend.agents.project_verification import project_verification_agent
from backend.agents.requirements import requirements_agent
from backend.agents.data_modeling import data_modeling_agent
from backend.agents.state import BuilderState, create_initial_state


def _run(coro):
    return asyncio.run(coro)


class TestRequirementsAgent:
    """Tests for Requirements Agent."""

    def test_requirements_agent_records_history(self, sample_builder_state):
        state = BuilderState(sample_builder_state)

        with patch(
            "backend.agents.requirements._generate_with_retry",
            return_value={
                "entities": state["entities"],
                "relationships": [],
                "business_rules": [],
            },
        ):
            result = _run(requirements_agent(state))

        assert result["current_agent"] == "requirements"
        assert result["agent_history"][-1]["agent_name"] == "requirements"
        assert "entities" in result


class TestDataModelingAgent:
    """Tests for Data Modeling Agent."""

    def test_data_modeling_creates_schema_artifact(self, sample_builder_state):
        state = BuilderState(sample_builder_state)

        with patch(
            "backend.agents.data_modeling.generate_with_retry",
            return_value={
                "common_cds": "namespace com.test;\ntype Currency : String(3);",
                "schema_cds": "namespace com.test;\nusing { cuid, managed } from '@sap/cds/common';\nentity Customer : cuid, managed { name : String(100); }",
                "sample_data": [],
            },
        ):
            result = _run(data_modeling_agent(state))

        assert result["current_agent"] == "data_modeling"
        assert any(artifact["path"] == "db/schema.cds" for artifact in result["artifacts_db"])
        schema = next(artifact for artifact in result["artifacts_db"] if artifact["path"] == "db/schema.cds")
        assert "managed" in schema["content"]


class TestEnterpriseAgents:
    """Tests for the enterprise-oriented deterministic agents."""

    def test_enterprise_architecture_generates_blueprint(self, sample_builder_state):
        state = BuilderState(sample_builder_state)
        state["integrations"] = [{"id": "s4hana_bp", "name": "BP", "system": "S4HANA"}]
        state["complexity_level"] = "enterprise"

        result = _run(enterprise_architecture_agent(state))

        assert result["enterprise_blueprint"]["solution_type"] == "enterprise_cap_fiori"
        assert result["service_modules"]
        assert any(artifact["path"] == "docs/ARCHITECTURE.md" for artifact in result["artifacts_docs"])

    def test_project_assembly_materializes_workspace(self, tmp_path):
        state = create_initial_state(
            session_id="assembly-test",
            project_name="Enterprise App",
            project_namespace="com.test.enterprise",
            project_description="Enterprise generation test",
        )
        state["artifacts_db"] = [{
            "path": "db/schema.cds",
            "content": "namespace com.test.enterprise;\nentity Customer { key ID : UUID; }",
            "file_type": "cds",
        }]
        state["artifacts_srv"] = [{
            "path": "srv/service.cds",
            "content": "using { com.test.enterprise as db } from '../db/schema';\nservice OperationsService { entity Customer as projection on db.Customer; }",
            "file_type": "cds",
        }]
        state["artifacts_app"] = [{
            "path": "app/customer/webapp/manifest.json",
            "content": '{"sap.app":{"id":"customer"},"sap.ui5":{}}',
            "file_type": "json",
        }]
        state["artifacts_deployment"] = [{
            "path": "xs-security.json",
            "content": '{"xsappname":"enterprise-app","scopes":[],"role-templates":[]}',
            "file_type": "json",
        }]
        state["artifacts_docs"] = [{
            "path": "docs/ARCHITECTURE.md",
            "content": "# Blueprint",
            "file_type": "md",
        }]

        with patch("backend.agents.project_assembly.get_settings") as mock_settings:
            mock_settings.return_value.artifacts_path = str(tmp_path)
            result = _run(project_assembly_agent(state))

        workspace = Path(result["generated_workspace_path"])
        assert workspace.exists()
        assert (workspace / "db/schema.cds").exists()
        assert (workspace / "docs/GENERATION_MANIFEST.json").exists()

    def test_project_verification_generates_report(self, tmp_path):
        workspace = tmp_path / "generated"
        (workspace / "db").mkdir(parents=True)
        (workspace / "srv").mkdir(parents=True)
        (workspace / "docs").mkdir(parents=True)
        (workspace / "app" / "customer" / "webapp").mkdir(parents=True)
        (workspace / "db" / "schema.cds").write_text("namespace com.test;\nentity Customer { key ID : UUID; }", encoding="utf-8")
        (workspace / "srv" / "service.cds").write_text(
            "using { com.test as db } from '../db/schema';\nservice OperationsService { @odata.draft.enabled entity Customer as projection on db.Customer; }",
            encoding="utf-8",
        )
        (workspace / "package.json").write_text('{"name":"test"}', encoding="utf-8")
        (workspace / "xs-security.json").write_text('{"xsappname":"test"}', encoding="utf-8")
        (workspace / "mta.yaml").write_text("ID: test", encoding="utf-8")
        (workspace / "docs" / "ARCHITECTURE.md").write_text("# Architecture", encoding="utf-8")
        (workspace / "docs" / "GENERATION_MANIFEST.json").write_text("{}", encoding="utf-8")
        (workspace / "app" / "customer" / "webapp" / "manifest.json").write_text(
            '{"sap.app":{"id":"customer"},"sap.ui5":{}}',
            encoding="utf-8",
        )

        state = create_initial_state(
            session_id="verification-test",
            project_name="Verification App",
        )
        state["generated_workspace_path"] = str(workspace)

        result = _run(project_verification_agent(state))

        assert result["verification_summary"]["failed"] == 0
        assert any(artifact["path"] == "docs/VERIFICATION_REPORT.md" for artifact in result["artifacts_docs"])
