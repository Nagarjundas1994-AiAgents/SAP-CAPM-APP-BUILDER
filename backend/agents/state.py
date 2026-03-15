"""
LangGraph Shared State Schema
Defines the global state passed between all agents in the workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict, Literal, Annotated
import operator


# =============================================================================
# Enums
# =============================================================================

class DomainType(str, Enum):
    """Pre-defined domain templates."""
    CUSTOM = "custom"
    ECOMMERCE = "ecommerce"
    HR = "hr"
    FINANCE = "finance"
    INVENTORY = "inventory"
    CRM = "crm"


class CAPRuntime(str, Enum):
    """CAP runtime options."""
    NODEJS = "nodejs"
    JAVA = "java"


class DatabaseType(str, Enum):
    """Database options."""
    SQLITE = "sqlite"
    HANA = "hana"


class ODataVersion(str, Enum):
    """OData protocol versions."""
    V2 = "v2"
    V4 = "v4"


class FioriAppType(str, Enum):
    """Fiori Elements app types."""
    LIST_REPORT = "list_report"
    OBJECT_PAGE = "object_page"
    ANALYTICAL_LIST_PAGE = "alp"
    OVERVIEW_PAGE = "overview_page"
    WORKLIST = "worklist"
    FREESTYLE = "freestyle"


class LayoutMode(str, Enum):
    """Fiori layout modes."""
    SINGLE = "single"
    FLEXIBLE_COLUMN = "flexible_column"
    FULL_PAGE = "full_page"


class FioriTheme(str, Enum):
    """SAP Fiori themes."""
    SAP_FIORI_3 = "sap_fiori_3"
    SAP_HORIZON = "sap_horizon"
    SAP_QUARTZ_DARK = "sap_quartz_dark"


class AuthType(str, Enum):
    """Authentication types."""
    MOCK = "mock"
    XSUAA = "xsuaa"
    IAS = "ias"


class DeploymentTarget(str, Enum):
    """Deployment targets."""
    LOCAL = "local"
    CF = "cf"
    KYMA = "kyma"


class CICDPlatform(str, Enum):
    """CI/CD platform options."""
    GITHUB_ACTIONS = "github_actions"
    AZURE_DEVOPS = "azure_devops"
    GITLAB_CI = "gitlab_ci"


class GenerationStatus(str, Enum):
    """Overall generation status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ComplexityLevel(str, Enum):
    """Application complexity level — controls generation depth."""
    STARTER = "starter"          # 2-3 entities, basic CRUD, mock auth
    STANDARD = "standard"        # 4-6 entities, draft, validations, roles
    ENTERPRISE = "enterprise"    # 6-10 entities, workflows, integrations, analytics, multi-app
    FULL_STACK = "full_stack"    # 8-15 entities, everything + testing + CI/CD + monitoring


# =============================================================================
# Component Type Definitions
# =============================================================================

class FieldDefinition(TypedDict, total=False):
    """Entity field definition."""
    name: str
    type: str  # String, Integer, Decimal, Date, DateTime, Boolean, UUID, etc.
    length: int | None
    precision: int | None
    scale: int | None
    key: bool
    nullable: bool
    default: Any
    annotations: dict[str, Any]


class EntityDefinition(TypedDict, total=False):
    """CDS entity definition."""
    name: str
    description: str | None
    fields: list[FieldDefinition]
    aspects: list[str]  # cuid, managed, temporal
    annotations: dict[str, Any]


class RelationshipDefinition(TypedDict, total=False):
    """Entity relationship definition."""
    name: str
    source_entity: str
    target_entity: str
    type: Literal["association", "composition"]
    cardinality: Literal["1:1", "1:n", "n:1", "n:m"]
    on_condition: str | None
    annotations: dict[str, Any]


class BusinessRule(TypedDict, total=False):
    """Business rule definition."""
    name: str
    description: str
    entity: str
    rule_type: Literal["validation", "calculation", "authorization", "workflow"]
    condition: str
    action: str


class RoleDefinition(TypedDict, total=False):
    """Security role definition."""
    name: str
    description: str | None
    scopes: list[str]


class IntegrationDefinition(TypedDict, total=False):
    """External service integration definition."""
    name: str
    system: Literal["S4HANA", "SuccessFactors", "Ariba", "Custom REST", "Custom OData"]
    description: str | None
    endpoint: str | None
    auth_type: Literal["Basic", "OAuth2", "PrincipalPropagation", "None"]


