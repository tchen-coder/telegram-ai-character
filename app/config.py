from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

KNOWN_LLM_PROVIDERS = {
    "openai": {
        "base_url": None,
        "model": "gpt-4o-mini",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "grok": {
        "base_url": "https://api.x.ai/v1",
        "model": None,
    },
}


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_proxy: Optional[str] = None
    miniapp_url: Optional[str] = None
    telegram_connection_pool_size: int = 32
    telegram_connect_timeout: float = 20.0
    telegram_read_timeout: float = 30.0
    telegram_write_timeout: float = 30.0
    telegram_pool_timeout: float = 30.0

    # LLM 配置：支持已知 provider 默认值，也支持任意 OpenAI 兼容接口
    llm_provider: str = "deepseek"
    llm_api_key: Optional[str] = None
    xai_api_key: Optional[str] = Field(default=None, alias="XAI_API_KEY")
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 500

    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "mysql://root:password@localhost:3306/telegram_ai_character"
    weaviate_host: str = "localhost"
    weaviate_http_port: int = 8080
    weaviate_grpc_port: int = 50051
    weaviate_skip_init_checks: bool = True
    weaviate_role_collection: str = "RoleKnowledge"
    weaviate_memory_collection: str = "ConversationMemory"
    weaviate_role_top_k: int = 4
    weaviate_memory_top_k: int = 6
    weaviate_hybrid_alpha: float = 0.65
    weaviate_role_chunk_size: int = 420
    weaviate_role_chunk_overlap: int = 80
    cos_secret_id: Optional[str] = None
    cos_secret_key: Optional[str] = None
    cos_bucket: Optional[str] = None
    cos_region: Optional[str] = None
    cos_domain: Optional[str] = None
    cos_sign_expire: int = 600
    admin_token: Optional[str] = None
    debug: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_llm_provider(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator(
        "telegram_proxy",
        "miniapp_url",
        "llm_base_url",
        "llm_model",
        "weaviate_host",
        "admin_token",
        "cos_secret_id",
        "cos_secret_key",
        "cos_bucket",
        "cos_region",
        "cos_domain",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @property
    def cos_enabled(self) -> bool:
        return all(
            [
                self.cos_secret_id,
                self.cos_secret_key,
                self.cos_bucket,
                self.cos_region,
                self.cos_domain,
            ]
        )

    @property
    def llm_provider_defaults(self) -> dict:
        return KNOWN_LLM_PROVIDERS.get(self.llm_provider, {})

    @property
    def resolved_llm_base_url(self) -> Optional[str]:
        return self.llm_base_url or self.llm_provider_defaults.get("base_url")

    @property
    def resolved_llm_api_key(self) -> str:
        if self.llm_provider == "grok":
            api_key = self.xai_api_key or self.llm_api_key
        else:
            api_key = self.llm_api_key
        if api_key:
            return api_key
        raise ValueError(
            f"API key is required for LLM_PROVIDER={self.llm_provider}"
        )

    @property
    def resolved_llm_model(self) -> str:
        model = self.llm_model or self.llm_provider_defaults.get("model")
        if model:
            return model
        raise ValueError(
            f"LLM_MODEL is required when LLM_PROVIDER={self.llm_provider}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
