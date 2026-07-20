import os

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

_model = None
_device = None


def _resolve_device():
    preferred = os.getenv("ANA_EMBED_DEVICE", "auto").strip().lower()
    if preferred in {"cuda", "gpu"}:
        return "cuda" if torch.cuda.is_available() else "cpu"
    if preferred == "cpu":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _get_model():
    global _model, _device
    if _model is None:
        _device = _resolve_device()
        _model = SentenceTransformer("./models/embedding_model", device=_device)
    return _model


def embed_text(texts):
    embeddings = _get_model().encode(texts, show_progress_bar=False)
    return np.array(embeddings, dtype="float32")


def embedding_status():
    _get_model()
    return {
        "status": "ready",
        "preferred_device": os.getenv("ANA_EMBED_DEVICE", "auto").strip().lower(),
        "device": _device or "unknown",
    }
