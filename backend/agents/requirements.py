"""
Agent 1: Requirements & Domain Agent

Collects, analyzes, normalizes, and validates business requirements.
Transforms user intent into structured, SAP-compatible specifications.
"""

import logging
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.llm_providers import get_llm_manager
from backend.agents.state import (
    BuilderState,
    EntityDefinition,
    FieldDefinition,
    RelationshipDefinition,
    BusinessRule,
    DomainType,
    ValidationError,
)

logger = logging.getLogger(__name__)


# =============================================================================
# System Prompts
# =============================================================================

REQUIREMENTS_SYSTEM_PROMPT = """You are an expert SAP CAP (Cloud Application Programming Model) architect.
Your task is to analyze business requirements and convert them into structured specifications 
compatible with SAP CAP and Fiori Elements.

STRICT RULES:
1. ONLY use official SAP CAP patterns, CDS syntax, and Fiori Elements annotations
2. NEVER invent or hallucinate APIs, decorators, or patterns that don't exist in SAP documentation
3. Follow SAP naming conventions: PascalCase for entities, camelCase for fields
4. Ensure all entity names are valid CDS identifiers (no spaces, special characters)
5. Always include key fields for entities (preferably UUID primary keys)

When analyzing requirements:
1. Identify all business entities and their attributes
2. Determine relationships between entities (association vs composition)
3. Identify validation rules and business logic
4. Suggest appropriate SAP aspects (cuid, managed, temporal)
5. Flag any requirements that cannot be implemented in SAP CAP

Respond ONLY with valid JSON matching the expected schema."""


ENTITY_EXTRACTION_PROMPT = """Analyze the following project description and extract entity definitions.

Project Name: {project_name}
Description: {description}
Domain Type: {domain_type}

Extract entities with their fields. For each entity, provide:
- name: PascalCase entity name
- description: Brief description
- fields: Array of field definitions with:
  - name: camelCase field name
  - type: CDS type (String, Integer, Decimal, Date, DateTime, Boolean, UUID, LargeString, etc.)
  - length: For String types (optional)
  - key: true for primary key fields
  - nullable: true/false
- aspects: Array of SAP aspects to apply (cuid, managed, temporal)

Respond with JSON only:
{{
  "entities": [...],
  "relationships": [...],
  "business_rules": [...]
}}"""


# =============================================================================
# Domain Templates
# =============================================================================

DOMAIN_TEMPLATES: dict[str, dict[str, Any]] = {
    DomainType.ECOMMERCE.value: {
        "entities": [
            {
                "name": "Product",
                "description": "Product catalog item",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "price", "type": "Decimal", "precision": 10, "scale": 2, "nullable": False},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "stock", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "imageUrl", "type": "String", "length": 500, "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Category",
                "description": "Product category",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "name", "type": "String", "length": 50, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Order",
                "description": "Customer order",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "orderNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "orderDate", "type": "DateTime", "nullable": False},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'New'"},
                    {"name": "totalAmount", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "OrderItem",
                "description": "Order line item",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False},
                    {"name": "unitPrice", "type": "Decimal", "precision": 10, "scale": 2, "nullable": False},
                    {"name": "totalPrice", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False},
                ],
                "aspects": ["cuid"],
            },
        ],
        "relationships": [
            {"name": "category", "source_entity": "Product", "target_entity": "Category", "type": "association", "cardinality": "n:1"},
            {"name": "items", "source_entity": "Order", "target_entity": "OrderItem", "type": "composition", "cardinality": "1:n"},
            {"name": "product", "source_entity": "OrderItem", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "validateStock", "entity": "OrderItem", "rule_type": "validation", "description": "Check product stock before order"},
            {"name": "calculateTotal", "entity": "OrderItem", "rule_type": "calculation", "description": "Calculate total from quantity * unitPrice"},
        ],
    },
    DomainType.INVENTORY.value: {
        "entities": [
            {
                "name": "Product",
                "description": "Inventory product",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "sku", "type": "String", "length": 50, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "unitOfMeasure", "type": "String", "length": 10, "nullable": False},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Warehouse",
                "description": "Storage location",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 20, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "address", "type": "LargeString", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "InventoryLevel",
                "description": "Stock level per product per warehouse",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "minQuantity", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "maxQuantity", "type": "Integer", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
        ],
        "relationships": [
            {"name": "product", "source_entity": "InventoryLevel", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
            {"name": "warehouse", "source_entity": "InventoryLevel", "target_entity": "Warehouse", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "lowStockAlert", "entity": "InventoryLevel", "rule_type": "validation", "description": "Alert when quantity below minimum"},
        ],
    },
}


