"""
RAG Document Loader

Ingests PDFs and markdown files into the vector store.
"""

import logging
from pathlib import Path
from typing import List

from backend.rag.retriever import add_document

logger = logging.getLogger(__name__)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    
    return chunks


def load_markdown(file_path: str, namespace: str) -> int:
    """
    Load a markdown file into a namespace.
    
    Args:
        file_path: Path to markdown file
        namespace: Target namespace
        
    Returns:
        Number of chunks ingested
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Chunk the content
        chunks = chunk_text(content)
        
        # Add each chunk to the namespace
        for chunk in chunks:
            add_document(namespace, chunk)
        
        logger.info(f"Loaded {len(chunks)} chunks from {file_path} into namespace {namespace}")
        return len(chunks)
        
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return 0


def load_pdf(file_path: str, namespace: str) -> int:
    """
    Load a PDF file into a namespace.
    
    Args:
        file_path: Path to PDF file
        namespace: Target namespace
        
    Returns:
        Number of chunks ingested
    """
    try:
        # PDF parsing would require PyPDF2 or similar
        # For now, return 0 and log a warning
        logger.warning(f"PDF loading not yet implemented for {file_path}")
        return 0
        
    except Exception as e:
        logger.error(f"Failed to load PDF {file_path}: {e}")
        return 0


def load_directory(directory: str, namespace: str, pattern: str = "*.md") -> int:
    """
    Load all matching files from a directory into a namespace.
    
    Args:
        directory: Directory path
        namespace: Target namespace
        pattern: File pattern (e.g., "*.md", "*.pdf")
        
    Returns:
        Total number of chunks ingested
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        logger.error(f"Directory {directory} does not exist")
        return 0
    
    total_chunks = 0
    
    for file_path in dir_path.glob(pattern):
        if file_path.suffix == '.md':
            total_chunks += load_markdown(str(file_path), namespace)
        elif file_path.suffix == '.pdf':
            total_chunks += load_pdf(str(file_path), namespace)
    
    logger.info(f"Loaded {total_chunks} total chunks from {directory} into namespace {namespace}")
    return total_chunks
