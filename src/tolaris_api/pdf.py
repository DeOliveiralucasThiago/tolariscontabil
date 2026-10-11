"""Proposta/diagnóstico em PDF com a identidade do escritório (Jinja2 + WeasyPrint)."""

from __future__ import annotations

import base64
from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from tolaris_motor import brl, pct

from .cnpj import formatar_cnpj
from .models import Cliente, Escritorio, Simulacao, Usuario
from .servicos import ROTULOS_ATIVIDADE

NEUTRO = "#B8C2CC"
TINTA = "#1D2733"
TINTA_SECUNDARIA = "#5B6775"

_env = Environment(loader=PackageLoader("tolaris_api", "templates"), autoescape=select_autoescape(["html"]))
_env.filters["brl"] = brl
_env.filters["pct"] = lambda v, casas=2: pct(v, casas) if v is not None else "—"
_env.filters["cnpj"] = lambda v: formatar_cnpj(v) if v else "—"


def _css_string(valor: str) -> Markup:
    """Texto como string CSS (para ``content:`` do rodapé), sem permitir fechar o <style>."""
    trocas = {"\\": "\\5C ", '"': "\\22 ", "<": "\\3C ", ">": "\\3E ", "\n": " ", "\r": " "}
    return Markup('"' + "".join(trocas.get(ch, ch) for ch in str(valor)) + '"')


_env.filters["css"] = _css_string


def _fetcher_somente_data():
    """O PDF só pode usar recursos embutidos (data:); nunca busca URLs na rede (evita SSRF)."""
    from weasyprint import URLFetcher

    return URLFetcher(allowed_protocols={"data"})


