import pytest

from tolaris_api.config import Settings


@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("postgres://u:s@host/db?sslmode=require", "postgresql+psycopg://u:s@host/db?sslmode=require"),
        ("postgresql://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
        ("  postgresql://u:s@host/db\n", "postgresql+psycopg://u:s@host/db"),
        ("postgresql+psycopg://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
        ("sqlite:///./x.db", "sqlite:///./x.db"),
    ],
)
def test_url_do_banco_aceita_formato_dos_provedores(entrada, esperado):
    assert Settings(database_url=entrada).database_url == esperado
