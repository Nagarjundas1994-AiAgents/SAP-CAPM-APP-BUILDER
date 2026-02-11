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
# Helpers
# =============================================================================

from backend.agents.progress import log_progress


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
6. For diverse applications, ensure you include domain-specific fields (e.g., Currency for Finance, Dimensions for Logistics, etc.)
7. Use SAP CDS Types correctly: String, Integer, Decimal, Boolean, Date, DateTime, UUID, etc.

When analyzing requirements:
1. Identify all business entities and their attributes
2. Determine relationships between entities (association vs composition)
3. Identify validation rules and business logic
4. Suggest appropriate SAP aspects (cuid, managed, temporal)
5. Flag any requirements that cannot be implemented in SAP CAP

Respond ONLY with valid JSON matching the expected schema."""


ENTITY_EXTRACTION_PROMPT = """Analyze the following project description and extract detailed entity definitions. 
Go beyond generic entities; identify specific business objects relevant to the domain.

Project Name: {project_name}
Description: {description}
Domain Type: {domain_type}

Extract entities with their fields. For each entity, provide:
- name: PascalCase entity name
- description: Detailed business description
- fields: Array of field definitions with:
  - name: camelCase field name
  - type: CDS type
  - length: For String types (optional)
  - key: true for primary key fields
  - nullable: true/false
  - annotations: Object with optional SAP annotations like title, description, readonly, mandatory
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
    # =========================================================================
    # E-COMMERCE (6 Entities)
    # =========================================================================
    DomainType.ECOMMERCE.value: {
        "entities": [
            {
                "name": "Product",
                "description": "Product catalog item with pricing and inventory",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "productNumber", "type": "String", "length": 20, "nullable": False, "annotations": {"title": "Product No."}},
                    {"name": "name", "type": "String", "length": 100, "nullable": False, "annotations": {"title": "Product Name"}},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "price", "type": "Decimal", "precision": 10, "scale": 2, "nullable": False},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "stock", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "minStock", "type": "Integer", "nullable": False, "default": "10"},
                    {"name": "weight", "type": "Decimal", "precision": 8, "scale": 2, "nullable": True},
                    {"name": "weightUnit", "type": "String", "length": 5, "nullable": True, "default": "'KG'"},
                    {"name": "imageUrl", "type": "String", "length": 500, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Available'"},
                    {"name": "taxRate", "type": "Decimal", "precision": 5, "scale": 2, "nullable": False, "default": "0"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Category",
                "description": "Product category hierarchy",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 10, "nullable": False},
                    {"name": "name", "type": "String", "length": 50, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "sortOrder", "type": "Integer", "nullable": False, "default": "0"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Customer",
                "description": "Customer master data with contact and address info",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "customerNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "firstName", "type": "String", "length": 50, "nullable": False},
                    {"name": "lastName", "type": "String", "length": 50, "nullable": False},
                    {"name": "email", "type": "String", "length": 255, "nullable": False},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "street", "type": "String", "length": 100, "nullable": True},
                    {"name": "city", "type": "String", "length": 50, "nullable": True},
                    {"name": "postalCode", "type": "String", "length": 10, "nullable": True},
                    {"name": "country", "type": "String", "length": 3, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Order",
                "description": "Customer sales order with status workflow",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "orderNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "orderDate", "type": "DateTime", "nullable": False},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'New'"},
                    {"name": "priority", "type": "String", "length": 10, "nullable": False, "default": "'Medium'"},
                    {"name": "netAmount", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "taxAmount", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "totalAmount", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "shippingAddress", "type": "LargeString", "nullable": True},
                    {"name": "notes", "type": "LargeString", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "OrderItem",
                "description": "Order line item with quantity, pricing, and discount",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "itemNumber", "type": "Integer", "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False, "default": "1"},
                    {"name": "unitPrice", "type": "Decimal", "precision": 10, "scale": 2, "nullable": False},
                    {"name": "totalPrice", "type": "Decimal", "precision": 12, "scale": 2, "nullable": False},
                    {"name": "discount", "type": "Decimal", "precision": 5, "scale": 2, "nullable": False, "default": "0"},
                ],
                "aspects": ["cuid"],
            },
            {
                "name": "Review",
                "description": "Product review with star rating",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "rating", "type": "Integer", "nullable": False},
                    {"name": "title", "type": "String", "length": 100, "nullable": True},
                    {"name": "comment", "type": "LargeString", "nullable": True},
                    {"name": "reviewDate", "type": "DateTime", "nullable": False},
                ],
                "aspects": ["cuid", "managed"],
            },
        ],
        "relationships": [
            {"name": "category", "source_entity": "Product", "target_entity": "Category", "type": "association", "cardinality": "n:1"},
            {"name": "items", "source_entity": "Order", "target_entity": "OrderItem", "type": "composition", "cardinality": "1:n"},
            {"name": "product", "source_entity": "OrderItem", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
            {"name": "customer", "source_entity": "Order", "target_entity": "Customer", "type": "association", "cardinality": "n:1"},
            {"name": "orders", "source_entity": "Customer", "target_entity": "Order", "type": "association", "cardinality": "1:n"},
            {"name": "product", "source_entity": "Review", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
            {"name": "customer", "source_entity": "Review", "target_entity": "Customer", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "validateStock", "entity": "OrderItem", "rule_type": "validation", "description": "Check product stock before placing order"},
            {"name": "calculateItemTotal", "entity": "OrderItem", "rule_type": "calculation", "description": "Calculate totalPrice = quantity * unitPrice * (1 - discount/100)"},
            {"name": "calculateOrderTotal", "entity": "Order", "rule_type": "calculation", "description": "Sum all item totals and calculate tax"},
            {"name": "autoGenerateOrderNumber", "entity": "Order", "rule_type": "auto_number", "description": "Auto-generate order number ORD-YYYYMMDD-XXXX"},
            {"name": "validateRating", "entity": "Review", "rule_type": "validation", "description": "Rating must be between 1 and 5"},
            {"name": "orderStatusWorkflow", "entity": "Order", "rule_type": "workflow", "description": "New -> Confirmed -> Shipped -> Delivered -> Closed"},
        ],
    },
    # =========================================================================
    # HR (6 Entities)
    # =========================================================================
    DomainType.HR.value: {
        "entities": [
            {
                "name": "Employee",
                "description": "Employee master data with personal and organizational info",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "employeeId", "type": "String", "length": 20, "nullable": False},
                    {"name": "firstName", "type": "String", "length": 50, "nullable": False},
                    {"name": "lastName", "type": "String", "length": 50, "nullable": False},
                    {"name": "email", "type": "String", "length": 100, "nullable": False},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "dateOfBirth", "type": "Date", "nullable": True},
                    {"name": "hireDate", "type": "Date", "nullable": False},
                    {"name": "terminationDate", "type": "Date", "nullable": True},
                    {"name": "jobTitle", "type": "String", "length": 100, "nullable": True},
                    {"name": "salary", "type": "Decimal", "precision": 12, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Department",
                "description": "Organizational department with cost center",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 10, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "costCenter", "type": "String", "length": 20, "nullable": True},
                    {"name": "headcount", "type": "Integer", "nullable": False, "default": "0"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Position",
                "description": "Job position with pay grade and salary band",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "title", "type": "String", "length": 100, "nullable": False},
                    {"name": "level", "type": "String", "length": 20, "nullable": False},
                    {"name": "minSalary", "type": "Decimal", "precision": 12, "scale": 2, "nullable": True},
                    {"name": "maxSalary", "type": "Decimal", "precision": 12, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "description", "type": "LargeString", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "LeaveRequest",
                "description": "Employee leave/vacation request with approval workflow",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "leaveType", "type": "String", "length": 30, "nullable": False},
                    {"name": "startDate", "type": "Date", "nullable": False},
                    {"name": "endDate", "type": "Date", "nullable": False},
                    {"name": "totalDays", "type": "Decimal", "precision": 5, "scale": 1, "nullable": False},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Pending'"},
                    {"name": "reason", "type": "LargeString", "nullable": True},
                    {"name": "approverComment", "type": "LargeString", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "TimeEntry",
                "description": "Time tracking entry for project work",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "date", "type": "Date", "nullable": False},
                    {"name": "hours", "type": "Decimal", "precision": 5, "scale": 2, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "projectCode", "type": "String", "length": 20, "nullable": True},
                    {"name": "taskCategory", "type": "String", "length": 50, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Draft'"},
                    {"name": "billable", "type": "Boolean", "nullable": False, "default": "true"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Skill",
                "description": "Employee skill or competency record",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "category", "type": "String", "length": 50, "nullable": True},
                    {"name": "proficiency", "type": "String", "length": 20, "nullable": False, "default": "'Beginner'"},
                ],
                "aspects": ["cuid"],
            },
        ],
        "relationships": [
            {"name": "department", "source_entity": "Employee", "target_entity": "Department", "type": "association", "cardinality": "n:1"},
            {"name": "manager", "source_entity": "Employee", "target_entity": "Employee", "type": "association", "cardinality": "n:1"},
            {"name": "position", "source_entity": "Employee", "target_entity": "Position", "type": "association", "cardinality": "n:1"},
            {"name": "employees", "source_entity": "Department", "target_entity": "Employee", "type": "association", "cardinality": "1:n"},
            {"name": "employee", "source_entity": "LeaveRequest", "target_entity": "Employee", "type": "association", "cardinality": "n:1"},
            {"name": "approver", "source_entity": "LeaveRequest", "target_entity": "Employee", "type": "association", "cardinality": "n:1"},
            {"name": "employee", "source_entity": "TimeEntry", "target_entity": "Employee", "type": "association", "cardinality": "n:1"},
            {"name": "skills", "source_entity": "Employee", "target_entity": "Skill", "type": "composition", "cardinality": "1:n"},
        ],
        "business_rules": [
            {"name": "validateLeaveDates", "entity": "LeaveRequest", "rule_type": "validation", "description": "End date must be after start date; no overlap with existing leaves"},
            {"name": "calculateLeaveDays", "entity": "LeaveRequest", "rule_type": "calculation", "description": "Auto-calculate total days from start/end dates"},
            {"name": "leaveApprovalWorkflow", "entity": "LeaveRequest", "rule_type": "workflow", "description": "Pending -> Approved/Rejected by manager"},
            {"name": "validateTimeEntry", "entity": "TimeEntry", "rule_type": "validation", "description": "Hours must be between 0.25 and 24"},
            {"name": "autoGenerateEmployeeId", "entity": "Employee", "rule_type": "auto_number", "description": "Auto-generate employee ID EMP-XXXX"},
            {"name": "updateDepartmentHeadcount", "entity": "Employee", "rule_type": "side_effect", "description": "Update department headcount on employee create/delete"},
        ],
    },
    # =========================================================================
    # INVENTORY (5 Entities)
    # =========================================================================
    DomainType.INVENTORY.value: {
        "entities": [
            {
                "name": "Product",
                "description": "Inventory product with specifications",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "sku", "type": "String", "length": 50, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "category", "type": "String", "length": 50, "nullable": True},
                    {"name": "unitOfMeasure", "type": "String", "length": 10, "nullable": False, "default": "'EA'"},
                    {"name": "unitCost", "type": "Decimal", "precision": 10, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "weight", "type": "Decimal", "precision": 8, "scale": 2, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Warehouse",
                "description": "Storage location with capacity info",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 20, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "address", "type": "LargeString", "nullable": True},
                    {"name": "city", "type": "String", "length": 50, "nullable": True},
                    {"name": "country", "type": "String", "length": 3, "nullable": True},
                    {"name": "capacity", "type": "Integer", "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "InventoryLevel",
                "description": "Stock level per product per warehouse",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "reservedQty", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "availableQty", "type": "Integer", "nullable": False, "default": "0"},
                    {"name": "minQuantity", "type": "Integer", "nullable": False, "default": "10"},
                    {"name": "maxQuantity", "type": "Integer", "nullable": True},
                    {"name": "reorderPoint", "type": "Integer", "nullable": True},
                    {"name": "lastCountDate", "type": "Date", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "StockMovement",
                "description": "Inventory receipt, issue, or transfer",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "movementNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "type", "type": "String", "length": 20, "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False},
                    {"name": "date", "type": "DateTime", "nullable": False},
                    {"name": "reference", "type": "String", "length": 50, "nullable": True},
                    {"name": "notes", "type": "LargeString", "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Completed'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Supplier",
                "description": "Material supplier / vendor",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "supplierNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "email", "type": "String", "length": 255, "nullable": True},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "country", "type": "String", "length": 3, "nullable": True},
                    {"name": "rating", "type": "Integer", "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
        ],
        "relationships": [
            {"name": "product", "source_entity": "InventoryLevel", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
            {"name": "warehouse", "source_entity": "InventoryLevel", "target_entity": "Warehouse", "type": "association", "cardinality": "n:1"},
            {"name": "product", "source_entity": "StockMovement", "target_entity": "Product", "type": "association", "cardinality": "n:1"},
            {"name": "fromWarehouse", "source_entity": "StockMovement", "target_entity": "Warehouse", "type": "association", "cardinality": "n:1"},
            {"name": "toWarehouse", "source_entity": "StockMovement", "target_entity": "Warehouse", "type": "association", "cardinality": "n:1"},
            {"name": "supplier", "source_entity": "Product", "target_entity": "Supplier", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "lowStockAlert", "entity": "InventoryLevel", "rule_type": "validation", "description": "Warning when quantity below minQuantity"},
            {"name": "calculateAvailable", "entity": "InventoryLevel", "rule_type": "calculation", "description": "availableQty = quantity - reservedQty"},
            {"name": "updateStockOnMovement", "entity": "StockMovement", "rule_type": "side_effect", "description": "Update InventoryLevel on stock movement"},
            {"name": "autoGenerateMovementNumber", "entity": "StockMovement", "rule_type": "auto_number", "description": "Auto-generate MOV-YYYYMMDD-XXXX"},
        ],
    },
    # =========================================================================
    # FINANCE (5 Entities)
    # =========================================================================
    DomainType.FINANCE.value: {
        "entities": [
            {
                "name": "ExpenseReport",
                "description": "Employee expense claim with approval workflow",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "reportNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "title", "type": "String", "length": 100, "nullable": False},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Draft'"},
                    {"name": "totalAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'EUR'"},
                    {"name": "travelFrom", "type": "String", "length": 100, "nullable": True},
                    {"name": "travelTo", "type": "String", "length": 100, "nullable": True},
                    {"name": "purpose", "type": "LargeString", "nullable": True},
                    {"name": "approverComment", "type": "LargeString", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "ExpenseItem",
                "description": "Individual expense line in a report",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "category", "type": "String", "length": 50, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "amount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'EUR'"},
                    {"name": "date", "type": "Date", "nullable": False},
                    {"name": "receiptUrl", "type": "String", "length": 500, "nullable": True},
                    {"name": "isBillable", "type": "Boolean", "nullable": False, "default": "false"},
                ],
                "aspects": ["cuid"],
            },
            {
                "name": "CostCenter",
                "description": "Organizational cost center for budgeting",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 20, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "manager", "type": "String", "length": 100, "nullable": True},
                    {"name": "budget", "type": "Decimal", "precision": 15, "scale": 2, "nullable": True},
                    {"name": "spent", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'EUR'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Invoice",
                "description": "Vendor or customer invoice",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "invoiceNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "type", "type": "String", "length": 20, "nullable": False, "default": "'Payable'"},
                    {"name": "vendor", "type": "String", "length": 100, "nullable": True},
                    {"name": "issueDate", "type": "Date", "nullable": False},
                    {"name": "dueDate", "type": "Date", "nullable": False},
                    {"name": "netAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False},
                    {"name": "taxAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "totalAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'EUR'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Open'"},
                    {"name": "paymentDate", "type": "Date", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Budget",
                "description": "Annual budget allocation per cost center",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "year", "type": "Integer", "nullable": False},
                    {"name": "quarter", "type": "String", "length": 5, "nullable": True},
                    {"name": "allocatedAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False},
                    {"name": "spentAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False, "default": "0"},
                    {"name": "remainingAmount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": False},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'EUR'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
        ],
        "relationships": [
            {"name": "items", "source_entity": "ExpenseReport", "target_entity": "ExpenseItem", "type": "composition", "cardinality": "1:n"},
            {"name": "costCenter", "source_entity": "ExpenseReport", "target_entity": "CostCenter", "type": "association", "cardinality": "n:1"},
            {"name": "costCenter", "source_entity": "Invoice", "target_entity": "CostCenter", "type": "association", "cardinality": "n:1"},
            {"name": "costCenter", "source_entity": "Budget", "target_entity": "CostCenter", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "autoApproval", "entity": "ExpenseReport", "rule_type": "workflow", "description": "Auto-approve reports under 500; manager approval above"},
            {"name": "calculateReportTotal", "entity": "ExpenseReport", "rule_type": "calculation", "description": "Sum all expense items into totalAmount"},
            {"name": "validateBudget", "entity": "Invoice", "rule_type": "validation", "description": "Warn if invoice exceeds remaining budget"},
            {"name": "calculateBudgetRemaining", "entity": "Budget", "rule_type": "calculation", "description": "remainingAmount = allocatedAmount - spentAmount"},
            {"name": "autoGenerateInvoiceNumber", "entity": "Invoice", "rule_type": "auto_number", "description": "Auto-generate INV-YYYYMM-XXXX"},
            {"name": "expenseStatusWorkflow", "entity": "ExpenseReport", "rule_type": "workflow", "description": "Draft -> Submitted -> Approved/Rejected -> Paid"},
        ],
    },
    # =========================================================================
    # CRM (5 Entities)
    # =========================================================================
    DomainType.CRM.value: {
        "entities": [
            {
                "name": "Account",
                "description": "Customer/prospect company account",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "accountNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "industry", "type": "String", "length": 50, "nullable": True},
                    {"name": "website", "type": "String", "length": 255, "nullable": True},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "email", "type": "String", "length": 255, "nullable": True},
                    {"name": "street", "type": "String", "length": 100, "nullable": True},
                    {"name": "city", "type": "String", "length": 50, "nullable": True},
                    {"name": "country", "type": "String", "length": 3, "nullable": True},
                    {"name": "annualRevenue", "type": "Decimal", "precision": 15, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Prospect'"},
                    {"name": "rating", "type": "String", "length": 10, "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Contact",
                "description": "Contact person at a customer account",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "firstName", "type": "String", "length": 50, "nullable": False},
                    {"name": "lastName", "type": "String", "length": 50, "nullable": False},
                    {"name": "email", "type": "String", "length": 255, "nullable": False},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "jobTitle", "type": "String", "length": 100, "nullable": True},
                    {"name": "isPrimary", "type": "Boolean", "nullable": False, "default": "false"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Opportunity",
                "description": "Sales opportunity with pipeline stage tracking",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "title", "type": "String", "length": 100, "nullable": False},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "stage", "type": "String", "length": 30, "nullable": False, "default": "'Qualification'"},
                    {"name": "probability", "type": "Integer", "nullable": False, "default": "10"},
                    {"name": "amount", "type": "Decimal", "precision": 15, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "expectedCloseDate", "type": "Date", "nullable": True},
                    {"name": "source", "type": "String", "length": 50, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Open'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Activity",
                "description": "Sales activity: call, email, meeting, task",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "type", "type": "String", "length": 20, "nullable": False},
                    {"name": "subject", "type": "String", "length": 200, "nullable": False},
                    {"name": "description", "type": "LargeString", "nullable": True},
                    {"name": "dueDate", "type": "DateTime", "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Planned'"},
                    {"name": "priority", "type": "String", "length": 10, "nullable": False, "default": "'Medium'"},
                    {"name": "duration", "type": "Integer", "nullable": True},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Lead",
                "description": "Sales lead before qualification to opportunity",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "firstName", "type": "String", "length": 50, "nullable": False},
                    {"name": "lastName", "type": "String", "length": 50, "nullable": False},
                    {"name": "email", "type": "String", "length": 255, "nullable": False},
                    {"name": "company", "type": "String", "length": 100, "nullable": True},
                    {"name": "source", "type": "String", "length": 50, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'New'"},
                    {"name": "score", "type": "Integer", "nullable": False, "default": "0"},
                ],
                "aspects": ["cuid", "managed"],
            },
        ],
        "relationships": [
            {"name": "contacts", "source_entity": "Account", "target_entity": "Contact", "type": "composition", "cardinality": "1:n"},
            {"name": "account", "source_entity": "Opportunity", "target_entity": "Account", "type": "association", "cardinality": "n:1"},
            {"name": "contact", "source_entity": "Opportunity", "target_entity": "Contact", "type": "association", "cardinality": "n:1"},
            {"name": "account", "source_entity": "Activity", "target_entity": "Account", "type": "association", "cardinality": "n:1"},
            {"name": "opportunity", "source_entity": "Activity", "target_entity": "Opportunity", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "opportunityStageWorkflow", "entity": "Opportunity", "rule_type": "workflow", "description": "Qualification -> Proposal -> Negotiation -> Won/Lost"},
            {"name": "updateProbability", "entity": "Opportunity", "rule_type": "calculation", "description": "Auto-update probability based on stage"},
            {"name": "convertLeadToOpportunity", "entity": "Lead", "rule_type": "action", "description": "Convert qualified lead to account + opportunity"},
            {"name": "autoGenerateAccountNumber", "entity": "Account", "rule_type": "auto_number", "description": "Auto-generate account number ACC-XXXX"},
            {"name": "validateEmail", "entity": "Contact", "rule_type": "validation", "description": "Validate email format"},
        ],
    },
    # =========================================================================
    # LOGISTICS (5 Entities)
    # =========================================================================
    "logistics": {
        "entities": [
            {
                "name": "Shipment",
                "description": "Logistics shipment with tracking",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "shipmentNumber", "type": "String", "length": 20, "nullable": False},
                    {"name": "trackingNumber", "type": "String", "length": 50, "nullable": True},
                    {"name": "origin", "type": "String", "length": 100, "nullable": False},
                    {"name": "destination", "type": "String", "length": 100, "nullable": False},
                    {"name": "plannedDate", "type": "DateTime", "nullable": False},
                    {"name": "actualDate", "type": "DateTime", "nullable": True},
                    {"name": "weight", "type": "Decimal", "precision": 10, "scale": 2, "nullable": True},
                    {"name": "weightUnit", "type": "String", "length": 5, "nullable": False, "default": "'KG'"},
                    {"name": "cost", "type": "Decimal", "precision": 12, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Pending'"},
                    {"name": "priority", "type": "String", "length": 10, "nullable": False, "default": "'Normal'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "ShipmentItem",
                "description": "Item/package within a shipment",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": False},
                    {"name": "quantity", "type": "Integer", "nullable": False, "default": "1"},
                    {"name": "weight", "type": "Decimal", "precision": 8, "scale": 2, "nullable": True},
                    {"name": "dimensions", "type": "String", "length": 50, "nullable": True},
                    {"name": "hazardous", "type": "Boolean", "nullable": False, "default": "false"},
                ],
                "aspects": ["cuid"],
            },
            {
                "name": "Carrier",
                "description": "Shipping carrier / logistics provider",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "code", "type": "String", "length": 10, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "type", "type": "String", "length": 30, "nullable": True},
                    {"name": "phone", "type": "String", "length": 30, "nullable": True},
                    {"name": "email", "type": "String", "length": 255, "nullable": True},
                    {"name": "rating", "type": "Integer", "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False, "default": "'Active'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "Route",
                "description": "Predefined shipping route with cost estimation",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "name", "type": "String", "length": 100, "nullable": False},
                    {"name": "origin", "type": "String", "length": 100, "nullable": False},
                    {"name": "destination", "type": "String", "length": 100, "nullable": False},
                    {"name": "distance", "type": "Decimal", "precision": 10, "scale": 2, "nullable": True},
                    {"name": "estimatedDays", "type": "Integer", "nullable": True},
                    {"name": "baseCost", "type": "Decimal", "precision": 12, "scale": 2, "nullable": True},
                    {"name": "currency", "type": "String", "length": 3, "nullable": False, "default": "'USD'"},
                ],
                "aspects": ["cuid", "managed"],
            },
            {
                "name": "TrackingEvent",
                "description": "Shipment tracking milestone event",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True, "nullable": False},
                    {"name": "eventType", "type": "String", "length": 30, "nullable": False},
                    {"name": "location", "type": "String", "length": 100, "nullable": True},
                    {"name": "timestamp", "type": "DateTime", "nullable": False},
                    {"name": "description", "type": "String", "length": 255, "nullable": True},
                    {"name": "status", "type": "String", "length": 20, "nullable": False},
                ],
                "aspects": ["cuid"],
            },
        ],
        "relationships": [
            {"name": "items", "source_entity": "Shipment", "target_entity": "ShipmentItem", "type": "composition", "cardinality": "1:n"},
            {"name": "carrier", "source_entity": "Shipment", "target_entity": "Carrier", "type": "association", "cardinality": "n:1"},
            {"name": "route", "source_entity": "Shipment", "target_entity": "Route", "type": "association", "cardinality": "n:1"},
            {"name": "trackingEvents", "source_entity": "Shipment", "target_entity": "TrackingEvent", "type": "composition", "cardinality": "1:n"},
            {"name": "carrier", "source_entity": "Route", "target_entity": "Carrier", "type": "association", "cardinality": "n:1"},
        ],
        "business_rules": [
            {"name": "shipmentStatusWorkflow", "entity": "Shipment", "rule_type": "workflow", "description": "Pending -> Picked Up -> In Transit -> Delivered"},
            {"name": "calculateShipmentWeight", "entity": "Shipment", "rule_type": "calculation", "description": "Sum all item weights"},
            {"name": "autoGenerateShipmentNumber", "entity": "Shipment", "rule_type": "auto_number", "description": "Auto-generate SHP-YYYYMMDD-XXXX"},
            {"name": "validateDeliveryDate", "entity": "Shipment", "rule_type": "validation", "description": "Planned date must be in the future"},
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
    state["current_logs"] = [] # Reset logs for this agent
    
    log_progress(state, "Analyzing project configuration...")
    
    # ==========================================================================
    # Step 1: Validate project configuration
    # ==========================================================================
    project_name = state.get("project_name", "")
    errors.extend(validate_project_name(project_name))
    
    if any(e["severity"] == "error" for e in errors):
        state["validation_errors"] = errors
        logger.error(f"Validation failed: {errors}")
        log_progress(state, f"Validation failed: {errors[0]['message']}")
        return state
    
    # ==========================================================================
    # Step 2: Process domain type
    # ==========================================================================
    domain_type = state.get("domain_type", DomainType.CUSTOM.value)
    
    if domain_type in DOMAIN_TEMPLATES and not state.get("entities"):
        # Use pre-defined template only if no entities already exist (e.g. from user approval)
        log_progress(state, f"Applying {domain_type} domain template...")
        template = DOMAIN_TEMPLATES[domain_type]
        
        state["entities"] = template.get("entities", [])
        state["relationships"] = template.get("relationships", [])
        state["business_rules"] = template.get("business_rules", [])
        log_progress(state, f"Imported {len(state['entities'])} entities from template.")
    
    elif state.get("entities"):
        # User provided entities - check if they have fields defined
        user_entities = state.get("entities", [])
        entities_need_fields = any(not e.get("fields") for e in user_entities)
        
        if entities_need_fields:
            # Entities have no fields - use LLM to generate full entity definitions
            entity_names = [e.get("name", "") for e in user_entities]
            log_progress(state, f"Generating fields for entities: {', '.join(entity_names)}...")
            
            try:
                llm_manager = get_llm_manager()
                provider = state.get("llm_provider")
                
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
                    log_progress(state, f"LLM generated {len(state['entities'])} entities with fields.")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response: {e}. Using fallback entity generation.")
                    log_progress(state, "LLM parsing failed. Using fallback field generation.")
                    # Fallback: generate basic fields for each entity
                    state["entities"] = generate_fallback_entities(user_entities)
                    
            except Exception as e:
                logger.error(f"LLM entity generation failed: {e}. Using fallback.")
                log_progress(state, f"LLM generation failed: {str(e)}. Using fallback.")
                # Fallback: generate basic fields
                state["entities"] = generate_fallback_entities(user_entities)
        else:
            # Entities have fields - just validate
            log_progress(state, "Validating user-defined entities...")
            errors.extend(validate_entities(user_entities))
    
    else:
        # Custom domain without entities - use LLM to extract from description
        log_progress(state, "Extracting entities from project description...")
        
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
                    log_progress(state, f"Extracted {len(state['entities'])} entities from description.")
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
                    log_progress(state, "Failed to parse entity extraction result.")
                    errors.append({
                        "agent": "requirements",
                        "code": "LLM_PARSE_ERROR",
                        "message": "Could not parse entity extraction response",
                        "field": None,
                        "severity": "warning",
                    })
            
            except Exception as e:
                logger.error(f"LLM extraction failed: {e}")
                log_progress(state, f"Entity extraction failed: {str(e)}")
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
    log_progress(state, "Performing final validation...")
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
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Requirements analysis complete.")
    logger.info(f"Requirements Agent completed. Entities: {len(state.get('entities', []))}, Errors: {len(errors)}")
    
    return state
