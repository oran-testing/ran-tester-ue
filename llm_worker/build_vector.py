import os
import re
import chromadb
from chromadb.utils import embedding_functions

KNOWLEDGE_BASE_DIR = "knowledge_base"
VECTOR_DB_DIR = "vector_db"
COLLECTION_NAME = "rf_knowledge"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

def _infer_component(filename: str, content: str) -> str:
    # Prefer explicit tag in file, e.g., "Component: sniffer"
    m = re.search(r'^\s*Component:\s*(sniffer|jammer|rtue|general)\s*$', content, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1).lower()
    name = filename.lower()
    if "sniffer" in name:
        return "sniffer"
    if "jammer" in name:
        return "jammer"
    if "rtue" in name:
        return "rtue"
    return "general"

def build_db():
    print("--- Building Vector Database ---")

    documents = []
    metadatas = []
    ids = []
    doc_id_counter = 1

    for filename in os.listdir(KNOWLEDGE_BASE_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                print(f"Reading: {filename}...")
                content = f.read()
                documents.append(content)
                component = _infer_component(filename, content)
                metadatas.append({"source": filename, "component": component})
                ids.append(str(doc_id_counter))
                doc_id_counter += 1

    if not documents:
        print("No knowledge documents found in the 'knowledge_base' directory. Aborting.")
        return

    print(f"Initializing SentenceTransformer embedding function for: {EMBEDDING_MODEL_NAME}")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL_NAME
    )

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)

    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        print(f"Collection '{COLLECTION_NAME}' already exists. Deleting it for a clean rebuild.")
        client.delete_collection(name=COLLECTION_NAME)

    print(f"Creating new collection '{COLLECTION_NAME}' with explicit embedding function.")
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=sentence_transformer_ef
    )

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
