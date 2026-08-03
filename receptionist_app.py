import json
import logging
import os
import re
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from utils.wav2lip_service import MEDIA_DIR, Wav2LipService
from utils.schedule_service import is_schedule_query

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend" / "receptionist"
AUDIO_DIR = BASE_DIR / "runtime" / "audio"
RESPONSE_CACHE_PATH = BASE_DIR / "cache" / "receptionist_responses.json"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ANA Wav2Lip Receptionist", version="1.0.0")
APP_MODE = "wav2lip_video_first"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8020", "http://localhost:8020"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/media/wav2lip", StaticFiles(directory=MEDIA_DIR), name="wav2lip-media")
app.mount("/media/audio", StaticFiles(directory=AUDIO_DIR), name="audio-media")

sessions: Dict[str, List[Dict[str, str]]] = {}
wav2lip_service = Wav2LipService()
_tts_service = None
_stt_service = None
_response_cache_lock = threading.Lock()


class ReceptionistRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: str | None = None
    speaker_enabled: bool = True


class ReceptionistResponse(BaseModel):
    session_id: str
    answer: str
    video_url: str | None = None
    audio_url: str | None = None
    meta: Dict[str, object]


def get_tts_service():
    global _tts_service
    if _tts_service is None:
        from utils.voice_tts import TextToSpeechService

        _tts_service = TextToSpeechService()
    return _tts_service


def get_stt_service():
    global _stt_service
    if _stt_service is None:
        from utils.voice_stt import SpeechToTextService

        _stt_service = SpeechToTextService()
    return _stt_service


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/status")
def status() -> Dict[str, object]:
    return {
        "status": "ok",
        "mode": APP_MODE,
        "response_cache": {"entries": len(_load_response_cache())},
        "wav2lip": wav2lip_service.status(),
    }


@app.post("/api/bootstrap")
def bootstrap() -> Dict[str, object]:
    steps = []
    steps.append({"name": "wav2lip", "result": wav2lip_service.warmup()})
    return {"status": "ready" if wav2lip_service.is_ready() else "setup_required", "steps": steps}