# =============================================================================
# Validation Functions
# =============================================================================

def validate_project_name(name: str) -> list[ValidationError]:
    """Validate project name follows SAP conventions."""
    errors: list[ValidationError] = []
    
    if not name:
        errors.append({
            "agent": "requirements",
            "code": "PROJECT_NAME_REQUIRED",
            "message": "Project name is required",
            "field": "project_name",
            "severity": "error",
        })
        return errors
    
    if len(name) < 3:
        errors.append({
            "agent": "requirements",
            "code": "PROJECT_NAME_TOO_SHORT",
            "message": "Project name must be at least 3 characters",
            "field": "project_name",
            "severity": "error",
        })
    
    if len(name) > 50:
        errors.append({
            "agent": "requirements",
            "code": "PROJECT_NAME_TOO_LONG",
            "message": "Project name must be 50 characters or less",
            "field": "project_name",
            "severity": "error",
        })
    
    if not name[0].isalpha():
        errors.append({
            "agent": "requirements",
            "code": "PROJECT_NAME_INVALID_START",
            "message": "Project name must start with a letter",
            "field": "project_name",
            "severity": "error",
        })
    
    if not all(c.isalnum() or c in "-_ " for c in name):
        errors.append({
            "agent": "requirements",
            "code": "PROJECT_NAME_INVALID_CHARS",
            "message": "Project name can only contain letters, numbers, spaces, hyphens, and underscores",
            "field": "project_name",
            "severity": "error",
        })
    
    return errors


def validate_entity_name(name: str) -> list[ValidationError]:
    """Validate entity name follows CDS conventions."""
    errors: list[ValidationError] = []
    
    if not name:
        errors.append({
            "agent": "requirements",
            "code": "ENTITY_NAME_REQUIRED",
            "message": "Entity name is required",
            "field": "entity_name",
            "severity": "error",
        })
        return errors
    
    # Must be PascalCase (start with uppercase)
    if not name[0].isupper():
        errors.append({
            "agent": "requirements",
            "code": "ENTITY_NAME_NOT_PASCAL_CASE",
            "message": f"Entity name '{name}' must start with uppercase (PascalCase)",
            "field": "entity_name",
            "severity": "warning",
        })
    
    # Only alphanumeric
    if not name.isalnum():
        errors.append({
            "agent": "requirements",
            "code": "ENTITY_NAME_INVALID_CHARS",
            "message": f"Entity name '{name}' can only contain letters and numbers",
            "field": "entity_name",
            "severity": "error",
        })
    
    return errors


def validate_entities(entities: list[EntityDefinition]) -> list[ValidationError]:
    """Validate entity definitions."""
    errors: list[ValidationError] = []
    
    if not entities:
        errors.append({
            "agent": "requirements",
            "code": "NO_ENTITIES",
            "message": "At least one entity must be defined",
            "field": "entities",
            "severity": "error",
        })
        return errors
    
    entity_names = set()
    for entity in entities:
        name = entity.get("name", "")
        
        # Check for duplicate names
        if name in entity_names:
            errors.append({
                "agent": "requirements",
                "code": "DUPLICATE_ENTITY_NAME",
                "message": f"Duplicate entity name: {name}",
                "field": "entities",
                "severity": "error",
            })
        entity_names.add(name)
        
        # Validate entity name
        errors.extend(validate_entity_name(name))
        
        # Check for key field
        fields = entity.get("fields", [])
        has_key = any(f.get("key", False) for f in fields)
        if not has_key:
            errors.append({
                "agent": "requirements",
                "code": "NO_KEY_FIELD",
                "message": f"Entity '{name}' must have at least one key field",
                "field": "entities",
                "severity": "error",
            })
    
    return errors


