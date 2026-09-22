from prepwise_api.database import database_connect_args


def test_production_database_connections_require_tls() -> None:
    assert database_connect_args("production") == {"sslmode": "require"}


def test_non_production_database_connections_keep_local_defaults() -> None:
    assert database_connect_args("development") == {}
    assert database_connect_args("test") == {}
