"""
Comprehensive Test Suite for Validation Module

Tests the enhanced validator with:
- CDS validation (balanced braces, key fields, types)
- JavaScript validation (missing exports, async/await)
- JSON validation (manifest, package.json, xs-security)
- YAML validation (mta.yaml structure)
- Cross-file consistency checking
- Quality scoring
"""

import pytest
import json
from backend.agents.validator import (
    validate_cds,
    validate_javascript,
    validate_json,
    validate_yaml,
    validate_best_practices,
    validate_artifact,
    validate_cross_file_consistency,
    compute_quality_score,
    ValidationSeverity,
)


# =============================================================================
# CDS Validation Tests
# =============================================================================

class TestCDSValidation:
    def test_valid_schema(self):
        content = """namespace com.test.app;
using { cuid, managed } from '@sap/cds/common';

entity Orders : cuid, managed {
    orderNumber : String(20) @mandatory;
    status      : String(20);
    items       : Composition of many OrderItems on items.parent = $self;
}

entity OrderItems : cuid {
    key ID   : UUID;
    parent   : Association to Orders;
    product  : String(100);
    quantity : Integer;
}
"""
        result = validate_cds(content, "db/schema.cds")
        assert result.is_valid
        assert result.error_count == 0

    def test_missing_namespace(self):
        content = "entity Foo { key ID : UUID; name : String; }"
        result = validate_cds(content, "db/schema.cds")
        warnings = [i for i in result.issues if i.code == "MISSING_NAMESPACE"]
        assert len(warnings) == 1

    def test_no_entities(self):
        content = "namespace com.test.app;\n// empty schema\n"
        result = validate_cds(content, "db/schema.cds")
        assert not result.is_valid
        errors = [i for i in result.issues if i.code == "NO_ENTITIES"]
        assert len(errors) == 1

    def test_unbalanced_braces(self):
        content = "namespace com.test;\nentity Foo {\n  key ID : UUID;\n"
        result = validate_cds(content, "db/schema.cds")
        errors = [i for i in result.issues if i.code == "UNBALANCED_BRACES"]
        assert len(errors) == 1

    def test_missing_key_field(self):
        content = "namespace com;\nentity Foo { name : String; }"
        result = validate_cds(content, "db/schema.cds")
        warnings = [i for i in result.issues if i.code == "NO_KEY_FIELD"]
        assert len(warnings) == 1


# =============================================================================
# JavaScript Validation Tests
# =============================================================================

class TestJavaScriptValidation:
    def test_valid_handler(self):
        content = """'use strict';
const cds = require('@sap/cds');
const LOG = cds.log('service');

module.exports = cds.service.impl(async function() {
    this.before('CREATE', 'Orders', async (req) => {
        LOG.info('Creating order');
    });
});"""
        result = validate_javascript(content, "srv/service.js")
        assert result.is_valid

    def test_missing_export(self):
        content = """const cds = require('@sap/cds');
function doStuff() { return 42; }"""
        result = validate_javascript(content, "srv/service.js")
        warnings = [i for i in result.issues if i.code == "NO_EXPORT"]
        assert len(warnings) == 1

    def test_console_log_warning(self):
        content = """module.exports = cds.service.impl(async function() {
    console.log('debug');
});"""
        result = validate_javascript(content, "srv/service.js")
        warnings = [i for i in result.issues if i.code == "CONSOLE_LOG"]
        assert len(warnings) == 1


# =============================================================================
# JSON Validation Tests
# =============================================================================

class TestJSONValidation:
    def test_valid_package_json(self):
        content = json.dumps({
            "name": "test-app",
            "dependencies": {"@sap/cds": "^7"},
            "scripts": {"start": "cds-serve"}
        })
        result = validate_json(content, "package.json")
        assert result.is_valid

    def test_invalid_json(self):
        result = validate_json("{ invalid json", "test.json")
        assert not result.is_valid

    def test_package_missing_name(self):
        result = validate_json(json.dumps({"dependencies": {}}), "package.json")
        assert not result.is_valid

    def test_package_missing_cds(self):
        result = validate_json(json.dumps({"name": "app", "dependencies": {}}), "package.json")
        warnings = [i for i in result.issues if i.code == "MISSING_CDS_DEP"]
        assert len(warnings) == 1

    def test_manifest_missing_sapapp(self):
        result = validate_json(json.dumps({"sap.ui5": {}}), "app/manifest.json")
        assert not result.is_valid

    def test_manifest_missing_ui5(self):
        result = validate_json(json.dumps({"sap.app": {}}), "app/manifest.json")
        errors = [i for i in result.issues if i.code == "MISSING_SAP_UI5"]
        assert len(errors) == 1

    def test_xs_security_missing_xsappname(self):
        result = validate_json(json.dumps({"scopes": []}), "xs-security.json")
        assert not result.is_valid


