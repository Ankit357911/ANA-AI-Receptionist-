from dataclasses import dataclass

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ModuleNotFoundError:
    RecursiveCharacterTextSplitter = None


@dataclass
class Chunk:
    page_content: str


def _fallback_chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50):
    chunks = []
    start = 0
    text = text.strip()

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(Chunk(page_content=text[start:end]))
        if end >= len(text):
            break
        start = max(0, end - chunk_overlap)

    return chunks


def chunk_text(text):
    if RecursiveCharacterTextSplitter is None:
        return _fallback_chunk_text(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    return splitter.create_documents([text])
