"""
RAG (Retrieval-Augmented Generation) Module

Provides document ingestion, retrieval, and rule extraction for agents.
"""

from backend.rag.retriever import retrieve_for_agent
from backend.rag.namespaces import get_agent_namespace, AGENT_NAMESPACES

__all__ = [
    "retrieve_for_agent",
    "get_agent_namespace",
    "AGENT_NAMESPACES",
]
