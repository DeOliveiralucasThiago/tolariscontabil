"""Backup do banco com verificação.

    python -m tolaris_api.backup criar [--destino PASTA] [--manter 14]
    python -m tolaris_api.backup verificar ARQUIVO [--restaurar-em URL_ADMIN_POSTGRES]

SQLite: cópia consistente pela API de backup do próprio SQLite (pode rodar com o sistema aberto).
PostgreSQL: ``pg_dump`` em formato custom (precisa do cliente do PostgreSQL instalado).
Um backup que nunca foi restaurado não é backup: ``verificar`` abre o arquivo e confere o conteúdo; no PostgreSQL,
com ``--restaurar-em``, restaura de verdade num banco temporário e o apaga em seguida.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import URL, make_url

from .config import get_settings

PREFIXO = "tolaris-"
TABELAS_ESSENCIAIS = ("escritorios", "usuarios", "clientes", "simulacoes")


class ErroBackup(Exception):
    pass


@dataclass
class ResultadoBackup:
    arquivo: Path
    bytes: int
    sha256: str


def _sha256(arq: Path) -> str:
    h = hashlib.sha256()
    with arq.open("rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _caminho_sqlite(url: URL) -> Path:
    if not url.database or url.database == ":memory:":
        raise ErroBackup("O banco SQLite está em memória: não há o que copiar.")
    return Path(url.database)


def _ferramenta(nome: str) -> str:
    achada = shutil.which(nome)
    if not achada:
        raise ErroBackup(f"Não encontrei '{nome}'. Instale o cliente do PostgreSQL (pacote postgresql-client) no servidor do backup.")
    return achada


def _args_conexao(url: URL) -> tuple[list[str], dict[str, str]]:
    host = url.host or url.query.get("host")
    args = []
    if host:
        args += ["--host", str(host)]
    porta = url.port or url.query.get("port")
    if porta:
        args += ["--port", str(porta)]
    if url.username:
        args += ["--username", url.username]
    env = dict(os.environ)
    if url.password:
        env["PGPASSWORD"] = url.password  # nunca na linha de comando (aparece na lista de processos)
    return args, env


def _rodar(cmd: list[str], env: dict[str, str] | None = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600)
    if r.returncode != 0:
        raise ErroBackup(f"{Path(cmd[0]).name} falhou: {(r.stderr or r.stdout).strip()[:500]}")
    return r.stdout


def _podar(destino: Path, manter: int) -> list[Path]:
    arquivos = sorted((a for a in destino.iterdir() if a.name.startswith(PREFIXO) and a.suffix in (".sqlite", ".dump")), key=lambda a: a.name)
    apagados = arquivos[:-manter] if manter > 0 else []
    for a in apagados:
        a.unlink()
        a.with_name(a.name + ".sha256").unlink(missing_ok=True)
    return apagados


def criar(url: str, destino: Path, manter: int = 14, agora: datetime | None = None) -> ResultadoBackup:
    u = make_url(url)
    destino.mkdir(parents=True, exist_ok=True)
    carimbo = (agora or datetime.now()).strftime("%Y%m%d-%H%M%S")
    if u.get_backend_name() == "sqlite":
        origem = _caminho_sqlite(u)
        if not origem.exists():
            raise ErroBackup(f"Banco não encontrado: {origem}")
        arq = destino / f"{PREFIXO}{carimbo}.sqlite"
        with sqlite3.connect(f"file:{origem.as_posix()}?mode=ro", uri=True) as src, sqlite3.connect(arq) as dst:
            src.backup(dst)
        con = sqlite3.connect(arq)
        try:
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            con.close()
        if ok != "ok":
            arq.unlink(missing_ok=True)
            raise ErroBackup(f"A cópia não passou na verificação de integridade: {ok}")
    elif u.get_backend_name() == "postgresql":
        arq = destino / f"{PREFIXO}{carimbo}.dump"
        args, env = _args_conexao(u)
        try:
            _rodar([_ferramenta("pg_dump"), "--format=custom", "--no-owner", "--file", str(arq), *args, u.database or "postgres"], env)
        except ErroBackup:
            arq.unlink(missing_ok=True)
            raise
    else:
        raise ErroBackup(f"Banco não suportado para backup: {u.get_backend_name()}")
    resultado = ResultadoBackup(arq, arq.stat().st_size, _sha256(arq))
    arq.with_name(arq.name + ".sha256").write_text(f"{resultado.sha256}  {arq.name}\n")
    _podar(destino, manter)
    return resultado


# --- Verificação -------------------------------------------------------------------------------------------
def _verificar_sha(arq: Path) -> None:
    soma = arq.with_name(arq.name + ".sha256")
    if soma.exists() and soma.read_text().split()[0] != _sha256(arq):
        raise ErroBackup("O arquivo não confere com o .sha256 guardado: foi alterado ou corrompido depois do backup.")


def verificar(arq: Path, restaurar_em: str | None = None) -> dict[str, int]:
    """Confere o backup e devolve o número de linhas das tabelas principais."""
    if not arq.exists():
        raise ErroBackup(f"Arquivo não encontrado: {arq}")
    _verificar_sha(arq)
    if arq.suffix == ".sqlite":
        con = sqlite3.connect(f"file:{arq.as_posix()}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ErroBackup("O arquivo de backup está corrompido (falhou na verificação de integridade).")
            existentes = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
            faltam = [t for t in TABELAS_ESSENCIAIS if t not in existentes]
            if faltam:
                raise ErroBackup(f"O backup não tem as tabelas: {', '.join(faltam)}")
            return {t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in TABELAS_ESSENCIAIS}  # noqa: S608
        except sqlite3.DatabaseError as erro:
            raise ErroBackup(f"O arquivo não é um banco SQLite válido: {erro}") from None
        finally:
            con.close()
    if arq.suffix == ".dump":
        listagem = _rodar([_ferramenta("pg_restore"), "--list", str(arq)])
        faltam = [t for t in TABELAS_ESSENCIAIS if f" {t} " not in listagem]
        if faltam:
            raise ErroBackup(f"O backup não tem as tabelas: {', '.join(faltam)}")
        return _restaurar_para_teste(arq, restaurar_em) if restaurar_em else {t: -1 for t in TABELAS_ESSENCIAIS}
    raise ErroBackup("Formato desconhecido (esperado .sqlite ou .dump)")


def _restaurar_para_teste(arq: Path, url_admin: str) -> dict[str, int]:
    """Restaura num banco temporário do mesmo servidor, conta as linhas e apaga o banco."""
    u = make_url(url_admin)
    args, env = _args_conexao(u)
    nome = f"tolaris_teste_restauracao_{secrets.token_hex(4)}"
    psql, restore = _ferramenta("psql"), _ferramenta("pg_restore")
    _rodar([psql, *args, "-d", u.database or "postgres", "-c", f'create database "{nome}"'], env)
    try:
        _rodar([restore, *args, "--no-owner", "-d", nome, str(arq)], env)
        return {
            t: int(_rodar([psql, *args, "-d", nome, "-tA", "-c", f"select count(*) from {t}"], env).strip())  # noqa: S608
            for t in TABELAS_ESSENCIAIS
        }
    finally:
        _rodar([psql, *args, "-d", u.database or "postgres", "-c", f'drop database if exists "{nome}"'], env)


def principal(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m tolaris_api.backup", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("criar", help="cria um backup do banco configurado")
    c.add_argument("--destino", type=Path, default=Path("backups"))
    c.add_argument("--manter", type=int, default=14, help="quantos backups manter na pasta (padrão: 14)")
    c.add_argument("--banco", help="URL do banco (padrão: TOLARIS_DATABASE_URL)")
    v = sub.add_parser("verificar", help="confere um arquivo de backup")
    v.add_argument("arquivo", type=Path)
    v.add_argument("--restaurar-em", help="PostgreSQL: URL de um banco do servidor onde criar e apagar um banco temporário para a restauração de teste")
    a = p.parse_args(argv)
    try:
        if a.comando == "criar":
            r = criar(a.banco or get_settings().database_url, a.destino, a.manter)
            print(f"Backup criado: {r.arquivo} ({r.bytes / 1024:.0f} KB, sha256 {r.sha256[:12]}…)")
            contagem = verificar(r.arquivo)
        else:
            contagem = verificar(a.arquivo, a.restaurar_em)
            print(f"Backup conferido: {a.arquivo}")
        if any(v >= 0 for v in contagem.values()):
            print("Linhas no backup: " + ", ".join(f"{k} {v}" for k, v in contagem.items()))
        return 0
    except ErroBackup as erro:
        print(f"ERRO: {erro}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
