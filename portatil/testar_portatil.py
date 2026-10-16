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


def enviar_arquivos(caminho: str, arquivos: list[tuple[str, bytes]], campos: dict[str, str] | None = None,
                    anonimo: bool = False) -> tuple[int, bytes]:
    limite = "----tolaris"
    corpo = b"".join(
        f'--{limite}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n'.encode()
        for nome, valor in (campos or {}).items()
    ) + b"".join(
        f'--{limite}\r\nContent-Disposition: form-data; name="arquivos"; filename="{nome}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n".encode() + conteudo + b"\r\n" for nome, conteudo in arquivos
    ) + f"--{limite}--\r\n".encode()
    req = urllib.request.Request(BASE + caminho, data=corpo, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    abridor = urllib.request.build_opener(urllib.request.ProxyHandler({})).open if anonimo else abrir  # sem o cookie do escritório
    try:
        with abridor(req, timeout=120) as r:
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

# Honorários, leitura e aceite no portal
status, _ = pedir("PATCH", "/api/escritorio", {"honorarios": {
    "base": {"simples": 800, "presumido": 1500}, "por_funcionario": 70, "adesao": 500,
    "servicos": "Escrituração fiscal e contábil\nFolha de pagamento", "validade_dias": 15}})
ok(status == 200, f"tabela de honorários salva ({status})")
status, corpo = pedir("PUT", f"/api/simulacoes/{sid}/honorarios", {"funcionarios": 2})
ok(status == 200 and json.loads(corpo)["honorarios"]["valor_mensal"] == 940, "proposta sugerida pela tabela: R$ 800 + 2 x R$ 70 = R$ 940")
status, _ = pedir("PATCH", f"/api/simulacoes/{sid}/publicacao", {"publicada": True})
status, corpo = pedir("POST", f"/api/clientes/{cid}/portal", {})
token = json.loads(corpo)["link"].rsplit("/", 1)[1]
status, _ = pedir("POST", f"/api/portal/{token}/simulacoes/{sid}/visto")
ok(status == 204, f"leitura registrada pelo portal ({status})")
status, corpo = pedir("POST", f"/api/portal/{token}/simulacoes/{sid}/aceite", {"nome": "Maria Souza", "confirmo": True})
ok(status == 200 and json.loads(corpo)["aceite_nome"] == "Maria Souza", f"aceite eletrônico da proposta ({status})")
status, corpo = pedir("GET", f"/api/clientes/{cid}/simulacoes")
primeira = next(x for x in json.loads(corpo) if x["id"] == sid)
ok(primeira["aberturas"] >= 1 and primeira["aceite_em"], "escritório vê a leitura e o aceite")
status, pdf = pedir("GET", f"/api/simulacoes/{sid}/proposta.pdf")
texto = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
ok("Proposta de honorários" in texto and "R$ 940,00" in texto and "Aceite eletrônico" in texto, "PDF com a proposta e o aceite")

status, corpo = pedir("GET", "/api/avisos")
lista = json.loads(corpo)["avisos"]
ok(status == 200 and any(a["codigo"] == "recuperacao" and a["valor"] == 432.43 for a in lista),
   "central de avisos aponta a oportunidade de recuperação")
status, corpo = pedir("GET", "/api/mudancas")
ok(status == 200 and any(m["id"] == "irpf-lei-15270" for m in json.loads(corpo)), "mudanças na legislação carregadas")
status, corpo = pedir("POST", f"/api/simulacoes/{sim['id']}/recalcular")
ok(status == 201 and json.loads(corpo)["resultado"]["recalculo"]["de"] == sim["id"], "recálculo cria nova versão do relatório")

# Notas sem atrito: link de envio sem login, planilha de dados contábeis e caixa de e-mail
status, corpo = pedir("POST", f"/api/clientes/{cid2}/caixa", {})
ok(status == 201, f"link de envio de notas gerado ({status})")
token_envio = json.loads(corpo)["link"].rsplit("/", 1)[1]
nova = nfe(99, "2025-02-20", [("19059090", "5102", "102", "", 5000.0, "BISCOITO")])
status, corpo = enviar_arquivos(f"/api/caixa/{token_envio}/arquivos", [("nova.xml", nova), ("n0.xml", notas[0][1])], anonimo=True)
ok(status == 201 and json.loads(corpo)["importados"] == 1 and json.loads(corpo)["duplicados"] == 1,
   "cliente envia notas pelo link sem login (nova entra, repetida é ignorada)")
csv = ("Mês;Faturamento;Folha;Compras\n" + "\n".join(f"2025-{m:02d};10000,00;1500,00;6000,00" for m in range(1, 13))).encode("utf-8")
mapa = json.dumps({"competencia": 0, "receita": 1, "folha": 2, "compras": 3})
status, corpo = enviar_arquivos(f"/api/clientes/{cid2}/financeiro/importar", [("dados.csv", csv)], {"mapeamento": mapa})
ok(status == 201 and json.loads(corpo)["meses_novos"] == 12, f"planilha de dados contábeis importada ({status})")
status, corpo = pedir("GET", f"/api/clientes/{cid2}/financeiro")
plan = json.loads(corpo)["planejamento"]
ok(plan["receita_bruta_anual"] == 120000 and plan["folha_clt_anual"] == 18000 and not plan["anualizado"],
   "planejamento sugerido pela planilha: receita R$ 120.000 e folha R$ 18.000")
status, corpo = pedir("GET", f"/api/clientes/{cid2}/acompanhamento")
ac = json.loads(corpo)
ok(status == 200 and ac["disponivel"] and ac["projecao"]["meses_base"] >= 6 and ac["projecao"]["serie"][-1]["projetado"],
   "acompanhamento projeta o RBT12 do cliente a partir da receita realizada")
status, corpo = pedir("PUT", "/api/escritorio/caixa-email", {
    "host": "93.184.216.34", "usuario": "notas@escritorio.com.br", "senha": "segredo-da-caixa"})
ok(status == 200 and "segredo-da-caixa" not in corpo.decode() and json.loads(corpo)["configurada"],
   "caixa de e-mail salva (senha cifrada, não volta na resposta)")
status, _ = pedir("PUT", "/api/escritorio/caixa-email", {"host": "127.0.0.1", "usuario": "a@b.com", "senha": "x"})
ok(status == 400, "servidor IMAP em rede interna recusado")

# Importação de clientes em lote (sem a consulta de CNPJ: a rede pode estar bloqueada no CI)
csv_clientes = "CNPJ;Razão social;Atividade\n45.997.418/0001-53;Oficina Boa Roda Ltda;Serviços — Anexo III\n4252011000110;Empresa do Zero Ltda;Atividade que não existe\n".encode("utf-8")
status, corpo = enviar_arquivos("/api/clientes-lote/importar", [("clientes.csv", csv_clientes)], {"mapeamento": json.dumps({"cnpj": 0, "razao_social": 1, "atividade": 2})})
ok(status == 201 and json.loads(corpo)["criados"] == 2, f"clientes importados em lote ({status})")
status, corpo = pedir("GET", "/api/clientes-lote/pendentes")
ok(status == 200 and json.loads(corpo)["pendentes"] == 1, "cliente de atividade não reconhecida fica por completar")

status, _ = pedir("POST", "/api/auth/esqueci-senha", {"email": "ana@teste.com.br"})
time.sleep(1)
emails = [json.loads(p.read_text(encoding="utf-8")) for p in (PASTA / "dados" / "emails").glob("*.json")]
ok(status == 202 and any(f"http://{ip}:3000/redefinir-senha" in m["texto"] for m in emails),
   "e-mail de redefinição salvo em dados/emails com o endereço da rede")
print("Tudo certo.")
