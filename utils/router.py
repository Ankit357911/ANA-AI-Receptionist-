import os
import re
import faiss
import pickle
from utils.embedder import embed_text

INDEX_DIR = "indexes"
RELEVANCE_THRESHOLD = 1.5


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _has_word(normalized_text: str, phrase: str) -> bool:
    tokens = phrase.lower().split()
    if not tokens:
        return False
    pattern = r"\b" + r"\s+".join(re.escape(token) for token in tokens) + r"\b"
    return re.search(pattern, normalized_text) is not None


def _preferred_source_name(query):
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    contact_keywords = (
        "contact information",
        "contact info",
        "contact details",
        "contact us",
        "how can i contact",
        "how do i contact",
        "how to contact",
        "how to reach",
        "how can i reach",
        "where is",
        "where are",
        "where can i find",
        "reach kcc",
        "reach kantipur",
        "contact to kcc",
        "contact kcc",
        "contact to kantipur",
        "contact with kcc",
        "contact with kantipur",
        "phone number",
        "phone no",
        "phone",
        "tel",
        "telephone",
        "email",
        "e mail",
        "location",
        "address",
    )
    if any(_has_word(normalized, phrase) for phrase in contact_keywords) or (
        "contact" in normalized and ("kcc" in normalized or "kantipur" in normalized or "college" in normalized)
    ) or (
        any(_has_word(normalized, word) for word in ("where", "reach", "email", "address", "phone", "tel", "location"))
        and ("kcc" in normalized or "kantipur" in normalized or "college" in normalized)
    ):
        return "Contact_Information"

    team_keywords = (
        "principal",
        "chairperson",
        "president",
        "vice principal",
        "vice-principal",
        "secretary",
        "treasurer",
        "coordinator",
        "team list",
        "team members",
        "team",
        "member",
        "members",
    )
    if any(_has_word(normalized, phrase) for phrase in team_keywords) and (
        "kcc" in normalized or "kantipur" in normalized or "college" in normalized or "team" in normalized
    ):
        return "collage team"

    keyword_map = [
        ("standard greetings", "Greeting"),
        ("greeting responses", "Greeting"),
        ("greeting", "Greeting"),
        ("greetings", "Greeting"),
        ("welcome message", "Greeting"),
        ("welcome", "Greeting"),
        ("ana greeting", "Greeting"),
        ("collage team", "collage team"),
        ("kcc team", "collage team"),
        ("team list", "collage team"),
        ("team members", "collage team"),
        ("team", "collage team"),
        ("kantipur city college", "College_Overview"),
        ("kcc college", "College_Overview"),
        ("tell me about kcc", "College_Overview"),
        ("about kcc", "College_Overview"),
        ("kcc", "College_Overview"),
        ("cirricular", "cirricular"),
        ("curriculum", "cirricular"),
        ("creators club", "creators club"),
        ("research committee", "research Committee"),
        ("student services", "student services"),
        ("student service", "student services"),
        ("it club", "IT club"),
        ("sdsn club", "sdsn club"),
        ("departments", "departments"),
        ("contact information", "Contact_Information"),
    ]
    for phrase, source_name in keyword_map:
        if _has_word(normalized, phrase):
            return source_name
    return None


def _source_bonus(query, source_name):
    normalized_query = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    normalized_source = re.sub(r"[^a-z0-9]+", " ", source_name.lower().replace("_", " ")).strip()
    query_tokens = set(normalized_query.split())
    source_tokens = set(normalized_source.split())
    if not source_tokens:
        return 0.0

    if normalized_source == "cirricular" and ("cirricular" in normalized_query or "curriculum" in normalized_query):
        return 2.5

    if normalized_source == "greeting" and any(word in normalized_query for word in ("greeting", "greetings", "welcome", "namaste")):
        return 2.0

    if normalized_source == "departments" and "departments" in query_tokens:
        return 0.9

    if normalized_source and normalized_source in normalized_query:
        return 0.6

    matched = len(query_tokens & source_tokens)
    if matched == 0:
        return 0.0

    bonus = matched * 0.06
    if source_tokens.issubset(query_tokens):
        bonus += 0.2
    return bonus


def _score_indexes(query, k=3):
    query_embedding = embed_text([query])
    scored = []

    for name in os.listdir(INDEX_DIR):
        index_path = f"{INDEX_DIR}/{name}/faiss_index"
        chunks_path = f"{INDEX_DIR}/{name}/chunks.pkl"

        if not os.path.exists(index_path):
            continue

        index = faiss.read_index(index_path)
        with open(chunks_path, "rb") as f:
            chunks = pickle.load(f)

        distances, indices = index.search(query_embedding, k)
        top_distance = distances[0][0]
        adjusted_distance = top_distance - _source_bonus(query, name)
        best_indices = [i for i, d in zip(indices[0], distances[0]) if i < len(chunks) and d < RELEVANCE_THRESHOLD]
        if not best_indices and len(indices[0]) > 0 and indices[0][0] < len(chunks):
            best_indices = [indices[0][0]]

        best_chunks = [chunks[i] for i in best_indices]
        scored.append((adjusted_distance, name, best_chunks))

    scored.sort(key=lambda item: item[0])
    return scored


def search_all_indexes(query, k=3):
    preferred = _preferred_source_name(query)
    if preferred:
        index_path = f"{INDEX_DIR}/{preferred}/faiss_index"
        chunks_path = f"{INDEX_DIR}/{preferred}/chunks.pkl"
        if os.path.exists(index_path):
            index = faiss.read_index(index_path)
            with open(chunks_path, "rb") as f:
                chunks = pickle.load(f)
            query_embedding = embed_text([query])
            distances, indices = index.search(query_embedding, k)
            best_chunks = [
                chunks[i] for i, d in zip(indices[0], distances[0])
                if i < len(chunks) and d < RELEVANCE_THRESHOLD
            ]
            if not best_chunks and len(indices[0]) > 0 and indices[0][0] < len(chunks):
                best_chunks = [chunks[indices[0][0]]]
            return best_chunks, preferred

    scored = _score_indexes(query, k=k)
    if not scored:
        return [], None

    _, best_source, best_chunks = scored[0]
    return best_chunks, best_source


def search_multiple_indexes(query, k=3, max_sources=2):
    scored = _score_indexes(query, k=k)
    if not scored:
        return [], None

    best_distance = scored[0][0]
    chunks = []
    best_source = None

    for adjusted_distance, name, source_chunks in scored:
        if best_source is not None and adjusted_distance > best_distance + 0.35:
            break
        if source_chunks:
            if best_source is None:
                best_source = name
            chunks.extend(source_chunks)
        if len(chunks) > 0 and len({best_source, name}) >= max_sources:
            break

    return chunks, best_source
