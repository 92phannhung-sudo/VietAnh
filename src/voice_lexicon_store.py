"""Global voice lexicon persistence (Settings-wide, not per-staff)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from src.patient_session_controller import _DEFAULT_LEXICON


def default_lexicon_path(base_dir: Path | str) -> Path:
    return Path(base_dir) / "voice_lexicon.json"


def load_lexicon(path: str | Path) -> Dict[str, str]:
    """Load phrase→intent map; fall back to controller defaults if missing/corrupt."""
    p = Path(path)
    base = dict(_DEFAULT_LEXICON)
    if not p.exists():
        return base
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return base
        cleaned = {
            str(k).strip().lower(): str(v).strip()
            for k, v in data.items()
            if str(k).strip() and str(v).strip()
        }
        if cleaned:
            return cleaned
        return base
    except (OSError, json.JSONDecodeError, TypeError):
        return base


def save_lexicon(path: str | Path, phrases: Dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {
        str(k).strip().lower(): str(v).strip()
        for k, v in phrases.items()
        if str(k).strip() and str(v).strip()
    }
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
