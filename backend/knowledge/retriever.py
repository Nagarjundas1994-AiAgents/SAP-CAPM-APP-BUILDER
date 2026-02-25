import os
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

KNOWLEDGE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(KNOWLEDGE_DIR, "db")

_vectorstore = None

def get_vectorstore():
    global _vectorstore
    
    if _vectorstore is not None:
        return _vectorstore
        
    if not os.path.exists(CHROMA_DB_DIR):
        print("Warning: Chroma DB directory does not exist. Please run ingest.py first.")
        return None
        
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    _vectorstore = Chroma(
        persist_directory=CHROMA_DB_DIR,
        embedding_function=embedding_model,
        collection_name="sap_knowledge"
    )
    
    return _vectorstore

def query_sap_knowledge(query: str, k: int = 3) -> str:
    """
    Retrieve relevant SAP knowledge for the given query.
    Returns a unified string block for inclusion in the LLM context.
    """
    vectorstore = get_vectorstore()
    
    if not vectorstore:
        return ""
        
    docs = vectorstore.similarity_search(query, k=k)
    
    if not docs:
        return ""
        
    context_parts = []
    for i, doc in enumerate(docs):
        source = doc.metadata.get("source", "Unknown")
        context_parts.append(f"--- [Source: {source}] ---\n{doc.page_content}")
        
    return "\n\n".join(context_parts)
