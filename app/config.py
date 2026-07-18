from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    LLM_PROVIDER: Literal["openai", "azure_openai", "anthropic"] = "azure_openai"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str | None = None
    OPENAI_BASE_URL: str | None = None

    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    AZURE_OPENAI_API_VERSION: str | None = None

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str | None = None

    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = Field(default=8000, ge=1, le=65535)
    APP_TIMEZONE: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    ZI_HOUR_DAY_BOUNDARY: int = Field(default=23, ge=0, le=24)
    KNOWLEDGE_DB_PATH: Path = Path("data/generated/knowledge.sqlite3")
    LLM_TEMPERATURE: float = Field(default=0, ge=0, le=0)
    LLM_TIMEOUT_SECONDS: float = Field(default=120, ge=1, le=600)

    @field_validator(
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OPENAI_BASE_URL",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        mode="before",
    )
    @classmethod
    def empty_string_is_none(cls, value: object) -> object:
        return None if value == "" else value

    def provider_config(self) -> dict[str, str]:
        required: dict[str, tuple[str, ...]] = {
            "openai": ("OPENAI_API_KEY", "OPENAI_MODEL"),
            "azure_openai": (
                "AZURE_OPENAI_API_KEY",
                "AZURE_OPENAI_ENDPOINT",
                "AZURE_OPENAI_DEPLOYMENT",
                "AZURE_OPENAI_API_VERSION",
            ),
            "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"),
        }
        names = required[self.LLM_PROVIDER]
        missing = [name for name in names if not getattr(self, name)]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(
                f"LLM_PROVIDER={self.LLM_PROVIDER} 缺少必要配置：{joined}"
            )
        return {name: str(getattr(self, name)) for name in names}


@lru_cache
def get_settings() -> Settings:
    return Settings()