class ServiceModuleDefinition(TypedDict, total=False):
    """Logical service grouping for enterprise-oriented projects."""
    name: str
    purpose: str
    entities: list[str]
    exposure_type: Literal["transactional", "catalog", "analytics", "admin", "integration"]


class UIAppDefinition(TypedDict, total=False):
    """Generated UI application plan."""
    name: str
    main_entity: str
    app_type: Literal["list_report", "worklist", "overview_page", "analytical_list_page"]
    service_module: str


class VerificationCheck(TypedDict, total=False):
    """Single verification or readiness gate result."""
    name: str
    status: Literal["passed", "failed", "skipped", "warning"]
    details: str


class EnterpriseBlueprint(TypedDict, total=False):
    """High-level enterprise architecture plan for the generated app."""
    solution_type: str
    domain_summary: str
    service_modules: list[ServiceModuleDefinition]
    ui_apps: list[UIAppDefinition]
    quality_gates: list[str]
    deployment_modules: list[str]
    architecture_decisions: list[str]
    delivery_scope: list[str]


class RestrictionDefinition(TypedDict, total=False):
    """Entity access restriction."""
    entity: str
    grants: list[Literal["READ", "CREATE", "UPDATE", "DELETE", "*"]]
    to_role: str
    where_condition: str | None


class GeneratedFile(TypedDict):
    """Generated file artifact."""
    path: str
    content: str
    file_type: str


class ValidationError(TypedDict):
    """Validation error details."""
    agent: str
    code: str
    message: str
    field: str | None
    severity: Literal["error", "warning"]


class AgentExecution(TypedDict):
    """Agent execution record."""
    agent_name: str
    status: Literal["pending", "running", "completed", "failed", "skipped"]
    started_at: str | None
    completed_at: str | None
    duration_ms: int | None
    error: str | None
    logs: list[str] | None


# =============================================================================
# Global State Schema
# =============================================================================

