"""Inicia o Tolaris portátil: API em 127.0.0.1:8000 e site em 0.0.0.0:3000 (rede local).

Estrutura esperada (montada por portatil/montar-windows.ps1):
    Tolaris/
      Iniciar Tolaris.bat     -> app/python/python.exe app/iniciar.py
      configuracao.txt        opcional: e-mail, porta, endereço
      app/iniciar.py          este arquivo
      app/python/             Python embutido com as dependências
      app/node/node.exe       Node.js
      app/web/                site (Next.js standalone)
      app/api/                alembic.ini e migrações
      app/gtk/                bibliotecas do PDF (Pango) e fontconfig
      dados/                  criado na primeira execução: banco, chave, e-mails, registros
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

APP = Path(__file__).resolve().parent
RAIZ = APP.parent
DADOS = RAIZ / "dados"
PORTA_API = 8000


def ip_local() -> str:
    """Endereço desta máquina na rede local (não envia nenhum pacote)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def porta_livre(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def ler_configuracao() -> dict[str, str]:
    """Linhas CHAVE=valor de configuracao.txt; # inicia comentário."""
    arq = RAIZ / "configuracao.txt"
    if not arq.exists():
        return {}
    try:
        texto = arq.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:  # Bloco de Notas salvando em ANSI
        texto = arq.read_text(encoding="cp1252")
    valores = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip()
    return valores


def chave_secreta() -> str:
    arq = DADOS / "chave.txt"
    if not arq.exists():
        arq.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return arq.read_text(encoding="utf-8").strip()


def aguardar(url: str, processo: subprocess.Popen, segundos: int = 90) -> bool:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if processo.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def ultimas_linhas(arq: Path, n: int = 25) -> str:
    try:
        return "\n".join(arq.read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def falhar(mensagem: str, registro: Path | None = None) -> None:
    print("\n*** " + mensagem)
    if registro:
        print(f"\nÚltimas linhas de {registro}:\n{ultimas_linhas(registro)}")
    print("\nSe precisar de ajuda, envie a pasta 'dados/registros'.")
    sys.exit(1)


def backup_do_dia(env: dict[str, str]) -> None:
    """Cópia do banco ao abrir o Tolaris, no máximo uma por dia (guarda as 14 últimas). Nunca impede de abrir."""
    pasta = DADOS / "backups"
    try:
        recentes = [a for a in pasta.glob("tolaris-*.sqlite") if time.time() - a.stat().st_mtime < 20 * 3600]
        if recentes or not (DADOS / "tolaris.db").exists():
            return
        r = subprocess.run(
            [sys.executable, "-m", "tolaris_api.backup", "criar", "--destino", str(pasta), "--manter", "14"],
            env=env, cwd=DADOS, capture_output=True, text=True, timeout=300,
        )
        print(" Backup do dia feito em dados\\backups." if r.returncode == 0 else " Aviso: o backup do dia não foi feito.")
    except Exception:  # noqa: BLE001
        print(" Aviso: o backup do dia não foi feito.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador (testes)")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")  # nunca derrubar por um caractere fora da página de código

    for pasta in (DADOS, DADOS / "registros", DADOS / "emails"):
        pasta.mkdir(parents=True, exist_ok=True)
    cfg = ler_configuracao()
    porta = int(cfg.pop("PORTA", "3000"))
    ip = ip_local()

    for p in (porta, PORTA_API):
        if not porta_livre(p):
            falhar(f"A porta {p} já está em uso. O Tolaris já está aberto em outra janela?")

    # Configuração da API: padrões do modo portátil, sobrescritos por configuracao.txt
    env = os.environ.copy()
    env.update({
        "TOLARIS_AMBIENTE": "producao",
        "TOLARIS_DATABASE_URL": "sqlite:///" + (DADOS / "tolaris.db").as_posix(),
        "TOLARIS_SECRET_KEY": chave_secreta(),
        "TOLARIS_COOKIE_SECURE": "false",
        "TOLARIS_PROXY_SALTOS": "1",  # a API só atende o site local, que repassa o IP real do aparelho
        "TOLARIS_URL_PUBLICA": f"http://{ip}:{porta}",
        # Sem servidor de e-mail configurado, as mensagens ficam salvas em dados/emails
        "TOLARIS_EMAIL_BACKEND": "arquivo",
        "TOLARIS_EMAIL_PASTA": str(DADOS / "emails"),
        "PYTHONUTF8": "1",
    })
    env.update({k if k.startswith("TOLARIS_") else f"TOLARIS_{k}": v for k, v in cfg.items()})

    gtk = APP / "gtk"
    if gtk.exists():  # bibliotecas do PDF no Windows
        env["WEASYPRINT_DLL_DIRECTORIES"] = str(gtk / "bin")
        env["FONTCONFIG_FILE"] = str(gtk / "etc" / "fonts" / "fonts.conf")
        env["FONTCONFIG_PATH"] = str(gtk / "etc" / "fonts")
        env["PATH"] = str(gtk / "bin") + os.pathsep + env.get("PATH", "")

    print("Iniciando o Tolaris Contábil...")
    reg_api = DADOS / "registros" / "api.log"
    reg_web = DADOS / "registros" / "site.log"

    migracao = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(APP / "api" / "alembic.ini"), "upgrade", "head"],
        env=env, cwd=DADOS, stdout=open(reg_api, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
    )
    if migracao.returncode != 0:
        falhar("Não foi possível preparar o banco de dados.", reg_api)

    backup_do_dia(env)

    processos: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "tolaris_api.main:app", "--host", "127.0.0.1", "--port", str(PORTA_API)],
            env=env, cwd=DADOS, stdout=open(reg_api, "a", encoding="utf-8"), stderr=subprocess.STDOUT,
        )
        processos.append(api)
        if not aguardar(f"http://127.0.0.1:{PORTA_API}/api/saude", api):
            falhar("O servidor de cálculo não iniciou.", reg_api)

        if not (APP / "web" / ".next" / "BUILD_ID").exists():
            falhar("A pasta app\\web\\.next está faltando. Baixe e descompacte o Tolaris portátil de novo.")
        # No Windows usa só o Node da pasta; fora dele (testes) aceita o do sistema
        node = shutil.which("node", path=str(APP / "node")) or (None if os.name == "nt" else shutil.which("node"))
        if not node:
            falhar("Node.js não encontrado em app/node.")
        web_env = {**env, "HOSTNAME": "0.0.0.0", "PORT": str(porta), "NODE_ENV": "production", "NEXT_TELEMETRY_DISABLED": "1"}
        web = subprocess.Popen(
            [node, "server.js"], env=web_env, cwd=APP / "web",
            stdout=open(reg_web, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
        )
        processos.append(web)
        if not aguardar(f"http://127.0.0.1:{porta}/login", web):
            falhar("O site não iniciou.", reg_web)

        local = f"http://localhost:{porta}"
        print()
        print("=" * 64)
        print(" Tolaris Contábil está funcionando.")
        print()
        print(f"   Neste computador:             {local}")
        print(f"   Outros aparelhos da rede:     http://{ip}:{porta}")
        print()
        print(" Mantenha esta janela aberta. Para desligar, feche a janela.")
        print(f" Seus dados ficam em: {DADOS}")
        if env["TOLARIS_EMAIL_BACKEND"] == "arquivo":
            print(" E-mail não configurado: as mensagens ficam em dados\\emails.")
        print("=" * 64)
        if not args.sem_navegador:
            webbrowser.open(local)

        while all(p.poll() is None for p in processos):
            time.sleep(1)
        falhar("O Tolaris parou inesperadamente.", reg_api if api.poll() is not None else reg_web)
    except KeyboardInterrupt:
        print("\nDesligando...")
    finally:
        for p in processos:
            if p.poll() is None:
                p.terminate()
        for p in processos:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
