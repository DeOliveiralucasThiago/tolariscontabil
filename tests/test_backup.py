"""Backup e verificação do banco (SQLite sempre; PostgreSQL quando há pg_dump e um banco de testes)."""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tolaris_api import backup
from tolaris_api.db import Base, criar_engine
from tolaris_api import models  # noqa: F401
from tolaris_api.models import Cliente, Escritorio, Usuario


@pytest.fixture()
def banco(tmp_path: Path) -> Path:
    arq = tmp_path / "tolaris.db"
    engine = criar_engine(f"sqlite:///{arq.as_posix()}")
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        esc = Escritorio(nome="Escritório")
        db.add_all([esc, Usuario(escritorio=esc, nome="Ana", email="ana@x.com", senha_hash="x")])
        db.flush()
        db.add_all([Cliente(escritorio_id=esc.id, razao_social=f"Cliente {i}") for i in range(3)])
        db.commit()
    engine.dispose()
    return arq


def test_backup_sqlite_e_verificacao(banco: Path, tmp_path: Path):
    r = backup.criar(f"sqlite:///{banco.as_posix()}", tmp_path / "bk")
    assert r.arquivo.exists() and r.arquivo.suffix == ".sqlite" and r.bytes > 0
    assert (tmp_path / "bk" / (r.arquivo.name + ".sha256")).read_text().startswith(r.sha256)
    assert backup.verificar(r.arquivo) == {"escritorios": 1, "usuarios": 1, "clientes": 3, "simulacoes": 0}


def test_backup_nao_mexe_no_banco_de_origem(banco: Path, tmp_path: Path):
    antes = banco.read_bytes()
    backup.criar(f"sqlite:///{banco.as_posix()}", tmp_path / "bk")
    assert banco.read_bytes() == antes


def test_backup_com_o_sistema_gravando(banco: Path, tmp_path: Path):
    con = sqlite3.connect(banco)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("insert into clientes (escritorio_id, razao_social, status, cadastro_pendente, criado_em, atualizado_em) values (1, 'Novo', 'ativo', 0, '2026-01-01', '2026-01-01')")
    con.commit()  # fica no WAL: a cópia precisa trazer
    r = backup.criar(f"sqlite:///{banco.as_posix()}", tmp_path / "bk")
    con.close()
    assert backup.verificar(r.arquivo)["clientes"] == 4


def test_verificar_pega_arquivo_alterado_corrompido_e_incompleto(banco: Path, tmp_path: Path):
    r = backup.criar(f"sqlite:///{banco.as_posix()}", tmp_path / "bk")
    alterado = tmp_path / "alterado.sqlite"
    shutil.copy(r.arquivo, alterado)
    shutil.copy(r.arquivo.with_name(r.arquivo.name + ".sha256"), alterado.with_name("alterado.sqlite.sha256"))
    with open(alterado, "r+b") as f:
        f.seek(5000)
        f.write(b"\xff" * 64)
    with pytest.raises(backup.ErroBackup, match="sha256"):
        backup.verificar(alterado)
    lixo = tmp_path / "lixo.sqlite"
    lixo.write_bytes(b"isto nao e um banco" * 100)
    with pytest.raises(backup.ErroBackup, match="SQLite|corrompido"):
        backup.verificar(lixo)
    vazio = tmp_path / "vazio.sqlite"
    sqlite3.connect(vazio).execute("create table x (a)").connection.commit()
    with pytest.raises(backup.ErroBackup, match="não tem as tabelas"):
        backup.verificar(vazio)
    with pytest.raises(backup.ErroBackup, match="não encontrado"):
        backup.verificar(tmp_path / "nao-existe.sqlite")
    with pytest.raises(backup.ErroBackup, match="Formato"):
        (tmp_path / "x.zip").write_bytes(b"x")
        backup.verificar(tmp_path / "x.zip")


def test_retencao_mantem_so_os_mais_recentes(banco: Path, tmp_path: Path):
    destino = tmp_path / "bk"
    base = datetime(2026, 1, 1, 8, 0, 0)
    for i in range(5):
        backup.criar(f"sqlite:///{banco.as_posix()}", destino, manter=3, agora=base + timedelta(days=i))
    nomes = sorted(a.name for a in destino.glob("*.sqlite"))
    assert nomes == ["tolaris-20260103-080000.sqlite", "tolaris-20260104-080000.sqlite", "tolaris-20260105-080000.sqlite"]
    assert len(list(destino.glob("*.sha256"))) == 3
    (destino / "outro-arquivo.txt").write_text("não é backup")
    backup.criar(f"sqlite:///{banco.as_posix()}", destino, manter=1, agora=base + timedelta(days=9))
    assert (destino / "outro-arquivo.txt").exists() and len(list(destino.glob("tolaris-*.sqlite"))) == 1


def test_erros_claros(tmp_path: Path):
    with pytest.raises(backup.ErroBackup, match="não encontrado"):
        backup.criar(f"sqlite:///{(tmp_path / 'nao.db').as_posix()}", tmp_path / "bk")
    with pytest.raises(backup.ErroBackup, match="memória"):
        backup.criar("sqlite://", tmp_path / "bk")
    with pytest.raises(backup.ErroBackup, match="não suportado"):
        backup.criar("mysql://u@h/d", tmp_path / "bk")


def test_linha_de_comando(banco: Path, tmp_path: Path, capsys):
    assert backup.principal(["criar", "--banco", f"sqlite:///{banco.as_posix()}", "--destino", str(tmp_path / "bk")]) == 0
    saida = capsys.readouterr().out
    assert "Backup criado" in saida and "clientes 3" in saida
    arq = next((tmp_path / "bk").glob("*.sqlite"))
    assert backup.principal(["verificar", str(arq)]) == 0
    assert backup.principal(["verificar", str(tmp_path / "nada.sqlite")]) == 1
    assert "ERRO" in capsys.readouterr().err


@pytest.mark.skipif(
    not os.environ.get("TOLARIS_TEST_DATABASE_URL", "").startswith("postgresql") or not shutil.which("pg_dump"),
    reason="precisa de PostgreSQL de teste e do pg_dump",
)
def test_backup_postgres_com_restauracao_de_verdade(tmp_path: Path):
    url = os.environ["TOLARIS_TEST_DATABASE_URL"]
    engine = criar_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        esc = Escritorio(nome="Escritório PG")
        db.add_all([esc, Usuario(escritorio=esc, nome="Ana", email="ana@pg.com", senha_hash="x")])
        db.flush()
        db.add(Cliente(escritorio_id=esc.id, razao_social="Cliente PG"))
        db.commit()
    r = backup.criar(url, tmp_path)
    assert r.arquivo.suffix == ".dump"
    contagem = backup.verificar(r.arquivo, restaurar_em=url)
    assert contagem == {"escritorios": 1, "usuarios": 1, "clientes": 1, "simulacoes": 0}
    Base.metadata.drop_all(engine)
    engine.dispose()
