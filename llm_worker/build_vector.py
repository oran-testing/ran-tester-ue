# build_vector_db.py (Corrected)
import os
import chromadb
from chromadb.utils import embedding_functions

# --- Configuration ---
KNOWLEDGE_BASE_DIR = "knowledge_base"
VECTOR_DB_DIR = "vector_db"
COLLECTION_NAME = "rf_knowledge"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def build_db():
    """
    Reads documents from the knowledge base, generates embeddings using a reliable
    SentenceTransformer function, and stores them in a ChromaDB vector database.
    """
    print("--- Building Vector Database ---")
    
    # Initialize empty lists to hold our data
    documents = []
    metadatas = []
    ids = []
    doc_id_counter = 1

    # Load all documents from the knowledge base directory
    for filename in os.listdir(KNOWLEDGE_BASE_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                print(f"Reading: {filename}...")
                content = f.read()
                documents.append(content)
                # Store the source file name in the metadata for each document
                metadatas.append({"source": filename})
                # Create a unique ID for each document
                ids.append(str(doc_id_counter))
                doc_id_counter += 1
    
    if not documents:
        print("No knowledge documents found in the 'knowledge_base' directory. Aborting.")
        return

    # Create an explicit embedding function to avoid the ONNX hanging issue
    print(f"Initializing SentenceTransformer embedding function for: {EMBEDDING_MODEL_NAME}")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )

    # Initialize ChromaDB client and get or create the collection
    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    
    # Delete the collection if it already exists to ensure a fresh start
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        print(f"Collection '{COLLECTION_NAME}' already exists. Deleting it for a clean rebuild.")
        client.delete_collection(name=COLLECTION_NAME)

    print(f"Creating new collection '{COLLECTION_NAME}' with explicit embedding function.")
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=sentence_transformer_ef
    )

    # Add the documents to the collection. ChromaDB will use our function to embed them.
    print("Adding documents to the collection...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    print("\n--- Vector Database built successfully! ---")
    print(f"Total documents indexed: {collection.count()}")
    print(f"Database saved in: '{VECTOR_DB_DIR}' directory.")

if __name__ == "__main__":
    build_db()
