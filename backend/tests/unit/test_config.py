import pytest

from app.core.config import ConfigurationError, Settings, get_settings
from tests.conftest import SECRET, make_settings


def test_local_defaults_are_valid():
    s = make_settings()
    assert s.app_env == "local" and s.use_mock_integrations and s.cors_origins == ["https://localhost:3000"]


def _bad(**kw):
    with pytest.raises(ValueError) as exc:
        make_settings(**kw)
    return str(exc.value)


def test_dev_auth_is_refused_outside_local():
    assert "AUTH_MODE=dev is only allowed" in _bad(app_env="staging")


def test_dev_auth_needs_a_long_secret():
    assert "DEV_JWT_SECRET" in _bad(dev_jwt_secret="short")
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="local", auth_mode="dev")


def test_entra_requires_tenant_and_audience():
    assert "ENTRA_TENANT_ID" in _bad(auth_mode="entra", dev_jwt_secret=None)


def test_wildcard_cors_is_refused():
    assert "not '*'" in _bad(cors_allowed_origins="https://a.example, *")


def test_real_integrations_need_https_urls_and_tokens():
    msg = _bad(
        use_mock_integrations=False, bug_api_base_url="http://bugs.internal", docs_api_base_url="https://d.internal"
    )
    assert "BUG_API_BASE_URL" in msg and "BUG_API_TOKEN" in msg
    ok = make_settings(
        use_mock_integrations=False,
        bug_api_base_url="https://bugs.internal",
        docs_api_base_url="https://docs.internal",
        bug_api_token="t1",
        docs_api_token="t2",
    )
    assert ok.bug_api_token.get_secret_value() == "t1"
    assert "t1" not in repr(ok)  # secrets are masked in reprs


def test_production_forbids_mock_integrations():
    msg = _bad(app_env="production", auth_mode="entra", dev_jwt_secret=None, entra_tenant_id="t", entra_audience="a")
    assert "USE_MOCK_INTEGRATIONS must be false" in msg


def test_get_settings_errors_never_echo_secret_values(monkeypatch):
    get_settings.cache_clear()
    for k, v in {
        "APP_ENV": "local",
        "AUTH_MODE": "dev",
        "DEV_JWT_SECRET": SECRET,
        "LLM_API_KEY": "sk-VERY-SECRET-VALUE",
        "CORS_ALLOWED_ORIGINS": "*",
    }.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(ConfigurationError) as exc:
        get_settings()
    text = str(exc.value)
    assert "CORS_ALLOWED_ORIGINS" in text
    assert "sk-VERY-SECRET-VALUE" not in text and SECRET not in text
    get_settings.cache_clear()
