from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.divination.service import DivinationService


@lru_cache
def get_divination_service() -> DivinationService:
    return DivinationService(
        settings=get_settings(),
        repo_root=Path(__file__).resolve().parents[2],
    )

