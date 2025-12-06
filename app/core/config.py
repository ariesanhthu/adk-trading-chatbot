"""Application settings and configuration."""

import json
from typing import Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_PREFIX: str = "/api"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Trading Chatbot ADK Backend"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]  # Chỉnh lại domain thật khi deploy

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, list]) -> list[str]:
        """Parse CORS origins from string (JSON) or list."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Nếu là string đơn giản (không phải JSON), wrap vào list
            if not v.strip().startswith("["):
                return [v.strip()] if v.strip() else ["*"]
            # Nếu là JSON string, parse nó
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                # Nếu parse JSON fail, coi như string đơn giản
                return [v.strip()] if v.strip() else ["*"]
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # bỏ qua các biến môi trường không định nghĩa
    )


settings = Settings()
