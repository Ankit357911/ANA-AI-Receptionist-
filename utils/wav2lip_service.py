import hashlib
import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import imageio_ffmpeg

logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent
WAV2LIP_DIR = BASE_DIR / "Wav2Lip"
DEFAULT_AVATAR_PATH = BASE_DIR / "assets" / "avatar" / "nepali_receptionist_neutral.png"
DEFAULT_CHECKPOINT_PATH = WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"
RUNTIME_DIR = BASE_DIR / "runtime" / "wav2lip"
CACHE_DIR = Path(os.getenv("ANA_WAV2LIP_CACHE_DIR", str(BASE_DIR / "cache" / "wav2lip")))
MEDIA_DIR = CACHE_DIR / "media"
AUDIO_CACHE_DIR = CACHE_DIR / "audio"
TEXT_CACHE_DIR = CACHE_DIR / "text"
TOOL_DIR = RUNTIME_DIR / "tools"


class Wav2LipService:
    def __init__(
        self,
        avatar_path: Path = DEFAULT_AVATAR_PATH,
        checkpoint_path: Path = DEFAULT_CHECKPOINT_PATH,
        media_url_prefix: str = "/media/wav2lip",
    ) -> None:
        self.avatar_path = Path(avatar_path)
        self.checkpoint_path = Path(checkpoint_path)
        self.media_url_prefix = media_url_prefix.rstrip("/")
        self._lock = threading.Lock()
        self.last_error: Optional[str] = None

    def status(self) -> Dict[str, object]:
        cached_videos = list(MEDIA_DIR.glob("*.mp4")) if MEDIA_DIR.exists() else []
        cached_audio = list(AUDIO_CACHE_DIR.glob("*.wav")) if AUDIO_CACHE_DIR.exists() else []
        cached_text = list(TEXT_CACHE_DIR.glob("*.json")) if TEXT_CACHE_DIR.exists() else []
        return {
            "status": "ready" if self.is_ready() else "setup_required",
            "avatar_exists": self.avatar_path.exists(),
            "checkpoint_exists": self.checkpoint_path.exists(),
            "checkpoint_path": str(self.checkpoint_path),
            "avatar_path": str(self.avatar_path),
            "cache_dir": str(MEDIA_DIR),
            "cached_videos": len(cached_videos),
            "cached_audio": len(cached_audio),
            "cached_text": len(cached_text),
            "last_error": self.last_error,
        }

    def is_ready(self) -> bool:
        return self.avatar_path.exists() and self.checkpoint_path.exists()

    def cached_video_for_text(self, text: str) -> Optional[Dict[str, object]]:
        paths = self._cache_paths(text)
        output_path = paths["video_path"]
        if output_path.exists() and output_path.stat().st_size > 0:
            return {
                "video_path": output_path,
                "video_url": f"{self.media_url_prefix}/{paths['video_name']}",
                "audio_path": paths["audio_path"],
                "text_path": paths["text_path"],
                "cached": True,
            }
        return None

    def warmup(self) -> Dict[str, object]:
        MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        TEXT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        TOOL_DIR.mkdir(parents=True, exist_ok=True)
        ffmpeg_path = self._ensure_ffmpeg()
        status = self.status()
        status["ffmpeg_path"] = str(ffmpeg_path)
        return status

    def generate(self, audio_path: Path, text: str, request_id: Optional[str] = None) -> Dict[str, object]:
        self.warmup()
        if not self.is_ready():
            raise FileNotFoundError("Wav2Lip checkpoint or avatar image is missing.")

        paths = self._cache_paths(text, request_id=request_id)
        output_path = paths["video_path"]
        if output_path.exists() and output_path.stat().st_size > 0:
            self._persist_cache_assets(audio_path, text, paths)
            return {
                "video_path": output_path,
                "video_url": f"{self.media_url_prefix}/{paths['video_name']}",
                "audio_path": paths["audio_path"],
                "text_path": paths["text_path"],
                "cached": True,
            }

        with self._lock:
            if output_path.exists() and output_path.stat().st_size > 0:
                self._persist_cache_assets(audio_path, text, paths)
                return {
                    "video_path": output_path,
                    "video_url": f"{self.media_url_prefix}/{paths['video_name']}",
                    "audio_path": paths["audio_path"],
                    "text_path": paths["text_path"],
                    "cached": True,
                }
            started_at = time.perf_counter()
            self._run_inference(audio_path, output_path)
            self._persist_cache_assets(audio_path, text, paths)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            return {
                "video_path": output_path,
                "video_url": f"{self.media_url_prefix}/{paths['video_name']}",
                "audio_path": paths["audio_path"],
                "text_path": paths["text_path"],
                "cached": False,
                "elapsed_ms": elapsed_ms,
            }

    def _run_inference(self, audio_path: Path, output_path: Path) -> None:
        env = os.environ.copy()
        env["PATH"] = f"{TOOL_DIR}{os.pathsep}{env.get('PATH', '')}"
        env["CUDA_VISIBLE_DEVICES"] = env.get("ANA_WAV2LIP_CUDA_DEVICE", "0")

        command = [
            str(BASE_DIR / "venv" / "Scripts" / "python.exe"),
            "inference.py",
            "--checkpoint_path",
            str(self.checkpoint_path),
            "--face",
            str(self.avatar_path),
            "--audio",
            str(audio_path),
            "--outfile",
            str(output_path),
            "--static",
            "True",
            "--fps",
            os.getenv("ANA_WAV2LIP_FPS", "15"),
            "--face_det_batch_size",
            os.getenv("ANA_FACE_DET_BATCH_SIZE", "2"),
            "--wav2lip_batch_size",
            os.getenv("ANA_WAV2LIP_BATCH_SIZE", "16"),
            "--pads",
            "0",
            "20",
            "0",
            "0",
        ]

        logger.info("Running Wav2Lip inference for %s", audio_path)
        result = subprocess.run(
            command,
            cwd=str(WAV2LIP_DIR),
            env=env,
            text=True,
            capture_output=True,
            timeout=int(os.getenv("ANA_WAV2LIP_TIMEOUT", "180")),
        )
        if result.returncode != 0:
            self.last_error = (result.stderr or result.stdout or "Wav2Lip inference failed.").strip()[-2000:]
            logger.error("Wav2Lip failed: %s", self.last_error)
            raise RuntimeError(self.last_error)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Wav2Lip did not produce an output video.")

    def _cache_key(self, text: str) -> str:
        fps = os.getenv("ANA_WAV2LIP_FPS", "15")
        normalized_text = " ".join((text or "").split()).strip().lower()
        cache_parts = [
            normalized_text,
            self._file_fingerprint(self.avatar_path),
            self._file_fingerprint(self.checkpoint_path),
            f"fps={fps}",
        ]
        return hashlib.sha256("|".join(cache_parts).encode("utf-8")).hexdigest()[:20]

    def _cache_paths(self, text: str, request_id: Optional[str] = None) -> Dict[str, Path | str]:
        digest = request_id or self._cache_key(text)
        return {
            "digest": digest,
            "video_name": f"{digest}.mp4",
            "audio_name": f"{digest}.wav",
            "text_name": f"{digest}.json",
            "video_path": MEDIA_DIR / f"{digest}.mp4",
            "audio_path": AUDIO_CACHE_DIR / f"{digest}.wav",
            "text_path": TEXT_CACHE_DIR / f"{digest}.json",
        }

    def _persist_cache_assets(self, audio_path: Path, text: str, paths: Dict[str, Path | str]) -> None:
        audio_cache_path = Path(paths["audio_path"])
        text_cache_path = Path(paths["text_path"])
        if Path(audio_path).exists() and not audio_cache_path.exists():
            shutil.copy2(audio_path, audio_cache_path)
        metadata = {
            "text": text,
            "video": str(paths["video_path"]),
            "audio": str(audio_cache_path),
            "avatar": str(self.avatar_path),
            "checkpoint": str(self.checkpoint_path),
            "fps": os.getenv("ANA_WAV2LIP_FPS", "15"),
            "cache_key": str(paths["digest"]),
        }
        text_cache_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    @staticmethod
    def _file_fingerprint(path: Path) -> str:
        if not path.exists():
            return f"{path}:missing"
        stat = path.stat()
        return f"{path.name}:size={stat.st_size}"

    @staticmethod
    def _ensure_ffmpeg() -> Path:
        target = TOOL_DIR / "ffmpeg.exe"
        if target.exists():
            return target
        source = Path(imageio_ffmpeg.get_ffmpeg_exe())
        shutil.copy2(source, target)
        return target
