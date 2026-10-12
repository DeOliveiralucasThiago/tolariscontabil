"""Teste de fumaça da pasta portátil já em execução (usado no CI do Windows).

Uso: python portatil/testar_portatil.py <pasta Tolaris>
Precisa de pypdf. Percorre: site no ar, cadastro, cliente, planejamento, PDF com texto,
acesso pelo IP da rede e e-mail de "esqueci a senha" salvo em dados/emails.
"""

from __future__ import annotations

import http.cookiejar
import io
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from pypdf import PdfReader

PASTA = Path(sys.argv[1])
BASE = "http://127.0.0.1:3000"
jar = http.cookiejar.CookieJar()
abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.ProxyHandler({})).open


def pedir(metodo: str, caminho: str, corpo: dict | None = None, base: str = BASE) -> tuple[int, bytes]:
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(base + caminho, data=dados, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with abrir(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def ok(cond: bool, msg: str) -> None:
    if not cond:
        print("FALHOU:", msg)
        for reg in (PASTA / "dados" / "registros").glob("*.log"):
            print(f"\n--- {reg.name} ---\n" + reg.read_text(encoding="utf-8", errors="replace")[-4000:])
        sys.exit(1)
    print("✓", msg)


limite = time.monotonic() + 240
while time.monotonic() < limite:
    try:
        if pedir("GET", "/login")[0] == 200:
            break
    except OSError:
        pass
    time.sleep(2)
else:
    ok(False, "site não respondeu em 4 minutos")
ok(True, "site no ar")

status, _ = pedir("POST", "/api/auth/cadastro", {
    "escritorio_nome": "Escritório Teste", "nome": "Ana", "email": "ana@teste.com.br", "senha": "senha-segura-123"})
ok(status == 201, f"cadastro ({status})")

status, corpo = pedir("POST", "/api/clientes", {"razao_social": "Comércio São João Ltda", "atividade": "comercio"})
ok(status == 201, f"cliente ({status})")
cid = json.loads(corpo)["id"]

status, corpo = pedir("POST", f"/api/clientes/{cid}/simulacoes/completa", {
    "atividade": "comercio", "receita_bruta_anual": 2000000, "folha_clt_anual": 240000,
    "pro_labore_anual": 36000, "compras_anual": 1200000, "despesas_creditaveis_anual": 80000})
ok(status == 201, f"planejamento completo ({status})")
sid = json.loads(corpo)["id"]

status, pdf = pedir("GET", f"/api/simulacoes/{sid}/proposta.pdf")
ok(status == 200 and pdf.startswith(b"%PDF"), f"PDF gerado ({len(pdf) // 1024} KB)")
texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
print(texto[:600])
ok("Comércio São João Ltda" in texto and "Simples Nacional" in texto, "PDF com texto e acentos legíveis")

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.connect(("10.255.255.255", 1))
    ip = s.getsockname()[0]
status, _ = pedir("GET", "/login", base=f"http://{ip}:3000")
ok(status == 200, f"acesso pela rede em http://{ip}:3000")

status, _ = pedir("POST", "/api/auth/esqueci-senha", {"email": "ana@teste.com.br"})
time.sleep(1)
emails = [json.loads(p.read_text(encoding="utf-8")) for p in (PASTA / "dados" / "emails").glob("*.json")]
ok(status == 202 and any(f"http://{ip}:3000/redefinir-senha" in m["texto"] for m in emails),
   "e-mail de redefinição salvo em dados/emails com o endereço da rede")
print("Tudo certo.")
