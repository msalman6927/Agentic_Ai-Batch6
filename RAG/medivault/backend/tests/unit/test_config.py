from medivault.config import Settings
from medivault.utils.errors import ConfigError, NotFoundError


def test_database_url_normalizes_driver() -> None:
    settings = Settings(database_url="postgres://user:pass@host/db", _env_file=None)
    assert settings.require_database_url() == ("postgresql+asyncpg://user:pass@host/db")


def test_database_url_keeps_existing_asyncpg_driver() -> None:
    url = "postgresql+asyncpg://user:pass@host/db"
    settings = Settings(database_url=url, _env_file=None)
    assert settings.require_database_url() == url


def test_missing_database_url_raises_config_error() -> None:
    settings = Settings(database_url="", _env_file=None)
    try:
        settings.require_database_url()
    except ConfigError as exc:
        assert exc.code == "config_error"
    else:
        raise AssertionError("expected ConfigError")


def test_sslmode_is_stripped_and_reported() -> None:
    settings = Settings(
        database_url="postgresql://u:p@h/db?sslmode=require&channel_binding=require",
        _env_file=None,
    )
    dsn = settings.require_database_url()
    assert "sslmode" not in dsn
    assert "channel_binding" not in dsn
    assert dsn.startswith("postgresql+asyncpg://")
    assert settings.database_ssl_mode() == "require"


def test_sslmode_absent_returns_none() -> None:
    settings = Settings(database_url="postgresql://u:p@h/db", _env_file=None)
    assert settings.database_ssl_mode() is None
    assert settings.require_database_url() == "postgresql+asyncpg://u:p@h/db"


def test_domain_error_codes() -> None:
    assert NotFoundError("x").code == "not_found"
    assert NotFoundError("x").status_code == 404