# =============================================================================
# Best Practices Tests
# =============================================================================

class TestBestPractices:
    def test_hardcoded_credentials(self):
        content = 'const password = "secret123";'
        result = validate_best_practices(content, "config.js", "javascript")
        errors = [i for i in result.issues if i.code == "HARDCODED_CREDENTIALS"]
        assert len(errors) == 1

    def test_commented_credentials_ignored(self):
        content = '// const password = "secret123";'
        result = validate_best_practices(content, "config.js", "javascript")
        errors = [i for i in result.issues if i.code == "HARDCODED_CREDENTIALS"]
        assert len(errors) == 0


# =============================================================================
# Cross-File Consistency Tests
# =============================================================================

class TestCrossFileConsistency:
    def test_consistent_entities(self):
        state = {
            "entities": [{"name": "Orders"}, {"name": "Products"}],
            "artifacts_db": [{
                "path": "db/schema.cds",
                "content": "entity Orders { key ID : UUID; }\nentity Products { key ID : UUID; }"
            }],
            "artifacts_srv": [{
                "path": "srv/service.cds",
                "content": "entity Orders as projection on db.Orders;\nentity Products as projection on db.Products;"
            }]
        }
        result = validate_cross_file_consistency(state)
        assert result.is_valid

    def test_missing_projection(self):
        state = {
            "entities": [{"name": "Orders"}, {"name": "Products"}],
            "artifacts_db": [{
                "path": "db/schema.cds",
                "content": "entity Orders { key ID : UUID; }\nentity Products { key ID : UUID; }"
            }],
            "artifacts_srv": [{
                "path": "srv/service.cds",
                "content": "entity Orders as projection on db.Orders;"
            }]
        }
        result = validate_cross_file_consistency(state)
        issues = [i for i in result.issues if i.code == "ENTITY_NOT_IN_SERVICE"]
        assert any("Products" in i.message for i in issues)


# =============================================================================
# Quality Scoring Tests
# =============================================================================

class TestQualityScoring:
    def test_basic_quality_score(self):
        state = {
            "artifacts_db": [{
                "path": "db/schema.cds",
                "content": "namespace com.test;\nusing { managed } from '@sap/cds/common';\nentity Orders : managed { key ID : UUID; @title:'Name' name : String; items : Composition of many Items; }"
            }],
            "artifacts_srv": [{
                "path": "srv/service.cds",
                "content": "entity Orders as projection on db.Orders;\n@odata.draft.enabled\naction approve() returns String;"
            }],
            "artifacts_app": [],
            "artifacts_security": [],
            "artifacts_deployment": [],
        }
        result = compute_quality_score(state)
        assert "total" in result
        assert "breakdown" in result
        assert 0 <= result["total"] <= 100
        assert result["breakdown"]["data_model"] > 0

    def test_empty_project_score(self):
        state = {
            "artifacts_db": [],
            "artifacts_srv": [],
            "artifacts_app": [],
            "artifacts_security": [],
            "artifacts_deployment": [],
        }
        result = compute_quality_score(state)
        assert result["total"] == 0


# =============================================================================
# Unified Validation Interface Tests
# =============================================================================

class TestValidateArtifact:
    def test_cds_file(self):
        results = validate_artifact("db/schema.cds", "namespace x;\nentity Foo { key ID : UUID; }")
        assert len(results) >= 1  # CDS + best_practices

    def test_json_file(self):
        results = validate_artifact("package.json", json.dumps({"name": "app", "dependencies": {"@sap/cds": "^7"}}))
        assert len(results) >= 1

    def test_js_file(self):
        results = validate_artifact("srv/service.js", "module.exports = cds.service.impl(async function() {});")
        assert len(results) >= 1
