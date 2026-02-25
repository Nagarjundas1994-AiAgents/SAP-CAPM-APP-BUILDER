"""
SAP Knowledge Base Loader

Loads curated SAP reference documentation from the knowledge/ directory
and provides it to agent prompts so the LLM generates code grounded in
real SAP documentation (no hallucinated APIs or syntax).
"""

import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# Knowledge base directory
KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


@lru_cache(maxsize=20)
def load_knowledge(filename: str) -> str:
    """
    Load a knowledge file by name.
    Cached so files are only read once per process.
    
    Args:
        filename: Name of the file in the knowledge/ directory (e.g., "cds_types.md")
        
    Returns:
        File contents as string, or empty string if file not found
    """
    filepath = KNOWLEDGE_DIR / filename
    try:
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            logger.debug(f"Loaded knowledge file: {filename} ({len(content)} chars)")
            return content
        else:
            logger.warning(f"Knowledge file not found: {filepath}")
            return ""
    except Exception as e:
        logger.error(f"Error loading knowledge file {filename}: {e}")
        return ""


from backend.knowledge.retriever import query_sap_knowledge

def get_data_modeling_knowledge() -> str:
    """Get knowledge relevant to the data modeling agent."""
    query = "CDS schema definition syntax entities fields types associations compositions cuid managed"
    rag_content = query_sap_knowledge(query, k=5)
    
    return f"""
--- SAP CDS REFERENCE DOCUMENTATION (RAG Context) ---
{rag_content}
--- END REFERENCE ---
"""


def get_service_knowledge() -> str:
    """Get knowledge relevant to the service exposure agent."""
    query = "CDS service projection annotations OData actions functions @readonly @insertonly @UI"
    rag_content = query_sap_knowledge(query, k=5)
    
    return f"""
--- SAP ANNOTATION REFERENCE (RAG Context) ---
{rag_content}
--- END REFERENCE ---
"""


def get_business_logic_knowledge() -> str:
    """Get knowledge relevant to the business logic agent."""
    query = "SAP CAP Node.js handlers module.exports cds.service.impl this.on this.before this.after SELECT INSERT UPDATE DELETE srv/service.js"
    rag_content = query_sap_knowledge(query, k=5)
    
    return f"""
--- SAP CAP HANDLER REFERENCE (RAG Context) ---
{rag_content}
--- END REFERENCE ---
"""


def get_fiori_knowledge() -> str:
    """Get knowledge relevant to the Fiori UI agent."""
    query = "SAP Fiori Elements manifest.json sap.app sap.ui5 dataSources routing FlexibleColumnLayout Component.js"
    rag_content = query_sap_knowledge(query, k=5)
    
    return f"""
--- SAP FIORI ELEMENTS REFERENCE (RAG Context) ---
{rag_content}
--- END REFERENCE ---
"""


def get_security_knowledge() -> str:
    """Get knowledge relevant to security and deployment agents."""
    query = "SAP BTP security xs-security.json XSUAA scopes role-templates @requires @restrict authorization"
    rag_content = query_sap_knowledge(query, k=5)
    
    return f"""
--- SAP SECURITY REFERENCE (RAG Context) ---
{rag_content}
--- END REFERENCE ---
"""


def _extract_section(content: str, start_header: str, end_header: str) -> str:
    """Extract a section from markdown content between two headers."""
    try:
        start_idx = content.index(start_header)
        try:
            end_idx = content.index(end_header, start_idx + len(start_header))
            return content[start_idx:end_idx].strip()
        except ValueError:
            return content[start_idx:].strip()
    except ValueError:
        return content[:2000]  # Return first 2000 chars if headers not found
