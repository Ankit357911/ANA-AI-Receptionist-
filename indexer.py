import os
import shutil
from utils.chunker import chunk_text
from utils.embedder import embed_text
from utils.vector_store import create_faiss_index, save_index

DATA_DIR = "data"
INDEX_DIR = "indexes"

def index_all_files():
    os.makedirs(INDEX_DIR, exist_ok=True)
    current_sources = set()

    for filename in os.listdir(DATA_DIR):
        filepath = os.path.join(DATA_DIR, filename)
        name = os.path.splitext(filename)[0]  # e.g. "fees"
        print(f"Indexing {filename}...")

        if filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        elif filename.endswith(".pdf"):
            from utils.pdf_extractor import extract_text_from_pdf
            with open(filepath, "rb") as f:
                text = extract_text_from_pdf(f)
        else:
            continue

        current_sources.add(name)
        # Keep the filename in the indexed text so short files without headings
        # (for example club/team lists) still retrieve well for direct queries.
        text = f"Source: {name}\n\n{text}"
        chunks = chunk_text(text)
        chunk_texts = [c.page_content for c in chunks]
        embeddings = embed_text(chunk_texts)
        index = create_faiss_index(embeddings)
        save_index(index, chunk_texts, path=f"{INDEX_DIR}/{name}")
        print(f"Done: {name}")

    for existing in os.listdir(INDEX_DIR):
        existing_path = os.path.join(INDEX_DIR, existing)
        if os.path.isdir(existing_path) and existing not in current_sources:
            print(f"Removing stale index: {existing}")
            shutil.rmtree(existing_path)

if __name__ == "__main__":
    index_all_files()
