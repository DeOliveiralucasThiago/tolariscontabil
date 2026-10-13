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

sys.stdout.reconfigure(encoding="utf-8")  # console do Windows em cp1252
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

# Recuperação de tributos: importa 13 meses de NF-e com itens (multipart) e confere o cálculo e o PDF
def nfe(n: int, data: str, itens: list[tuple]) -> bytes:
    chave = f"3526031122233300018155001{n:09d}1{n:08d}"[:43].ljust(43, "0") + "1"
    dets = "".join(
        f'<det nItem="{i}"><prod><cProd>{i}</cProd><xProd>{nome}</xProd><NCM>{ncm}</NCM>'
        f'{f"<CEST>{cest}</CEST>" if cest else ""}<CFOP>{cfop}</CFOP><vProd>{valor:.2f}</vProd></prod><imposto>'
        f"<ICMS><ICMSSN{csosn}><orig>0</orig><CSOSN>{csosn}</CSOSN></ICMSSN{csosn}></ICMS>"
        f"<PIS><PISOutr><CST>49</CST></PISOutr></PIS></imposto></det>"
        for i, (ncm, cfop, csosn, cest, valor, nome) in enumerate(itens, start=1))
    total = sum(i[4] for i in itens)
    return (f'<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{chave}">'
            f"<ide><mod>55</mod><dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>11222333000181</CNPJ></emit>"
            f"<dest><CNPJ>45997418000153</CNPJ></dest>{dets}<total><ICMSTot><vICMS>0.00</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS>"
            f"<vCOFINS>0.00</vCOFINS><vNF>{total:.2f}</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>{chave}</chNFe>"
            f"<cStat>100</cStat></infProt></protNFe></nfeProc>").encode()


def enviar_arquivos(caminho: str, arquivos: list[tuple[str, bytes]]) -> tuple[int, bytes]:
    limite = "----tolaris"
    corpo = b"".join(
        f'--{limite}\r\nContent-Disposition: form-data; name="arquivos"; filename="{nome}"\r\n'
        "Content-Type: application/xml\r\n\r\n".encode() + conteudo + b"\r\n" for nome, conteudo in arquivos
    ) + f"--{limite}--\r\n".encode()
    req = urllib.request.Request(BASE + caminho, data=corpo, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    try:
        with abrir(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


status, corpo = pedir("POST", "/api/clientes", {
    "razao_social": "Mercadinho Boa Compra Ltda", "cnpj": "11222333000181", "atividade": "comercio", "regime_atual": "simples"})
ok(status == 201, f"cliente com CNPJ ({status})")
cid2 = json.loads(corpo)["id"]
comum = ("19059090", "5102", "102", "", 100000.0, "BISCOITO")
refri = ("22021000", "5405", "500", "0300100", 10000.0, "REFRIGERANTE COLA 2L")
notas = []
for i in range(13):
    itens = [comum] if i < 12 else [refri, ("19059090", "5102", "102", "", 90000.0, "BISCOITO")]
    notas.append((f"n{i}.xml", nfe(i + 1, f"{2025 + i // 12}-{i % 12 + 1:02d}-10", itens)))
status, corpo = enviar_arquivos(f"/api/clientes/{cid2}/importacoes", notas)
ok(status == 201 and json.loads(corpo)["importados"] == 13, f"13 notas com itens importadas ({status})")
status, corpo = pedir("POST", f"/api/clientes/{cid2}/recuperacao", {})
ok(status == 201, f"análise de recuperação salva ({status})")
sim = json.loads(corpo)
ok(sim["resultado"]["totais"]["provavel"] == 432.43, "imposto pago a mais = R$ 432,43 (PIS/Cofins 136,79 + ICMS 295,64)")
status, pdf = pedir("GET", f"/api/simulacoes/{sim['id']}/proposta.pdf")
texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
ok(status == 200 and "Recuperação de tributos no Simples Nacional" in texto and "R$ 432,43" in texto, "PDF da recuperação com texto legível")

status, _ = pedir("POST", "/api/auth/esqueci-senha", {"email": "ana@teste.com.br"})
time.sleep(1)
emails = [json.loads(p.read_text(encoding="utf-8")) for p in (PASTA / "dados" / "emails").glob("*.json")]
ok(status == 202 and any(f"http://{ip}:3000/redefinir-senha" in m["texto"] for m in emails),
   "e-mail de redefinição salvo em dados/emails com o endereço da rede")
print("Tudo certo.")
