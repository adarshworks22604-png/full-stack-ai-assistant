"""Configuration from environment variables. Fails fast on unsafe combinations."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- runtime ---
    app_env: Literal["local", "staging", "production"] = "local"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_allowed_origins: str = "https://localhost:3000"

    # --- authentication ---
    auth_mode: Literal["dev", "entra"] = "dev"
    dev_jwt_secret: SecretStr | None = None
    entra_tenant_id: str | None = None
    entra_audience: str | None = None
    entra_issuer: str | None = None  # optional override; default is the v2.0 issuer
    # JSON object mapping Entra group IDs to product names, e.g. {"<group-id>": ["payments"]}
    entra_group_product_map: str = "{}"
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=300)

    # --- request limits ---
    max_request_body_bytes: int = Field(default=65_536, ge=1_024)
    request_timeout_seconds: float = Field(default=60.0, gt=0)
    sse_heartbeat_seconds: float = Field(default=15.0, gt=0)
    rate_limit_per_minute: int = Field(default=20, ge=1)
    max_concurrent_streams_global: int = Field(default=50, ge=1)
    max_concurrent_streams_per_user: int = Field(default=2, ge=1)

    # --- upstream calls (bug tracker + docs search) ---
    use_mock_integrations: bool = True
    mock_step_delay_seconds: float = Field(default=0.3, ge=0)
    bug_id_pattern: str = r"\bBUG-\d{1,8}\b"
    bug_api_base_url: str | None = None
    bug_api_token: SecretStr | None = None
    docs_api_base_url: str | None = None
    docs_api_token: SecretStr | None = None
    upstream_connect_timeout: float = Field(default=3.0, gt=0)
    upstream_read_timeout: float = Field(default=8.0, gt=0)
    upstream_write_timeout: float = Field(default=5.0, gt=0)
    upstream_pool_timeout: float = Field(default=3.0, gt=0)
    upstream_max_retries: int = Field(default=2, ge=0, le=5)
    upstream_backoff_base_seconds: float = Field(default=0.2, ge=0)
    upstream_backoff_max_seconds: float = Field(default=2.0, ge=0)
    upstream_max_concurrency: int = Field(default=10, ge=1)
    upstream_max_response_bytes: int = Field(default=1_000_000, ge=1_024)

    # --- later stages (names reserved; not used yet) ---
    llm_provider: str = "openai"
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    database_url: SecretStr | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _check_safe_combinations(self) -> "Settings":
        problems: list[str] = []
        if self.auth_mode == "dev":
            if self.app_env != "local":
                problems.append("AUTH_MODE=dev is only allowed when APP_ENV=local")
            if self.dev_jwt_secret is None or len(self.dev_jwt_secret.get_secret_value()) < 32:
                problems.append("DEV_JWT_SECRET must be set to at least 32 characters when AUTH_MODE=dev")
        else:
            if not self.entra_tenant_id or not self.entra_audience:
                problems.append("ENTRA_TENANT_ID and ENTRA_AUDIENCE are required when AUTH_MODE=entra")
        if any(o == "*" for o in self.cors_origins):
            problems.append("CORS_ALLOWED_ORIGINS must list explicit origins, not '*'")
        if not self.use_mock_integrations:
            for name, value in (
                ("BUG_API_BASE_URL", self.bug_api_base_url),
                ("DOCS_API_BASE_URL", self.docs_api_base_url),
            ):
                if not value or not value.startswith("https://"):
                    problems.append(f"{name} must be an https:// URL when USE_MOCK_INTEGRATIONS=false")
            if self.bug_api_token is None or self.docs_api_token is None:
                problems.append("BUG_API_TOKEN and DOCS_API_TOKEN are required when USE_MOCK_INTEGRATIONS=false")
        if self.app_env == "production" and self.use_mock_integrations:
            problems.append("USE_MOCK_INTEGRATIONS must be false when APP_ENV=production")
        if problems:
            # Messages name variables only; never include values.
            raise ValueError("Invalid configuration: " + "; ".join(problems))
        return self


class ConfigurationError(RuntimeError):
    """Startup configuration problem. The message names settings, never their values."""


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        # pydantic's default error text echoes input values, which could include secrets.
        problems = sorted({f"{'.'.join(str(p) for p in e['loc']) or 'settings'}: {e['msg']}" for e in exc.errors()})
        raise ConfigurationError("; ".join(problems)) from None