@app.post("/api/receptionist/respond", response_model=ReceptionistResponse)
def respond(payload: ReceptionistRequest) -> ReceptionistResponse:
    from utils.chat_service import ChatServiceError, answer_receptionist

    session_id = payload.session_id or uuid4().hex
    history = sessions.setdefault(session_id, [])
    try:
        started_at = time.perf_counter()
        cached_answer = _cached_answer_for_message(payload.message)
        if cached_answer:
            answer = _limit_for_video(cached_answer)
            cached_video = wav2lip_service.cached_video_for_text(answer)
            if not cached_video or not Path(cached_video["audio_path"]).exists() or not Path(cached_video["text_path"]).exists():
                audio_path = _synthesize_audio(answer)
                cached_video = wav2lip_service.generate(audio_path=audio_path, text=answer)
            history.append({"role": "user", "content": payload.message})
            history.append({"role": "assistant", "content": answer})
            return ReceptionistResponse(
                session_id=session_id,
                answer=answer,
                video_url=str(cached_video["video_url"]),
                audio_url=None,
                meta={
                    "chat": {"source": "response_cache", "model": "cache"},
                    "wav2lip": {k: str(v) for k, v in cached_video.items() if k != "video_path"},
                    "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                },
            )

        answer, chat_meta = answer_receptionist(payload.message, history)
        answer = _limit_for_video(answer)
        cached_video = wav2lip_service.cached_video_for_text(answer)
        if cached_video:
            if not Path(cached_video["audio_path"]).exists() or not Path(cached_video["text_path"]).exists():
                audio_path = _synthesize_audio(answer)
                cached_video = wav2lip_service.generate(audio_path=audio_path, text=answer)
            _save_answer_for_message(payload.message, answer)
            return ReceptionistResponse(
                session_id=session_id,
                answer=answer,
                video_url=str(cached_video["video_url"]),
                audio_url=None,
                meta={
                    "chat": chat_meta,
                    "wav2lip": {k: str(v) for k, v in cached_video.items() if k != "video_path"},
                    "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                },
            )
        audio_path = _synthesize_audio(answer)
        wav_meta = wav2lip_service.generate(audio_path=audio_path, text=answer)
        _save_answer_for_message(payload.message, answer)
        return ReceptionistResponse(
            session_id=session_id,
            answer=answer,
            video_url=str(wav_meta["video_url"]),
            audio_url=None,
            meta={
                "chat": chat_meta,
                "wav2lip": {k: str(v) for k, v in wav_meta.items() if k != "video_path"},
                "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
    except ChatServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Receptionist response failed.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> Dict[str, object]:
    try:
        audio_bytes = await audio.read()
        suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
        result = get_stt_service().transcribe_bytes(audio_bytes, suffix=suffix)
        if not result["text"]:
            raise HTTPException(status_code=422, detail="I could not hear a clear question. Please try again.")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription failed.")
        raise HTTPException(status_code=500, detail=f"Speech recognition failed: {exc}") from exc


@app.get("/assets/avatar/neutral")
def neutral_avatar() -> FileResponse:
    return FileResponse(wav2lip_service.avatar_path)


def _synthesize_audio(text: str) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio = get_tts_service().synthesize_wav(text)
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", dir=AUDIO_DIR)
    with handle:
        handle.write(audio)
    return Path(handle.name)


def _audio_url_for_path(audio_path: Path) -> str:
    return f"/media/audio/{audio_path.name}"


def _limit_for_video(answer: str) -> str:
    max_chars = int(os.getenv("ANA_MAX_REPLY_CHARS", "360"))
    answer = " ".join((answer or "").split())
    if len(answer) <= max_chars:
        return answer
    trimmed = answer[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{trimmed}."


def _cached_answer_for_message(message: str) -> str | None:
    if not _can_use_response_cache(message):
        return None
    cache = _load_response_cache()
    item = cache.get(_response_cache_key(message))
    if not item:
        return None
    answer = str(item.get("answer", "")).strip()
    return answer or None


def _save_answer_for_message(message: str, answer: str) -> None:
    if not _can_use_response_cache(message):
        return
    key = _response_cache_key(message)
    with _response_cache_lock:
        cache = _load_response_cache()
        cache[key] = {
            "answer": answer,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        RESPONSE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        RESPONSE_CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _load_response_cache() -> Dict[str, Dict[str, str]]:
    if not RESPONSE_CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(RESPONSE_CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        logger.warning("Could not read receptionist response cache.", exc_info=True)
        return {}


def _can_use_response_cache(message: str) -> bool:
    normalized = _response_cache_key(message)
    if len(normalized.split()) < 2:
        return False
    if is_schedule_query(message):
        return False
    if _looks_like_greeting_query(normalized):
        return False
    if _looks_like_college_query(normalized):
        return False
    return not re.match(r"^(what about|and|also|it|that|those|they|he|she|his|her)\b", normalized)


def _looks_like_college_query(normalized_message: str) -> bool:
    keywords = (
        "kcc",
        "college",
        "kantipur",
        "admission",
        "bca",
        "bit",
        "bba",
        "club",
        "team",
        "committee",
        "department",
        "service",
        "student",
        "research",
        "curricular",
        "cirricular",
    )
    return any(keyword in normalized_message for keyword in keywords)


def _looks_like_greeting_query(normalized_message: str) -> bool:
    normalized_message = re.sub(r"(.)\1{2,}", r"\1\1", normalized_message)
    return any(
        phrase in normalized_message
        for phrase in (
            "hello",
            "hi",
            "hey",
            "namaste",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
            "good mornig",
            "good mornin",
            "good afternon",
            "good evning",
        )
    )


def _response_cache_key(message: str) -> str:
    text = re.sub(r"\bb\s*c\s*a\s*[- ]?\s*i\s*t\b", "bca-it", message.lower())
    text = re.sub(r"\bbca\s*id\b|\bbcaid\b|\bbcait\b", "bca-it", text)
    text = re.sub(r"[^a-z0-9\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()
