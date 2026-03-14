"""
RAG Retriever

Scoped retrieval per agent namespace.
"""

import logging
from typing import List

from backend.rag.namespaces import get_agent_namespace

logger = logging.getLogger(__name__)

# In-memory document store (namespace -> documents)
# In production, this would be a vector database like Pinecone, Weaviate, or ChromaDB
_document_store: dict[str, list[str]] = {}


async def retrieve_for_agent(
    agent_name: str,
    query: str,
    top_k: int = 5
) -> list[str]:
    """
    Retrieve relevant document chunks for an agent.
    
    Args:
        agent_name: Name of the agent requesting documents
        query: Query string for retrieval
        top_k: Number of top results to return
        
    Returns:
        List of relevant document chunks
    """
    namespace = get_agent_namespace(agent_name)
    
    # Get documents for this namespace
    docs = _document_store.get(namespace, [])
    
    if not docs:
        logger.debug(f"No documents found for agent {agent_name} (namespace: {namespace})")
        return []
    
    # Simple keyword-based retrieval (in production, use embeddings + vector search)
    query_lower = query.lower()
    scored_docs = []
    
    for doc in docs:
        doc_lower = doc.lower()
        # Simple scoring: count keyword matches
        score = sum(1 for word in query_lower.split() if word in doc_lower)
        if score > 0:
            scored_docs.append((score, doc))
    
    # Sort by score and return top_k
    scored_docs.sort(reverse=True, key=lambda x: x[0])
    results = [doc for _, doc in scored_docs[:top_k]]
    
    logger.debug(f"Retrieved {len(results)} documents for agent {agent_name}")
    return results


def add_document(namespace: str, content: str) -> None:
    """
    Add a document to a namespace.
    
    Args:
        namespace: Document namespace
        content: Document content
    """
    if namespace not in _document_store:
        _document_store[namespace] = []
    _document_store[namespace].append(content)
    logger.info(f"Added document to namespace {namespace}")


def get_namespace_stats() -> dict[str, int]:
    """
    Get document counts per namespace.
    
    Returns:
        Dict mapping namespace to document count
    """
    return {ns: len(docs) for ns, docs in _document_store.items()}


def clear_namespace(namespace: str) -> None:
    """Clear all documents in a namespace."""
    _document_store.pop(namespace, None)
    logger.info(f"Cleared namespace {namespace}")
