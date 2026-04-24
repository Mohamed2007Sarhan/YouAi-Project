"""
Persistent voice profile: sample paths + optional ElevenLabs cloned voice ID.
Stored as JSON next to other memory files (no DB migration required).
"""

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_PROFILE_PATH = os.path.join(_DIR, "voice_profile.json")
USER_VOICE_DIR = os.path.join(os.path.dirname(_DIR), "user_data", "voice_samples")


def _ensure_dirs() -> None:
    os.makedirs(USER_VOICE_DIR, exist_ok=True)


def load_voice_profile() -> Dict[str, Any]:
    if not os.path.isfile(VOICE_PROFILE_PATH):
        return {"sample_paths": [], "elevenlabs_voice_id": ""}
    try:
        with open(VOICE_PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"sample_paths": [], "elevenlabs_voice_id": ""}
        data.setdefault("sample_paths", [])
        data.setdefault("elevenlabs_voice_id", "")
        return data
    except Exception:
        return {"sample_paths": [], "elevenlabs_voice_id": ""}


def save_voice_profile(
    sample_paths: List[str],
    elevenlabs_voice_id: Optional[str] = None,
) -> bool:
    _ensure_dirs()
    existing = load_voice_profile()
    payload = {
        "sample_paths": sample_paths,
        "elevenlabs_voice_id": elevenlabs_voice_id if elevenlabs_voice_id is not None else existing.get("elevenlabs_voice_id", ""),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with open(VOICE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def copy_samples_to_user_data(source_paths: List[str]) -> List[str]:
    """Copy uploaded audio files into user_data/voice_samples and return new paths."""
    _ensure_dirs()
    out: List[str] = []
    for i, src in enumerate(source_paths):
        if not src or not os.path.isfile(src):
            continue
        ext = os.path.splitext(src)[1].lower() or ".wav"
        if ext not in (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"):
            ext = ".wav"
        dst_name = f"voice_sample_{i+1}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
        dst = os.path.join(USER_VOICE_DIR, dst_name)
        try:
            shutil.copy2(src, dst)
            out.append(dst)
        except Exception:
            continue
    return out


def set_elevenlabs_voice_id(voice_id: str) -> bool:
    data = load_voice_profile()
    data["elevenlabs_voice_id"] = voice_id
    data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(VOICE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
