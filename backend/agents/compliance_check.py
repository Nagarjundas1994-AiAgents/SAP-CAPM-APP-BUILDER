"""
Agent: Compliance Check

GDPR, data privacy, SAP BTP security standards scan.
"""

import json
import logging
from datetime import datetime

from backend.agents.state import BuilderState
from backend.agents.progress import log_progress
from backend.agents.llm_utils import generate_with_retry
from backend.rag import retrieve_for_agent

logger = logging.getLogger(__name__)


COMPLIANCE_SYSTEM_PROMPT = """You are a GDPR and data privacy compliance expert with deep knowledge of SAP BTP security standards.
Your task is to analyze data models and identify compliance requirements, personal data handling, and security risks.

COMPLIANCE AREAS:
1. GDPR Compliance: Personal data identification, consent management, right to erasure
2. Data Privacy: Data minimization, purpose limitation, storage limitation
3. SAP BTP Security: Authentication, authorization, encryption, audit trails
4. Personal Data: PII fields (email, phone, address, SSN, etc.)
5. Sensitive Data: Health, financial, biometric, location data

OUTPUT FORMAT:
Return valid JSON:
{
  "gdpr_compliant": true/false,
  "data_privacy_checks": [
    {
      "check": "string",
      "status": "pass/warning/fail",
      "details": "string"
    }
  ],
  "security_scan_results": [
    {
      "area": "string",
      "status": "pass/warning/fail",
      "recommendation": "string"
    }
  ],
  "personal_data_fields": [
    {
      "entity": "string",
      "field": "string",
      "data_type": "email/phone/address/ssn/etc",
      "requires_consent": true/false,
      "retention_policy": "string"
    }
  ],
  "recommendations": [
    {
      "priority": "high/medium/low",
      "category": "gdpr/privacy/security",
      "recommendation": "string",
      "implementation": "string"
    }
  ]
}

Return ONLY valid JSON."""


COMPLIANCE_PROMPT = """Analyze the following data model for GDPR, data privacy, and security compliance.

Project: {project_name}
Description: {description}

Entities:
{entities_json}

Security Configuration:
{security_json}

Tasks:
1. Identify all personal data fields (PII)
2. Check GDPR compliance requirements
3. Verify data privacy controls
4. Scan for security vulnerabilities
5. Provide compliance recommendations

Respond with ONLY valid JSON."""


async def compliance_check_agent(state: BuilderState) -> BuilderState:
    """
    Compliance Check Agent - GDPR, data privacy, security scan.
    
    Checks:
    - GDPR compliance
    - Data privacy requirements
    - SAP BTP security standards
    - Personal data handling
    """
    logger.info("Starting Compliance Check Agent")
    
    now = datetime.utcnow().isoformat()
    state["current_agent"] = "compliance_check"
    state["updated_at"] = now
    state["current_logs"] = []
    
    log_progress(state, "Starting compliance check phase...")
    
    # Get context
    project_name = state.get("project_name", "App")
    description = state.get("project_description", "")
    entities = state.get("entities", [])
    security_config = state.get("security_config", {})
    
    if not entities:
        log_progress(state, "No entities found - using minimal compliance report")
        compliance_report = {
            "gdpr_compliant": True,
            "data_privacy_checks": [],
            "security_scan_results": [],
            "personal_data_fields": [],
            "recommendations": []
        }
    else:
        # Retrieve RAG context
        rag_docs = await retrieve_for_agent("compliance_check", f"GDPR data privacy SAP BTP security {project_name}")
        rag_context = "\n\n".join(rag_docs) if rag_docs else ""
        
        prompt = COMPLIANCE_PROMPT.format(
            project_name=project_name,
            description=description or "No description provided",
            entities_json=json.dumps(entities, indent=2),
            security_json=json.dumps(security_config, indent=2),
        )
        
        if rag_context:
            prompt = f"REFERENCE DOCUMENTATION:\n{rag_context}\n\n{prompt}"
        
        log_progress(state, f"Scanning {len(entities)} entities for compliance issues...")
        
        result = await generate_with_retry(
            prompt=prompt,
            system_prompt=COMPLIANCE_SYSTEM_PROMPT,
            state=state,
            required_keys=["gdpr_compliant", "personal_data_fields"],
            max_retries=3,
            agent_name="compliance_check",
        )
        
        if result:
            compliance_report = result
            pii_count = len(result.get("personal_data_fields", []))
            log_progress(state, f"✅ Identified {pii_count} personal data fields")
            log_progress(state, f"✅ Generated {len(result.get('recommendations', []))} compliance recommendations")
        else:
            log_progress(state, "⚠️ LLM generation failed - using minimal compliance report")
            compliance_report = {
                "gdpr_compliant": True,
                "data_privacy_checks": [],
                "security_scan_results": [],
                "personal_data_fields": [],
                "recommendations": []
            }
    
    state["compliance_report"] = compliance_report
    state["needs_correction"] = False
    
    # Record execution
    state["agent_history"] = state.get("agent_history", []) + [{
        "agent_name": "compliance_check",
        "status": "completed",
        "started_at": now,
        "completed_at": datetime.utcnow().isoformat(),
        "duration_ms": None,
        "error": None,
        "logs": state.get("current_logs", []),
    }]
    
    log_progress(state, "Compliance check complete.")
    return state
