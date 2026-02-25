import os
import glob
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# Initialize SentenceTransformer embedding
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

KNOWLEDGE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_DIR = os.path.join(KNOWLEDGE_DIR, "db")

if not os.path.exists(CHROMA_DB_DIR):
    os.makedirs(CHROMA_DB_DIR)

def ingest_documents():
    print(f"Ingesting documents from {KNOWLEDGE_DIR}...")
    documents = []

    # Load Text/Markdown files
    for filepath in glob.glob(os.path.join(KNOWLEDGE_DIR, "docs", "*.md")):
        print(f"Loading {filepath}...")
        loader = TextLoader(filepath, autodetect_encoding=True)
        documents.extend(loader.load())

    for filepath in glob.glob(os.path.join(KNOWLEDGE_DIR, "docs", "*.txt")):
        print(f"Loading {filepath}...")
        loader = TextLoader(filepath, autodetect_encoding=True)
        documents.extend(loader.load())

    # Load PDF files
    for filepath in glob.glob(os.path.join(KNOWLEDGE_DIR, "docs", "*.pdf")):
        print(f"Loading {filepath}...")
        loader = PyPDFLoader(filepath)
        documents.extend(loader.load())

    if not documents:
        print("No documents found to ingest. Please place .md, .txt, or .pdf files in backend/knowledge/docs/")
        return

    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(documents)

    print(f"Created {len(splits)} document chunks.")

    # Create Chroma vector store
    print(f"Building/updating Chroma DB at {CHROMA_DB_DIR}...")
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embedding_model,
        persist_directory=CHROMA_DB_DIR,
        collection_name="sap_knowledge"
    )

    print("Ingestion complete!")

if __name__ == "__main__":
    ingest_documents()
