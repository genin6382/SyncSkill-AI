# vector_store.py
from chroma_setup import JobVectorStore

def load_vector_store(persist_directory="./chroma_db", collection_name="job_dataset"):
    return JobVectorStore(
        csv_path=None,  # Don't load dataset
        collection_name=collection_name,
        persist_directory=persist_directory
    )
