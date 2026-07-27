from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_AGENT_ROOT = Path(__file__).resolve().parent.parent / "agent"
_DEFAULT_CONFIG_DIR = _AGENT_ROOT / "configs"
_DEFAULT_SCHEMA_DIR = _AGENT_ROOT / "schemas"


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    AGENT_CONFIG_DIR: str = Field(default=str(_DEFAULT_CONFIG_DIR))
    AGENT_SCHEMA_DIR: str = Field(default=str(_DEFAULT_SCHEMA_DIR))

    LLM_BRIDGE_URL: str = "http://localhost:15000/v1"
    LLM_SERVED_MODEL_NAME: str = "LLM"
    EMBEDDING_BRIDGE_URL: str = "http://localhost:15001/v1"
    EMBEDDING_SERVED_MODEL_NAME: str = "embedding"

    AGENT_API_KEY: str = "not-needed"
    AGENT_EAGER_LOAD: bool = False
    AGENT_DEFAULT_TIMEOUT: float = 300.0
    AGENT_DEFAULT_MAX_RETRIES: int = 2

    @field_validator("AGENT_CONFIG_DIR", "AGENT_SCHEMA_DIR")
    @classmethod
    def validate_dir_exists(cls, v: str, info) -> str:
        path = Path(v)
        if not path.is_dir():
            raise ValueError(
                f"{info.field_name} bukan direktori valid: '{v}' "
                f"(resolved: '{path.resolve()}')"
            )
        return v

    @property
    def config_dir(self) -> Path:
        return Path(self.AGENT_CONFIG_DIR)

    @property
    def schema_dir(self) -> Path:
        return Path(self.AGENT_SCHEMA_DIR)

    @property
    def model_bridge(self) -> dict:
        return {
            "llm": {
                "url": self.LLM_BRIDGE_URL,
                "served_model_name": self.LLM_SERVED_MODEL_NAME,
            },
            "embedding": {
                "url": self.EMBEDDING_BRIDGE_URL,
                "served_model_name": self.EMBEDDING_SERVED_MODEL_NAME,
            },
        }


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()