class BuilderState(TypedDict, total=False):
    """
    Global shared state for the LangGraph agent workflow.
    This state is passed between all agents and updated at each step.
    """
    
    # -------------------------------------------------------------------------
    # Session Identity
    # -------------------------------------------------------------------------
    session_id: str
    created_at: str
    updated_at: str
    
    # -------------------------------------------------------------------------
    # Project Configuration
    # -------------------------------------------------------------------------
    project_name: str
    project_namespace: str
    project_description: str
    
    # -------------------------------------------------------------------------
    # Domain Configuration
    # -------------------------------------------------------------------------
    domain_type: str  # DomainType value
    entities: list[EntityDefinition]
    relationships: list[RelationshipDefinition]
    business_rules: list[BusinessRule]
    integrations: list[IntegrationDefinition]
    
    # -------------------------------------------------------------------------
    # CAP Configuration
    # -------------------------------------------------------------------------
    cap_runtime: str  # CAPRuntime value
    database_type: str  # DatabaseType value
    odata_version: str  # ODataVersion value
    multitenancy_enabled: bool
    draft_enabled: bool
    generate_sample_data: bool
    
    # -------------------------------------------------------------------------
    # Fiori Configuration
    # -------------------------------------------------------------------------
    fiori_app_type: str  # FioriAppType value
    fiori_layout_mode: str  # LayoutMode value
    fiori_theme: str  # FioriTheme value
    fiori_main_entity: str
    fiori_extensions_enabled: bool
    
    # -------------------------------------------------------------------------
    # Security Configuration
    # -------------------------------------------------------------------------
    auth_type: str  # AuthType value
    roles: list[RoleDefinition]
    restrictions: list[RestrictionDefinition]
    
    # -------------------------------------------------------------------------
    # Deployment Configuration
    # -------------------------------------------------------------------------
    deployment_target: str  # DeploymentTarget value
    ci_cd_enabled: bool
    ci_cd_platform: str | None  # CICDPlatform value
    docker_enabled: bool
    
    # -------------------------------------------------------------------------
    # Complexity Level
    # -------------------------------------------------------------------------
    complexity_level: str  # ComplexityLevel value — controls generation depth

    # -------------------------------------------------------------------------
    # LLM Configuration (NEW)
    # -------------------------------------------------------------------------
    llm_provider: str | None  # User-selected LLM provider (openai, gemini, xai, etc.)
    llm_model: str | None  # User-selected model name (grok-4-1-fast-reasoning, etc.)

    # -------------------------------------------------------------------------
    # Enterprise Architecture Planning
    # -------------------------------------------------------------------------
    enterprise_blueprint: EnterpriseBlueprint
    architecture_context_md: str
    service_modules: list[ServiceModuleDefinition]
    ui_apps: list[UIAppDefinition]
    quality_gates: list[str]

    # -------------------------------------------------------------------------
    # Agent Execution State
    # -------------------------------------------------------------------------
    current_agent: str
    agent_history: Annotated[list[AgentExecution], operator.add]
    current_logs: Annotated[list[str], operator.add]
    
    # -------------------------------------------------------------------------
    # Self-Healing / Retry Tracking (UPGRADED)
    # -------------------------------------------------------------------------
    retry_counts: dict[str, int]  # Per-agent retry counter {"data_modeling": 2}
    correction_history: Annotated[list[dict[str, Any]], operator.add]  # Track what was corrected
    auto_fixed_errors: Annotated[list[dict[str, Any]], operator.add]  # Success stories for analytics
    needs_correction: bool  # Flag to trigger retry in workflow
    agent_failed: bool  # True when max retries exhausted
    MAX_RETRIES: int  # Default 3, configurable per agent
    validation_retry_count: int  # Number of self-healing correction loops completed
    correction_agent: str | None  # Agent to route back to for correction
    correction_context: dict | None  # { "issues": [...], "correction_prompt": "..." }
    
    # -------------------------------------------------------------------------
    # Human Gate State (NEW)
    # -------------------------------------------------------------------------
    current_gate: str | None  # ID of gate currently waiting
    human_feedback: str | None  # Notes from human reviewer
    gate_decisions: dict[str, str]  # History of all gate decisions
    
    # -------------------------------------------------------------------------
    # RAG / Documentation (NEW)
    # -------------------------------------------------------------------------
    retrieved_docs: dict[str, list]  # Docs retrieved per agent {"data_modeling": [...]}
    validation_rules_applied: Annotated[list[str], operator.add]  # Rules checked during validation
    
    # -------------------------------------------------------------------------
    # Parallel Phase Tracking (NEW)
    # -------------------------------------------------------------------------
    parallel_phase_results: dict[str, dict]  # Results from each parallel branch
    
    # -------------------------------------------------------------------------
    # New Agent Outputs (NEW)
    # -------------------------------------------------------------------------
    domain_model: dict | None
    integration_spec: dict | None
    error_handling_spec: dict | None
    audit_logging_spec: dict | None
    api_governance_spec: dict | None
    ux_design_spec: dict | None
    i18n_bundles: dict | None
    multitenancy_config: dict | None
    feature_flags_config: dict | None
    compliance_report: dict | None
    performance_report: dict | None
    ci_cd_config: dict | None
    observability_config: dict | None
    documentation_bundle: dict | None
    
    # -------------------------------------------------------------------------
    # Model Routing (NEW)
    # -------------------------------------------------------------------------
    model_tier: dict[str, str]  # {"agent_name": "opus|sonnet|haiku"}
    
    # -------------------------------------------------------------------------
    # Validation Results
    # -------------------------------------------------------------------------
    validation_errors: Annotated[list[ValidationError], operator.add]
    compliance_status: str
    
    # -------------------------------------------------------------------------
    # Generated Artifacts (by category)
    # -------------------------------------------------------------------------
    artifacts_db: Annotated[list[GeneratedFile], operator.add]  # db/ folder files
    artifacts_srv: Annotated[list[GeneratedFile], operator.add]  # srv/ folder files
    artifacts_app: Annotated[list[GeneratedFile], operator.add]  # app/ folder files
    artifacts_deployment: Annotated[list[GeneratedFile], operator.add]  # mta.yaml, xs-security, etc.
    artifacts_docs: Annotated[list[GeneratedFile], operator.add]  # README, guides
    
    # -------------------------------------------------------------------------
    # Generation Metadata
    # -------------------------------------------------------------------------
    generation_status: str  # GenerationStatus value
    generation_started_at: str | None
    generation_completed_at: str | None
    generated_workspace_path: str | None
    generated_manifest: dict[str, Any] | None
    verification_checks: Annotated[list[VerificationCheck], operator.add]
    verification_summary: dict[str, Any] | None

    # -------------------------------------------------------------------------
    # Inter-Agent Context (agents see each other's actual output)
    # -------------------------------------------------------------------------
    generated_schema_cds: str      # Actual db/schema.cds from data_modeling agent
    generated_common_cds: str      # Actual db/common.cds from data_modeling agent
    generated_service_cds: str     # Actual srv/service.cds from service_exposure agent
    generated_annotations_cds: str # Actual srv/annotations.cds from service_exposure agent
    generated_handler_js: str      # Actual srv/service.js from business_logic agent
    generated_manifest_json: str   # Actual manifest.json from fiori_ui agent




