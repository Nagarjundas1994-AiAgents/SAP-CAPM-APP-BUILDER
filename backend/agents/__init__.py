"""
Agents Package - LangGraph Multi-Agent System
"""

from backend.agents.llm_providers import get_llm_manager, LLMManager
from backend.agents.graph import run_generation_workflow, get_builder_graph

# Agent functions (28 total)
from backend.agents.requirements import requirements_agent
from backend.agents.enterprise_architecture import enterprise_architecture_agent
from backend.agents.domain_modeling import domain_modeling_agent
from backend.agents.data_modeling import data_modeling_agent
from backend.agents.db_migration import db_migration_agent
from backend.agents.integration_design import integration_design_agent
from backend.agents.integration import integration_agent
from backend.agents.service_exposure import service_exposure_agent
from backend.agents.error_handling import error_handling_agent
from backend.agents.audit_logging import audit_logging_agent
from backend.agents.api_governance import api_governance_agent
from backend.agents.business_logic import business_logic_agent
from backend.agents.ux_design import ux_design_agent
from backend.agents.fiori_ui import fiori_ui_agent
from backend.agents.security import security_agent
from backend.agents.multitenancy import multitenancy_agent
from backend.agents.i18n import i18n_agent
from backend.agents.feature_flags import feature_flags_agent
from backend.agents.compliance_check import compliance_check_agent
from backend.agents.extension import extension_agent
from backend.agents.performance_review import performance_review_agent
from backend.agents.ci_cd import ci_cd_agent
from backend.agents.deployment import deployment_agent
from backend.agents.testing import testing_agent
from backend.agents.observability import observability_agent
from backend.agents.documentation import documentation_agent
from backend.agents.project_assembly import project_assembly_agent
from backend.agents.project_verification import project_verification_agent
from backend.agents.validation import validation_agent

__all__ = [
    "get_llm_manager",
    "LLMManager",
    "run_generation_workflow",
    "get_builder_graph",
    "requirements_agent",
    "enterprise_architecture_agent",
    "domain_modeling_agent",
    "data_modeling_agent",
    "db_migration_agent",
    "integration_design_agent",
    "integration_agent",
    "service_exposure_agent",
    "error_handling_agent",
    "audit_logging_agent",
    "api_governance_agent",
    "business_logic_agent",
    "ux_design_agent",
    "fiori_ui_agent",
    "security_agent",
    "multitenancy_agent",
    "i18n_agent",
    "feature_flags_agent",
    "compliance_check_agent",
    "extension_agent",
    "performance_review_agent",
    "ci_cd_agent",
    "deployment_agent",
    "testing_agent",
    "observability_agent",
    "documentation_agent",
    "project_assembly_agent",
    "project_verification_agent",
    "validation_agent",
]