def _luminancia(hex_cor: str) -> float:
    canais = [int(hex_cor[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def cor_texto_sobre(hex_cor: str) -> str:
    """Branco ou tinta escura, o que tiver mais contraste sobre a cor da marca."""
    lum = _luminancia(hex_cor)
    return "#FFFFFF" if (1.05 / (lum + 0.05)) >= ((lum + 0.05) / 0.05) else TINTA


def grafico_barras(regimes: list[dict[str, Any]], melhor: str, cor: str) -> Markup:
    """Barras horizontais do total anual por regime; o recomendado na cor do escritório."""
    largura, rotulo_w, valor_w = 620, 150, 150
    barra_h, passo, topo = 22, 40, 8
    area = largura - rotulo_w - valor_w
    aplicaveis = [r for r in regimes if r["aplicavel"]]
    maximo = max((r["total"] for r in aplicaveis), default=0) or 1
    altura = topo + passo * len(regimes)
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" font-family="Helvetica, Arial, sans-serif" role="img">',
        f'<line x1="{rotulo_w}" y1="0" x2="{rotulo_w}" y2="{altura}" stroke="#D5DBE1" stroke-width="1"/>',
    ]
    for i, r in enumerate(regimes):
        y = topo + i * passo
        meio = y + barra_h / 2 + 4
        destaque = r["titulo"] == melhor
        peso = "700" if destaque else "400"
        partes.append(
            f'<text x="{rotulo_w - 10}" y="{meio}" text-anchor="end" font-size="12" '
            f'font-weight="{peso}" fill="{TINTA}">{escape(r["titulo"])}</text>'
        )
        if not r["aplicavel"]:
            partes.append(
                f'<text x="{rotulo_w + 8}" y="{meio}" font-size="11" fill="{TINTA_SECUNDARIA}">não aplicável</text>'
            )
            continue
        w = max(4.0, area * r["total"] / maximo)
        # Ponta arredondada (4px) só na extremidade do dado; a base fica reta no eixo.
        partes.append(
            f'<path d="M{rotulo_w},{y} h{w - 4} a4,4 0 0 1 4,4 v{barra_h - 8} a4,4 0 0 1 -4,4 h{-(w - 4)} z" '
            f'fill="{cor if destaque else NEUTRO}"/>'
        )
        texto = brl(r["total"])
        if r.get("carga_efetiva") is not None:
            texto += f"  ({pct(r['carga_efetiva'], 1)})"
        partes.append(
            f'<text x="{rotulo_w + w + 8}" y="{meio}" font-size="12" font-weight="{peso}" '
            f'fill="{TINTA}">{escape(texto)}</text>'
        )
    partes.append("</svg>")
    return Markup("".join(partes))


def tabela_tributos(regimes: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    """Linhas = tributos (na ordem em que aparecem), colunas = regimes aplicáveis."""
    colunas = [r for r in regimes if r["aplicavel"]]
    nomes: list[str] = []
    for r in colunas:
        for t in r["tributos"]:
            if t["nome"] not in nomes:
                nomes.append(t["nome"])
    linhas = []
    for nome in nomes:
        valores = []
        for r in colunas:
            achado = next((t["valor"] for t in r["tributos"] if t["nome"] == nome), None)
            valores.append(achado)
        linhas.append({"nome": nome, "valores": valores})
    return [r["titulo"] for r in colunas], linhas


def _entradas_legiveis(sim: Simulacao) -> list[tuple[str, str]]:
    e = sim.entrada
    atividade = ROTULOS_ATIVIDADE.get(e.get("atividade", ""), e.get("atividade", ""))
    if sim.tipo == "expressa":
        return [
            ("Atividade", atividade),
            ("Faturamento mensal", brl(e["faturamento_mensal"])),
            ("Folha de salários mensal", brl(e["folha_mensal"])),
            ("Pró-labore mensal", brl(e.get("pro_labore_mensal", 0))),
            ("Ano-calendário", str(e.get("ano", ""))),
        ]
    rotulos = [
        ("receita_bruta_anual", "Receita bruta anual"),
        ("folha_clt_anual", "Folha CLT anual"),
        ("pro_labore_anual", "Pró-labore anual"),
        ("compras_anual", "Compras e insumos"),
        ("despesas_creditaveis_anual", "Despesas com crédito de PIS/Cofins"),
        ("outras_despesas_anual", "Outras despesas"),
    ]
    linhas = [("Atividade", atividade)]
    linhas += [(r, brl(e[c])) for c, r in rotulos if float(e.get(c) or 0)]
    if e.get("atividade") in ("comercio", "industria"):
        linhas.append(("ICMS", pct(e.get("aliquota_icms", 0))))
    else:
        linhas.append(("ISS", pct(e.get("aliquota_iss", 0))))
    linhas.append(("Ano-calendário", str(e.get("ano", ""))))
    return linhas


def montar_html(escritorio: Escritorio, cliente: Cliente, sim: Simulacao, usuario: Usuario) -> str:
    res = sim.resultado
    cor = escritorio.cor_primaria or "#1F3A5F"
    logo = None
    if escritorio.logo and escritorio.logo_mime:
        logo = f"data:{escritorio.logo_mime};base64,{base64.b64encode(escritorio.logo).decode()}"
    colunas, linhas = tabela_tributos(res["regimes"])
    data = sim.criado_em
    if data.tzinfo is not None:
        data = data.astimezone(ZoneInfo("America/Sao_Paulo"))
    return _env.get_template("proposta.html").render(
        escritorio=escritorio,
        cliente=cliente,
        sim=sim,
        res=res,
        cor=cor,
        cor_texto=cor_texto_sobre(cor),
        logo=logo,
        grafico=grafico_barras(res["regimes"], res["melhor"], cor),
        colunas=colunas,
        linhas=linhas,
        entradas=_entradas_legiveis(sim),
        atividade=ROTULOS_ATIVIDADE.get(cliente.atividade or "", None),
        responsavel=escritorio.contador_responsavel or usuario.nome,
        data=data.strftime("%d/%m/%Y"),
        gerado_em=datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M"),
    )


def gerar_proposta(escritorio: Escritorio, cliente: Cliente, sim: Simulacao, usuario: Usuario) -> bytes:
    from weasyprint import HTML  # import tardio: carrega Pango só quando gera PDF

    return HTML(string=montar_html(escritorio, cliente, sim, usuario), url_fetcher=_fetcher_somente_data()).write_pdf()