def create_initial_state(
    session_id: str,
    project_name: str,
    project_namespace: str = "",
    project_description: str = "",
) -> BuilderState:
    """Create an initial empty state for a new session."""
    now = datetime.utcnow().isoformat()
    
    return BuilderState(
        # Session
        session_id=session_id,
        created_at=now,
        updated_at=now,
        
        # Project
        project_name=project_name,
        project_namespace=project_namespace or f"com.company.{project_name.lower().replace('-', '_')}",
        project_description=project_description,
        
        # Domain
        domain_type=DomainType.CUSTOM.value,
        entities=[],
        relationships=[],
        business_rules=[],
        integrations=[],
        
        # CAP
        cap_runtime=CAPRuntime.NODEJS.value,
        database_type=DatabaseType.SQLITE.value,
        odata_version=ODataVersion.V4.value,
        multitenancy_enabled=False,
        draft_enabled=True,
        generate_sample_data=True,
        
        # Fiori
        fiori_app_type=FioriAppType.LIST_REPORT.value,
        fiori_layout_mode=LayoutMode.FLEXIBLE_COLUMN.value,
        fiori_theme=FioriTheme.SAP_HORIZON.value,
        fiori_main_entity="",
        fiori_extensions_enabled=False,
        
        # Security
        auth_type=AuthType.MOCK.value,
        roles=[],
        restrictions=[],
        
        # Deployment
        deployment_target=DeploymentTarget.LOCAL.value,
        ci_cd_enabled=False,
        ci_cd_platform=None,
        docker_enabled=False,
        
        # Complexity
        complexity_level=ComplexityLevel.STANDARD.value,

        # Enterprise Architecture
        enterprise_blueprint={},
        architecture_context_md="",
        service_modules=[],
        ui_apps=[],
        quality_gates=[],

        # Execution
        current_agent="",
        agent_history=[],
        current_logs=[],
        
        # Validation
        validation_errors=[],
        compliance_status="pending",
        
        # Artifacts
        artifacts_db=[],
        artifacts_srv=[],
        artifacts_app=[],
        artifacts_deployment=[],
        artifacts_docs=[],
        
        # Generation
        generation_status=GenerationStatus.PENDING.value,
        generation_started_at=None,
        generation_completed_at=None,
        generated_workspace_path=None,
        generated_manifest=None,
        verification_checks=[],
        verification_summary=None,

        # Inter-Agent Context
        generated_schema_cds="",
        generated_common_cds="",
        generated_service_cds="",
        generated_annotations_cds="",
        generated_handler_js="",
        generated_manifest_json="",
        
        # Self-Healing
        needs_correction=False,
        validation_retry_count=0,
        correction_agent=None,
        correction_context=None,
        agent_failed=False,
        MAX_RETRIES=5,
        retry_counts={},
        correction_history=[],
        auto_fixed_errors=[],
        
        # Human Gate State
        current_gate=None,
        human_feedback=None,
        gate_decisions={},
        
        # RAG / Documentation
        retrieved_docs={},
        validation_rules_applied=[],
        
        # Parallel Phase Tracking
        parallel_phase_results={},
        
        # New Agent Outputs
        domain_model=None,
        integration_spec=None,
        error_handling_spec=None,
        audit_logging_spec=None,
        api_governance_spec=None,
        ux_design_spec=None,
        i18n_bundles=None,
        multitenancy_config=None,
        feature_flags_config=None,
        compliance_report=None,
        performance_report=None,
        ci_cd_config=None,
        observability_config=None,
        documentation_bundle=None,
        
        # Model Routing
        model_tier={},
        
        # LLM
        llm_provider=None,
        llm_model=None,
    )