def generate_fallback_entities(user_entities: list) -> list:
    """Generate basic entity definitions when LLM fails.
    
    Creates standard fields for each entity provided by the user.
    """
    generated = []
    
    for entity in user_entities:
        name = entity.get("name", "Entity")
        
        # Generate standard fields based on entity name
        fields = [
            {"name": "ID", "type": "UUID", "key": True, "nullable": False},
            {"name": "name", "type": "String", "length": 100, "nullable": False},
            {"name": "description", "type": "LargeString", "nullable": True},
            {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
        ]
        
        # Add some common fields based on entity name patterns
        name_lower = name.lower()
        if "order" in name_lower or "invoice" in name_lower:
            fields.extend([
                {"name": "orderDate", "type": "DateTime", "nullable": False},
                {"name": "totalAmount", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False},
                {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
            ])
        elif "product" in name_lower or "item" in name_lower:
            fields.extend([
                {"name": "price", "type": "Decimal", "precision": 10, "scale": 2, "nullable": False},
                {"name": "quantity", "type": "Integer", "nullable": False, "default": "0"},
            ])
        elif "customer" in name_lower or "user" in name_lower or "employee" in name_lower:
            fields.extend([
                {"name": "email", "type": "String", "length": 255, "nullable": True},
                {"name": "phone", "type": "String", "length": 50, "nullable": True},
            ])
        elif "incident" in name_lower or "ticket" in name_lower or "issue" in name_lower:
            fields.extend([
                {"name": "priority", "type": "String", "length": 20, "nullable": False, "default": "'Medium'"},
                {"name": "category", "type": "String", "length": 50, "nullable": True},
                {"name": "assignedTo", "type": "String", "length": 100, "nullable": True},
                {"name": "resolvedDate", "type": "DateTime", "nullable": True},
            ])
        
        generated.append({
            "name": name,
            "description": f"{name} entity",
            "fields": fields,
            "aspects": ["cuid", "managed"],
        })
    
    return generated


# =============================================================================
# Main Agent Function
# =============================================================================

async def requirements_agent(state: BuilderState) -> BuilderState:
    """
    Requirements & Domain Agent
    
    Processes:
    1. Validates project configuration
    2. Normalizes domain type (template or custom)
    3. Extracts/generates entity definitions
    4. Identifies relationships
    5. Extracts business rules
    
    Returns updated state with entities, relationships, and business rules.
    """
    logger.info("Starting Requirements Agent")
    
    now = datetime.utcnow().isoformat()
    errors: list[ValidationError] = []
    
    # Update state
    state["current_agent"] = "requirements"
    state["updated_at"] = now
    
    # ==========================================================================
    # Step 1: Validate project configuration
    # ==========================================================================
    project_name = state.get("project_name", "")
    errors.extend(validate_project_name(project_name))
    
    if any(e["severity"] == "error" for e in errors):
        state["validation_errors"] = errors
        logger.error(f"Validation failed: {errors}")
        return state
    
    # ==========================================================================
    # Step 2: Process domain type
    # ==========================================================================
    domain_type = state.get("domain_type", DomainType.CUSTOM.value)
    
    if domain_type in DOMAIN_TEMPLATES and not state.get("entities"):
        # Use pre-defined template only if no entities already exist (e.g. from user approval)
        logger.info(f"Using domain template: {domain_type}")
        template = DOMAIN_TEMPLATES[domain_type]
        
        state["entities"] = template.get("entities", [])
        state["relationships"] = template.get("relationships", [])
        state["business_rules"] = template.get("business_rules", [])
    
    elif state.get("entities"):
        # User provided entities - check if they have fields defined
        user_entities = state.get("entities", [])
        entities_need_fields = any(not e.get("fields") for e in user_entities)
        
        if entities_need_fields:
            # Entities have no fields - use LLM to generate full entity definitions
            logger.info("User provided entity names but no fields. Using LLM to generate complete entity definitions.")
            
            try:
                llm_manager = get_llm_manager()
                provider = state.get("llm_provider")
                
                entity_names = [e.get("name", "") for e in user_entities]
                
                prompt = f"""Generate complete CDS entity definitions for the following entities in a {project_name} application.

Entity Names: {', '.join(entity_names)}
Project Description: {state.get('project_description', 'No description provided')}

For each entity, generate:
- name: The entity name (PascalCase)
- description: Brief description of what this entity represents
- fields: Array of fields with:
  - name: Field name (camelCase)  
  - type: CDS type (String, Integer, Decimal, Date, DateTime, Boolean, UUID, LargeString)
  - length: For String types (optional)
  - key: true for primary key (first field should be UUID key named "ID")
  - nullable: true/false
- aspects: ["cuid", "managed"] for audit fields

Also generate relationships between entities if applicable.

Respond with ONLY valid JSON:
{{
  "entities": [...],
  "relationships": [...],
  "business_rules": [...]
}}"""
                
                response = await llm_manager.generate(
                    prompt=prompt,
                    system_prompt=REQUIREMENTS_SYSTEM_PROMPT,
                    provider=provider,
                    temperature=0.1,
                )
                
                # Parse JSON response
                import json
                try:
                    response = response.strip()
                    if response.startswith("```json"):
                        response = response[7:]
                    if response.startswith("```"):
                        response = response[3:]
                    if response.endswith("```"):
                        response = response[:-3]
                    
                    extracted = json.loads(response.strip())
                    state["entities"] = extracted.get("entities", user_entities)
                    state["relationships"] = extracted.get("relationships", [])
                    state["business_rules"] = extracted.get("business_rules", [])
                    logger.info(f"LLM generated {len(state['entities'])} entities with fields")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response: {e}. Using fallback entity generation.")
                    # Fallback: generate basic fields for each entity
                    state["entities"] = generate_fallback_entities(user_entities)
                    
            except Exception as e:
                logger.error(f"LLM entity generation failed: {e}. Using fallback.")
                # Fallback: generate basic fields
                state["entities"] = generate_fallback_entities(user_entities)
        else:
            # Entities have fields - just validate
            logger.info("Validating user-provided entities with fields")
            errors.extend(validate_entities(user_entities))
    
    else:
        # Custom domain without entities - use LLM to extract from description
        logger.info("Extracting entities from description using LLM")
        
        description = state.get("project_description", "")
        if description:
            try:
                llm_manager = get_llm_manager()
                provider = state.get("llm_provider")
                
                prompt = ENTITY_EXTRACTION_PROMPT.format(
                    project_name=project_name,
                    description=description,
                    domain_type=domain_type,
                )
                
                response = await llm_manager.generate(
                    prompt=prompt,
                    system_prompt=REQUIREMENTS_SYSTEM_PROMPT,
                    provider=provider,
                    temperature=0.1,
                )
                
                # Parse JSON response
                import json
                try:
                    # Clean response if needed
                    response = response.strip()
                    if response.startswith("```json"):
                        response = response[7:]
                    if response.startswith("```"):
                        response = response[3:]
                    if response.endswith("```"):
                        response = response[:-3]
                    
                    extracted = json.loads(response)
                    state["entities"] = extracted.get("entities", [])
                    state["relationships"] = extracted.get("relationships", [])
                    state["business_rules"] = extracted.get("business_rules", [])
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
                    errors.append({
                        "agent": "requirements",
                        "code": "LLM_PARSE_ERROR",
                        "message": "Could not parse entity extraction response",
                        "field": None,
                        "severity": "warning",
                    })
            
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
                errors.append({
                    "agent": "requirements",
                    "code": "LLM_ERROR",
                    "message": f"Entity extraction failed: {str(e)}",
                    "field": None,
                    "severity": "warning",
                })
    
    # ==========================================================================
    # Step 3: Final validation
    # ==========================================================================
    errors.extend(validate_entities(state.get("entities", [])))
    
    # ==========================================================================
    # Step 4: Set main entity for Fiori if not set
    # ==========================================================================
    if not state.get("fiori_main_entity") and state.get("entities"):
        state["fiori_main_entity"] = state["entities"][0].get("name", "")
    
    # ==========================================================================
    # Step 5: Update state
    # ==========================================================================
    state["validation_errors"] = errors
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "requirements",
        "status": "completed" if not any(e["severity"] == "error" for e in errors) else "failed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None if not errors else str(errors[0]["message"]) if errors else None,
    }]
    
    logger.info(f"Requirements Agent completed. Entities: {len(state.get('entities', []))}, Errors: {len(errors)}")
    
    return state
