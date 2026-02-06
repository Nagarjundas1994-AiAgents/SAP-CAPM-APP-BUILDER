"""
LangGraph Shared State Schema
Defines the global state passed between all agents in the workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict, Literal


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
    # Agent Execution State
    # -------------------------------------------------------------------------
    current_agent: str
    agent_history: list[AgentExecution]
    
    # -------------------------------------------------------------------------
    # Validation Results
    # -------------------------------------------------------------------------
    validation_errors: list[ValidationError]
    compliance_status: str
    
    # -------------------------------------------------------------------------
    # Generated Artifacts (by category)
    # -------------------------------------------------------------------------
    artifacts_db: list[GeneratedFile]  # db/ folder files
    artifacts_srv: list[GeneratedFile]  # srv/ folder files
    artifacts_app: list[GeneratedFile]  # app/ folder files
    artifacts_deployment: list[GeneratedFile]  # mta.yaml, xs-security, etc.
    artifacts_docs: list[GeneratedFile]  # README, guides
    
    # -------------------------------------------------------------------------
    # Generation Metadata
    # -------------------------------------------------------------------------
    generation_status: str  # GenerationStatus value
    generation_started_at: str | None
    generation_completed_at: str | None
    
    # -------------------------------------------------------------------------
    # LLM Provider
    # -------------------------------------------------------------------------
    llm_provider: str | None


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
        
        # Execution
        current_agent="",
        agent_history=[],
        
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
        
        # LLM
        llm_provider=None,
    )
