"""Baixa o texto das leis federais do Senado (normas.leg.br) e grava em ``legislação/`` (texto, metadados e índice).

Fontes (APIs abertas do Congresso):
  - Senado, dados abertos: ``legis.senado.leg.br/dadosabertos/legislacao/lista`` resolve tipo, número e ano na data da norma;
  - Portal Normas.leg.br: ``normas.leg.br/api/public/normas?urn=...&&tipo_documento=maior-detalhe`` lista as versões do texto, e
    ``normas.leg.br/api/public/binario/{id}/texto`` entrega o HTML do texto. Preferimos a **compilação vigente** (texto com todas as
    alterações); sem ela, a publicação original.
  - Portal de normas da Receita Federal (``--receita CGSN:Resol.:140:2018``): resoluções do CGSN, instruções normativas etc., na visão
    multivigente (texto com todas as alterações). A API é a mesma que o próprio site usa.
  - ``--pdf``: PDF oficial convertido em texto, para consolidações que as APIs não trazem (a LC 214 do Normas.leg.br é a publicação original; a
    consolidada com a LC 227 vem do PDF da Fazenda de Minas Gerais).
  - Câmara dos Deputados, dados abertos (opcional, ``--proposicao PLP:108:2021``): grava o PDF do texto mais recente da tramitação, útil para
    projetos que ainda não viraram lei.

Uso:
    python scripts/baixar_legislacao.py                       # baixa a lista padrão
    python scripts/baixar_legislacao.py LCP:123:2006 LEI:9249:1995
    python scripts/baixar_legislacao.py --proposicao PLP:108:2021

O texto de uma lei prevalece sobre qualquer resumo do Tolaris; confira a versão no Diário Oficial quando a decisão depender dela.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "legislação"
SENADO = "https://legis.senado.leg.br/dadosabertos/legislacao/lista"
NORMAS = "https://normas.leg.br/api/public/normas"
CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
RECEITA = "https://normas.receita.fazenda.gov.br/api"
RECEITA_TEXTO = "https://normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato"
PAUSA = 1.5
"""Segundos entre chamadas: os serviços públicos devolvem 503 quando recebem rajadas."""

PADRAO_RECEITA = [
    # Simples Nacional (CGSN): 140/2018 consolida o regulamento; as demais alteram para 2027 em diante
    "CGSN:Resol.:140:2018", "CGSN:Resol.:186:2026", "CGSN:Resol.:190:2026", "CGSN:Resol.:191:2026", "CGSN:Resol.:194:2026", "CGSN:Resol.:195:2026",
    # Lucro Presumido e Real
    "RFB:IN:1700:2017", "RFB:IN:2110:2022",
]
PADRAO = [
    # Simples Nacional e Reforma Tributária
    "LCP:123:2006", "LCP:214:2025", "LCP:227:2026", "LCP:238:2026", "LCP:224:2025", "EMC:132:2023",
    # Impostos sobre consumo (ISS, ICMS) e ISS fixo
    "LCP:116:2003", "LCP:87:1996", "DEL:406:1968",
    # Imposto de renda, CSLL, PIS/Cofins e previdência
    "LEI:9249:1995", "LEI:9430:1996", "LEI:7689:1988", "LEI:9715:1998", "LEI:9718:1998", "LEI:10637:2002", "LEI:10833:2003",
    "LEI:8212:1991", "LEI:15270:2025",
]
TIPO_URN = {
    "LCP": "lei.complementar",
    "LEI": "lei",
    "DEL": "decreto.lei",
    "DEC": "decreto",
    "EMC": "emenda.constitucional",
    "MPV": "medida.provisoria",
}


class Texto(HTMLParser):
    """HTML do Normas.leg.br em texto puro: um parágrafo por linha, sem os metadados do Word que vêm no começo."""

    BLOCOS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "blockquote"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "title"):
            self.ignorar += 1
        elif tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "title"):
            self.ignorar = max(0, self.ignorar - 1)
        elif tag in self.BLOCOS:
            self.partes.append("\n")

    def handle_data(self, data):
        if not self.ignorar:
            self.partes.append(data)

    def texto(self) -> str:
        bruto = "".join(self.partes)
        linhas = [re.sub(r"[ \t ]+", " ", l).strip() for l in bruto.splitlines()]
        return "\n".join(l for l in linhas if l)


def _html_para_texto(html: str) -> str:
    parser = Texto()
    parser.feed(html)
    return parser.texto()


def pegar(url: str, tentativas: int = 5) -> bytes:
    """GET com espera crescente: o Senado alterna respostas 503 mesmo com poucas chamadas."""
    espera = 3.0
    for n in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json, text/html, */*", "User-Agent": "tolaris-legislacao/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                dados = r.read()
            time.sleep(PAUSA)
            return dados
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or n == tentativas:
                raise
        except (urllib.error.URLError, http.client.IncompleteRead, ConnectionError, TimeoutError):
            if n == tentativas:
                raise
        time.sleep(espera)
        espera *= 2
    raise RuntimeError("inalcançável")


def resolver(tipo: str, numero: int, ano: int) -> dict:
    """Dados da norma no Senado (id, nome, data da assinatura) e a URN do Normas.leg.br."""
    consulta = urllib.parse.urlencode({"tipo": tipo, "numero": numero, "ano": ano})
    lista = json.loads(pegar(f"{SENADO}?{consulta}"))
    docs = lista["ListaDocumento"]["documentos"]["documento"]
    doc = docs[0] if isinstance(docs, list) else docs
    dia, mes, ano_ass = doc["dataassinatura"].split("/")
    return {
        "id_senado": doc["id"],
        "nome": doc["normaNome"],
        "ementa": doc["ementa"],
        "assinatura": f"{ano_ass}-{mes}-{dia}",
        "urn": f"urn:lex:br:federal:{TIPO_URN[tipo]}:{ano_ass}-{mes}-{dia};{numero}",
    }


def escolher_versao(metadados: dict) -> dict | None:
    """Compilação vigente se houver (texto com todas as alterações); senão a publicação original. ``None`` se não há texto em arquivo."""
    versoes = metadados.get("encoding") or []
    if isinstance(versoes, dict):
        versoes = [versoes]
    for v in versoes:
        if v.get("version") == "Current" and v.get("contentUrl"):
            return v
    for v in versoes:
        if v.get("additionalType") == "PublicacaoOriginal" and v.get("contentUrl"):
            return v
    return next((v for v in versoes if v.get("contentUrl")), None)


def nome_da_versao(v: dict) -> str:
    """Rótulo legível da versão do texto (o campo ``additionalType`` nem sempre vem preenchido)."""
    tipo = v.get("additionalType")
    if tipo:
        return str(tipo)
    nome = str(v.get("name") or "")
    return nome.split("[")[0].strip() or str(v.get("version") or "texto")


def texto_da_arvore(no: dict, linhas: list[str] | None = None) -> list[str]:
    """Texto de uma norma pela árvore de dispositivos (quando o portal não traz o arquivo do texto): um dispositivo por linha."""
    linhas = [] if linhas is None else linhas
    exemplo = no.get("workExample") or {}
    nome = str(exemplo.get("name") or "").strip()
    corpo = _html_para_texto(str(exemplo.get("text") or ""))
    if nome or corpo:
        linhas.append(f"{nome} {corpo}".strip())
    filhos = no.get("hasPart") or []
    for filho in [filhos] if isinstance(filhos, dict) else filhos:
        texto_da_arvore(filho, linhas)
    return linhas


def baixar_norma(codigo: str) -> dict:
    tipo, numero, ano = codigo.split(":")
    info = resolver(tipo.upper(), int(numero), int(ano))
    meta = json.loads(pegar(f"{NORMAS}?urn={urllib.parse.quote(info['urn'], safe=':;')}&&tipo_documento=maior-detalhe"))
    versao = escolher_versao(meta)
    if versao:
        url = versao["contentUrl"].replace("/api/binario/", "/api/public/binario/")
        texto = _html_para_texto(pegar(url).decode("utf-8", errors="replace"))
        rotulo = nome_da_versao(versao)
    else:
        url = f"{NORMAS}?urn={urllib.parse.quote(info['urn'], safe=':;')}&&tipo_documento=maior-detalhe"
        texto = "\n".join(texto_da_arvore(meta.get("hasPart") or {}))
        rotulo = "árvore de dispositivos (versão original)"
        if not texto:
            raise RuntimeError("a norma não traz nenhuma versão do texto")
    # o Word grava metadados (autor, datas, contadores) antes do título; o texto da lei começa na primeira linha com o nome da norma
    ini = re.search(r"^(LEI|EMENDA|DECRETO|CONSTITUI)[^\n]*\n", texto, flags=re.M | re.I)
    if ini and ini.start() < 2000:
        texto = texto[ini.start():]
    arquivo = f"{tipo.upper()}-{int(numero):03d}-{ano}.txt" if int(numero) < 1000 else f"{tipo.upper()}-{numero}-{ano}.txt"
    cabecalho = (
        f"{info['nome']}\n"
        f"Fonte: Normas.leg.br (Senado Federal), versão \"{rotulo}\"\n"
        f"Endereço: {url}\n"
        f"Baixado em: {date.today().isoformat()}\n"
        f"{'=' * 78}\n\n"
    )
    (PASTA / arquivo).write_text(cabecalho + texto + "\n", encoding="utf-8")
    return {
        "arquivo": arquivo,
        "norma": info["nome"],
        "urn": info["urn"],
        "versao": rotulo,
        "ementa": info["ementa"],
        "url": url,
        "baixado_em": date.today().isoformat(),
        "caracteres": len(texto),
    }


def _post_json(url: str, corpo: dict, tentativas: int = 4) -> dict:
    espera = 3.0
    for n in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(corpo).encode(), method="POST",
                headers={"Content-Type": "application/json; charset=UTF-8", "User-Agent": "tolaris-legislacao/1.0"},
            )
            with urllib.request.urlopen(req, timeout=90) as r:
                dados = json.loads(r.read())
            time.sleep(PAUSA)
            return dados
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or n == tentativas:
                raise
        time.sleep(espera)
        espera *= 2
    raise RuntimeError("inalcançável")


def baixar_receita(codigo: str) -> dict:
    """Ato do portal de normas da Receita (órgão:tipo:número:ano), texto multivigente (com as alterações em vigor)."""
    orgao, tipo, numero, ano = codigo.split(":")
    tipos = json.loads(pegar(f"{RECEITA}/tipoAto/ativo"))
    achado = next((t for t in tipos if t["siglaTipoAto"].lower() == tipo.lower()), None)
    if not achado:
        raise RuntimeError(f"tipo de ato desconhecido: {tipo}")
    resposta = _post_json(f"{RECEITA}/indexacao/ato/pesquisar", {
        "termoBusca": "", "numeroAto": numero, "orgaosSelecionados": orgao, "tiposAtosSelecionados": str(achado["idTipoAto"]),
        "paginacaoPaginaAtual": 1, "paginacaoQuantidadePorPagina": 30, "tipoData": "dataPublicacao", "internet": True,
    })
    atos = [a for a in resposta.get("atos", []) if a["anoAto"] == ano and a["numeroAto"] == numero]
    if not atos:
        raise RuntimeError(f"{codigo} não encontrado no portal de normas da Receita")
    # retificações e erratas têm o mesmo número: o ato principal é o de ementa mais longa
    ato = max(atos, key=lambda a: len(unescape(a.get("ementa") or "")))
    url = f"{RECEITA_TEXTO}/{ato['idAto']}/visao/multivigente"
    dados = json.loads(pegar(url))
    segmentos = [s for s in (dados.get("ementas") or []) + (dados.get("outrosSegmentos") or []) if s.get("compilado") and not s.get("tachado") and not s.get("omitir")]
    segmentos.sort(key=lambda s: int(s.get("ordemSegmentoAto") or 0))
    linhas = [dados.get("epigrafeCompleta", ""), dados.get("dadosPublicacao", "")]
    for s in segmentos:
        corpo = _html_para_texto(s.get("textoIntegra") or "")
        notas = " ".join(a.get("texto", "") for a in (s.get("ancorasDestino") or []) if a.get("texto"))
        if corpo:
            linhas.append(f"{corpo} {notas}".strip())
    texto = "\n".join(l for l in linhas if l)
    nome = dados.get("epigrafeCompleta") or f"{tipo} {orgao} {numero}/{ano}"
    sigla = re.sub(r"[^A-Za-z0-9]", "", tipo).upper()
    arquivo = f"{orgao.upper()}-{sigla}-{int(numero):04d}-{ano}.txt"
    cabecalho = (
        f"{nome}\n"
        f"Fonte: portal de normas da Receita Federal, visão multivigente (texto com as alterações em vigor; trechos revogados e anexos em PDF ficam de fora)\n"
        f"Endereço: {url}\n"
        f"Baixado em: {date.today().isoformat()}\n"
        f"{'=' * 78}\n\n"
    )
    (PASTA / arquivo).write_text(cabecalho + texto + "\n", encoding="utf-8")
    return {
        "arquivo": arquivo,
        "norma": nome,
        "urn": "",
        "versao": "multivigente (Receita Federal)",
        "ementa": unescape(ato.get("ementa") or ""),
        "url": url,
        "baixado_em": date.today().isoformat(),
        "caracteres": len(texto),
    }


def baixar_pdf(spec: str) -> dict:
    """PDF de um órgão oficial convertido em texto (``pdftotext``): ``ARQUIVO=URL``. Para consolidações que as APIs não trazem."""
    import shutil
    import subprocess
    import tempfile

    nome, _, url = spec.partition("=")
    if not nome or not url:
        raise RuntimeError("use ARQUIVO=URL")
    if not shutil.which("pdftotext"):
        raise RuntimeError("pdftotext não está instalado (pacote poppler-utils)")
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "norma.pdf"
        pdf.write_bytes(pegar(url))
        txt = Path(tmp) / "norma.txt"
        subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
        texto = txt.read_text(encoding="utf-8", errors="replace")
    arquivo = nome if nome.endswith(".txt") else f"{nome}.txt"
    cabecalho = f"Fonte: {url}\nBaixado em: {date.today().isoformat()}\nTexto extraído de PDF oficial (pdftotext -layout)\n{'=' * 78}\n\n"
    (PASTA / arquivo).write_text(cabecalho + texto, encoding="utf-8")
    return {
        "arquivo": arquivo, "norma": nome, "urn": "", "versao": "PDF oficial convertido em texto", "ementa": "",
        "url": url, "baixado_em": date.today().isoformat(), "caracteres": len(texto),
    }


def baixar_proposicao(codigo: str) -> dict:
    """PDF do texto mais recente de um projeto na Câmara (projetos ainda em tramitação ou recém-aprovados)."""
    tipo, numero, ano = codigo.split(":")
    achados = json.loads(pegar(f"{CAMARA}/proposicoes?siglaTipo={tipo.upper()}&numero={numero}&ano={ano}"))["dados"]
    if not achados:
        raise RuntimeError(f"{codigo} não encontrado na Câmara")
    prop = achados[0]
    detalhe = json.loads(pegar(f"{CAMARA}/proposicoes/{prop['id']}"))["dados"]
    url = detalhe.get("urlInteiroTeor")
    if not url:
        raise RuntimeError(f"{codigo} sem inteiro teor")
    arquivo = f"{tipo.upper()}-{numero}-{ano}-camara.pdf"
    (PASTA / arquivo).write_bytes(pegar(url))
    return {
        "arquivo": arquivo,
        "norma": f"{tipo.upper()} {numero}/{ano} (Câmara dos Deputados)",
        "urn": "",
        "versao": f"inteiro teor, situação: {detalhe.get('statusProposicao', {}).get('descricaoSituacao', '')}",
        "ementa": detalhe.get("ementa", ""),
        "url": url,
        "baixado_em": date.today().isoformat(),
        "caracteres": 0,
    }


def gravar_indice(novos: list[dict]) -> None:
    caminho = PASTA / "indice.json"
    atuais = {i["arquivo"]: i for i in json.loads(caminho.read_text(encoding="utf-8"))} if caminho.exists() else {}
    atuais.update({i["arquivo"]: i for i in novos})
    itens = sorted(atuais.values(), key=lambda i: i["arquivo"])
    caminho.write_text(json.dumps(itens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    linhas = [
        "# Legislação (texto baixado das APIs do Congresso)",
        "",
        "Gerado por `python scripts/baixar_legislacao.py`. O texto de uma lei prevalece sobre qualquer resumo do Tolaris; confira a versão no",
        "Diário Oficial quando a decisão depender dela. Para acrescentar uma norma: `python scripts/baixar_legislacao.py LEI:9249:1995`.",
        "",
        "| Arquivo | Norma | Versão do texto | Baixado em |",
        "|---|---|---|---|",
    ]
    linhas += [f"| `{i['arquivo']}` | {i['norma']} | {i['versao']} | {i['baixado_em']} |" for i in itens]
    (PASTA / "LEIA-ME.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("normas", nargs="*", help="TIPO:NÚMERO:ANO (LCP, LEI, DEL, DEC, EMC, MPV); sem argumentos, a lista padrão")
    ap.add_argument("--receita", action="append", default=[], help="ÓRGÃO:TIPO:NÚMERO:ANO de um ato da Receita (ex.: CGSN:Resol.:140:2018)")
    ap.add_argument("--pdf", action="append", default=[], help="ARQUIVO=URL de um PDF oficial a converter em texto (consolidações fora das APIs)")
    ap.add_argument("--proposicao", action="append", default=[], help="TIPO:NÚMERO:ANO de um projeto da Câmara (ex.: PLP:108:2021)")
    args = ap.parse_args()
    PASTA.mkdir(exist_ok=True)
    padrao = not (args.normas or args.proposicao or args.receita or args.pdf)
    alvos = args.normas or (PADRAO if padrao else [])
    receita = args.receita or (PADRAO_RECEITA if padrao else [])
    feitos: list[dict] = []
    falhas: list[str] = []
    for codigo in alvos:
        try:
            item = baixar_norma(codigo)
            tamanho = f"{item['caracteres']:,}".replace(",", ".")
            print(f"ok  {codigo:<16} {item['norma']} ({item['versao']}, {tamanho} caracteres)")
            feitos.append(item)
        except Exception as e:  # noqa: BLE001 - segue para a próxima norma e resume no fim
            falhas.append(codigo)
            print(f"ERRO {codigo}: {e}", file=sys.stderr)
    for codigo in receita:
        try:
            item = baixar_receita(codigo)
            tamanho = f"{item['caracteres']:,}".replace(",", ".")
            print(f"ok  {codigo:<22} {item['norma']} ({item['versao']}, {tamanho} caracteres)")
            feitos.append(item)
        except Exception as e:  # noqa: BLE001
            falhas.append(codigo)
            print(f"ERRO {codigo}: {e}", file=sys.stderr)
    for spec in args.pdf:
        try:
            item = baixar_pdf(spec)
            print(f"ok  {item['arquivo']} ({item['caracteres']:,} caracteres)".replace(",", "."))
            feitos.append(item)
        except Exception as e:  # noqa: BLE001
            falhas.append(spec)
            print(f"ERRO {spec}: {e}", file=sys.stderr)
    for codigo in args.proposicao:
        try:
            item = baixar_proposicao(codigo)
            print(f"ok  {codigo:<16} {item['norma']}")
            feitos.append(item)
        except Exception as e:  # noqa: BLE001
            falhas.append(codigo)
            print(f"ERRO {codigo}: {e}", file=sys.stderr)
    if feitos:
        gravar_indice(feitos)
    if falhas:
        print("Falharam:", ", ".join(falhas), file=sys.stderr)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
