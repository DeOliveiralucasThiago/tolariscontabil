"""Proposta/diagnóstico em PDF com a identidade do escritório (Jinja2 + WeasyPrint)."""

from __future__ import annotations

import base64
import re
import unicodedata
from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from tolaris_motor import brl, pct

from .cnpj import formatar_cnpj
from .honorarios import para_pdf
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


def _valor_passo(valor: float, descricao: str) -> str:
    """Taxas (alíquotas, fator R, percentuais) em %; o resto em reais."""
    if re.search(r"alíquota|fator r|percentua|fatia", descricao, re.IGNORECASE):
        return pct(valor, 4)
    return brl(valor)


_env.filters["valor_passo"] = _valor_passo


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


def grafico_barras(regimes: list[dict[str, Any]], melhor: str | set[str], cor: str) -> Markup:
    """Barras horizontais do total por item; o(s) destacado(s) na cor do escritório."""
    destaques = {melhor} if isinstance(melhor, str) else set(melhor)
    largura, rotulo_w, valor_w = 620, 190, 150
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
        destaque = r["titulo"] in destaques
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
            *([("Receita mensal do exterior", brl(e["receita_exterior_mensal"]))] if float(e.get("receita_exterior_mensal") or 0) else []),
            ("Ano-calendário", str(e.get("ano", ""))),
        ]
    rotulos = [
        ("receita_bruta_anual", "Receita bruta anual"),
        ("folha_clt_anual", "Folha CLT anual"),
        ("pro_labore_anual", "Pró-labore anual"),
        ("compras_anual", "Compras e insumos"),
        ("despesas_creditaveis_anual", "Despesas com crédito de PIS/Cofins"),
        ("outras_despesas_anual", "Outras despesas"),
        ("receita_exterior_anual", "Receita do exterior (exportação)"),
    ]
    linhas = [("Atividade", atividade)]
    linhas += [(r, brl(e[c])) for c, r in rotulos if float(e.get(c) or 0)]
    if float(e.get("variacao_cambial_anual") or 0):
        linhas.append(("Variação cambial líquida", brl(e["variacao_cambial_anual"])))
    if e.get("atividade") in ("comercio", "industria"):
        linhas.append(("ICMS", pct(e.get("aliquota_icms", 0))))
    else:
        linhas.append(("ISS", pct(e.get("aliquota_iss", 0))))
    linhas.append(("Ano-calendário", str(e.get("ano", ""))))
    return linhas


def _contexto(escritorio: Escritorio, cliente: Cliente, sim: Simulacao, usuario: Usuario | None) -> dict[str, Any]:
    cor = escritorio.cor_primaria or "#1F3A5F"
    logo = None
    if escritorio.logo and escritorio.logo_mime:
        logo = f"data:{escritorio.logo_mime};base64,{base64.b64encode(escritorio.logo).decode()}"
    data = sim.criado_em
    if data.tzinfo is not None:
        data = data.astimezone(ZoneInfo("America/Sao_Paulo"))
    return dict(
        escritorio=escritorio,
        cliente=cliente,
        sim=sim,
        res=sim.resultado,
        cor=cor,
        cor_texto=cor_texto_sobre(cor),
        logo=logo,
        atividade=ROTULOS_ATIVIDADE.get(cliente.atividade or "", None),
        honorarios=para_pdf(sim.honorarios, sim.resultado.get("economia_vs_pior"), sim.aceite_em, sim.aceite_nome)
        if sim.honorarios else None,
        responsavel=escritorio.contador_responsavel or (usuario.nome if usuario else escritorio.nome),
        data=data.strftime("%d/%m/%Y"),
        gerado_em=datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M"),
    )


def montar_html(escritorio: Escritorio, cliente: Cliente, sim: Simulacao, usuario: Usuario | None) -> str:
    ctx = _contexto(escritorio, cliente, sim, usuario)
    res = sim.resultado
    if sim.tipo in RELATORIOS:
        r = RELATORIOS[sim.tipo](sim, ctx["cor"])
        alertas = list(dict.fromkeys(r.pop("alertas")))
        return _env.get_template("relatorio.html").render(
            **ctx, r=r, alertas=alertas, entradas=r.pop("entradas"),
            titulo_doc=r["titulo"], subtitulo_doc=r["subtitulo"],
        )
    colunas, linhas = tabela_tributos(res["regimes"])
    return _env.get_template("proposta.html").render(
        **ctx,
        titulo_doc="Diagnóstico tributário",
        subtitulo_doc=f"Comparativo de regimes — ano-calendário {res['ano']}",
        grafico=grafico_barras(res["regimes"], res["melhor"], ctx["cor"]),
        colunas=colunas,
        linhas=linhas,
        entradas=_entradas_legiveis(sim),
    )


TITULOS = {
    "expressa": "Diagnóstico tributário",
    "completa": "Diagnóstico tributário",
    "reforma": "Impacto da Reforma Tributária",
    "simples_reforma": "Simples Nacional na Reforma",
    "autonomo": "Vale abrir CNPJ?",
    "pro_labore": "Pró-labore × distribuição de lucros",
    "enquadramento": "Enquadramento no Simples Nacional",
    "recuperacao": "Recuperação de tributos no Simples Nacional",
}


def titulo_documento(sim: Simulacao) -> str:
    return TITULOS.get(sim.tipo, "Relatório")


def nome_arquivo(sim: Simulacao) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo_documento(sim).lower()).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", sem_acento).strip("-")
    return f"{base or 'relatorio'}-{sim.id}.pdf"


def gerar_proposta(escritorio: Escritorio, cliente: Cliente, sim: Simulacao, usuario: Usuario | None = None) -> bytes:
    from weasyprint import HTML  # import tardio: carrega Pango só quando gera PDF

    return HTML(string=montar_html(escritorio, cliente, sim, usuario), url_fetcher=_fetcher_somente_data()).write_pdf()


# --- Relatórios da Fase 2 -------------------------------------------------------------
SERIE_1 = "#2A78D6"  # categórica 1 (tributos atuais)
SERIE_2 = "#EB6834"  # categórica 2 (IBS/CBS)


def grafico_colunas_empilhadas(colunas: list[dict[str, Any]], cores: list[str]) -> Markup:
    """Colunas por ano com segmentos empilhados (2px de respiro entre eles) e rótulo no topo."""
    largura, altura, base_y, topo = 620, 210, 186, 18
    n = len(colunas)
    passo = largura / n
    barra = min(44.0, passo * 0.6)
    maximo = max((sum(c["valores"]) for c in colunas), default=0) or 1
    escala = (base_y - topo) / maximo
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" '
        'font-family="Helvetica, Arial, sans-serif" role="img">',
        f'<line x1="0" y1="{base_y}" x2="{largura}" y2="{base_y}" stroke="#D5DBE1" stroke-width="1"/>',
    ]
    for i, c in enumerate(colunas):
        x = i * passo + (passo - barra) / 2
        y = base_y
        ultimo = max((j for j, v in enumerate(c["valores"]) if v > 0), default=-1)
        for j, v in enumerate(c["valores"]):
            if v <= 0:
                continue
            h = v * escala
            y -= h
            if j == ultimo and h > 4:
                d = (f"M{x},{y + h} v{-(h - 4)} a4,4 0 0 1 4,-4 h{barra - 8} a4,4 0 0 1 4,4 v{h - 4} z")
            else:
                d = f"M{x},{y + h} v{-h} h{barra} v{h} z"
            partes.append(f'<path d="{d}" fill="{cores[j]}"/>')
            y -= 2  # respiro entre segmentos
        partes.append(
            f'<text x="{x + barra / 2}" y="{y - 4}" text-anchor="middle" font-size="9" fill="{TINTA}">{escape(c["topo"])}</text>'
        )
        partes.append(
            f'<text x="{x + barra / 2}" y="{base_y + 15}" text-anchor="middle" font-size="10" fill="{TINTA_SECUNDARIA}">'
            f'{escape(str(c["rotulo"]))}</text>'
        )
    partes.append("</svg>")
    return Markup("".join(partes))


def _sim_nao(v: Any) -> str:
    return "Sim" if v else "Não"


def _rel_reforma(sim: Simulacao, cor: str) -> dict[str, Any]:
    res, e = sim.resultado, sim.entrada
    anos = res["anos"]
    a0, an = anos[0], anos[-1]
    variacao = res["variacao_total"]
    sentido = "aumento" if variacao > 0 else "redução"
    linhas = []
    for a in anos:
        t = {x["nome"]: x["valor"] for x in a["tributos"]}
        local = t.get("ICMS", 0) + t.get("ISS", 0)
        linhas.append({"valores": [
            str(a["ano"]), brl(t.get("PIS/Cofins", 0)), brl(t.get("IPI", 0)), brl(local),
            brl(t.get("CBS", 0)), brl(t.get("IBS", 0)), brl(a["total"]), pct(a["carga"]),
        ]})
    mostrar = {2025, 2027, 2029, 2033}
    return {
        "titulo": "Impacto da Reforma Tributária",
        "subtitulo": "Tributos sobre o consumo ano a ano (EC 132/2023 e LC 214/2025)",
        "destaque": {
            "rotulo": f"Carga sobre o consumo em {an['ano']}",
            "valor": pct(an["carga"]),
            "detalhe": f"Hoje ({a0['ano']}): {pct(a0['carga'])} — {sentido} de {brl(abs(variacao))} por ano.",
        },
        "cartoes": [
            {"rotulo": "Vendas sem tributos", "valor": brl(res["base_venda"])},
            {"rotulo": "Aquisições com crédito", "valor": brl(res["base_credito"])},
            {"rotulo": "CBS + IBS de referência", "valor": pct(res["cbs_referencia"] + res["ibs_referencia"], 1)},
        ],
        "grafico_titulo": "Tributos sobre o consumo por ano (R$)",
        "legenda": [("Tributos atuais (PIS/Cofins, IPI, ICMS/ISS)", SERIE_1), ("CBS + IBS", SERIE_2)],
        "grafico": grafico_colunas_empilhadas(
            [{"rotulo": a["ano"], "valores": [a["atuais"], a["novos"]], "topo": pct(a["carga"], 1)} for a in anos],
            [SERIE_1, SERIE_2],
        ),
        "grafico_nota": "No topo de cada coluna, a carga sobre o valor das vendas sem tributos. "
                        "Em 2026, CBS e IBS de teste são dispensados e não aparecem.",
        "tabelas": [{
            "titulo": "Detalhamento por tributo (R$/ano)",
            "colunas": ["Ano", "PIS/Cofins", "IPI", "ICMS/ISS", "CBS", "IBS", "Total", "Carga"],
            "linhas": linhas,
        }],
        "entradas": [
            ("Receita bruta anual", brl(e["receita_bruta_anual"])),
            ("Vende", "Mercadorias" if e["vende_mercadoria"] else "Serviços"),
            ("PIS/Cofins hoje", "Não cumulativo" if e.get("pis_cofins_nao_cumulativo") else "Cumulativo"),
            ("Compras com crédito", brl(e.get("compras_anual", 0))),
            ("Outras aquisições com crédito", brl(e.get("despesas_creditaveis_anual", 0))),
            ("ICMS" if e["vende_mercadoria"] else "ISS", pct(e["aliquota_icms"] if e["vende_mercadoria"] else e["aliquota_iss"])),
            ("IPI", pct(e.get("aliquota_ipi", 0))),
            ("Redução setorial", pct(e.get("reducao_setorial", 0), 0)),
        ],
        "alertas": res["alertas"] + [x for a in anos for x in a["alertas"]],
        "memorias": [{"titulo": f"{a['ano']} — total {brl(a['total'])}", "passos": a["memoria"]} for a in anos if a["ano"] in mostrar],
        "aviso_extra": "As alíquotas de referência de CBS e IBS são estimativas até a fixação oficial.",
    }


def _rel_simples_reforma(sim: Simulacao, cor: str) -> dict[str, Any]:
    res, e = sim.resultado, sim.entrada
    cen = res["cenarios"]
    final = cen[-1]
    barras, melhores = [], set()
    for c in cen:
        dentro = {"titulo": f"{c['ano']} — dentro do DAS", "total": c["dentro_do_das"], "aplicavel": True}
        fora = {"titulo": f"{c['ano']} — por fora", "total": c["por_fora"], "aplicavel": True}
        barras += [dentro, fora]
        melhores.add((fora if c["diferenca"] > 0 else dentro)["titulo"])
    return {
        "titulo": "Simples Nacional na Reforma",
        "subtitulo": "Recolher IBS/CBS dentro do DAS ou pelo regime regular (por fora)",
        "destaque": {
            "rotulo": f"Recomendação para {final['ano']}",
            "valor": final["recomendacao"],
            "detalhe": f"Diferença estimada de {brl(abs(final['diferenca']))} por ano na receita líquida de tributos.",
        },
        "cartoes": [
            {"rotulo": "Vendas a empresas (B2B)", "valor": pct(res["percentual_b2b"], 0)},
            {"rotulo": f"Por fora compensa ({final['ano']})", "valor": final["equilibrio_texto"]},
            {"rotulo": "Crédito ao cliente a cada R$ 100", "valor": f"{brl(final['credito_cliente_dentro'])} × {brl(final['credito_cliente_fora'])}"},
        ],
        "grafico_titulo": "Receita líquida de tributos por ano (R$)",
        "grafico": grafico_barras(barras, melhores, cor),
        "grafico_nota": "Destacada, a opção mais vantajosa em cada ano. Crédito ao cliente: dentro do DAS × por fora.",
        "tabelas": [{
            "titulo": "Comparativo",
            "colunas": ["Ano", "Dentro do DAS", "Por fora", "Diferença", "Por fora compensa", "Recomendação"],
            "linhas": [{"valores": [
                str(c["ano"]), brl(c["dentro_do_das"]), brl(c["por_fora"]), brl(c["diferenca"]),
                c["equilibrio_texto"], c["recomendacao"],
            ]} for c in cen],
        }],
        "entradas": [
            ("Atividade", ROTULOS_ATIVIDADE.get(e["atividade"], e["atividade"])),
            ("Receita bruta anual", brl(e["receita_bruta_anual"])),
            ("Vendas a empresas", pct(e["percentual_b2b"], 0)),
            ("Compras com crédito", brl(e.get("compras_creditaveis_anual", 0))),
            ("Redução setorial", pct(e.get("reducao_setorial", 0), 0)),
        ],
        "alertas": [x for c in cen for x in c["alertas"]],
        "memorias": [{"titulo": str(c["ano"]), "passos": c["memoria"]} for c in cen],
        "aviso_extra": "A partilha do DAS a partir de 2027 ainda será redefinida; os percentuais atuais são usados como aproximação.",
    }


def _rel_autonomo(sim: Simulacao, cor: str) -> dict[str, Any]:
    res, e = sim.resultado, sim.entrada
    aplicaveis = [o for o in res["opcoes"] if o["aplicavel"]]
    barras = [{"titulo": o["nome"], "total": o["liquido_mensal"], "aplicavel": o["aplicavel"]} for o in res["opcoes"]]
    ganho = res["ganho_vs_autonomo_anual"]
    return {
        "titulo": "Vale abrir CNPJ?",
        "subtitulo": "Autônomo × MEI × Simples Nacional × Lucro Presumido (valores mensais)",
        "destaque": {
            "rotulo": "Opção mais vantajosa",
            "valor": res["melhor"],
            "detalhe": (f"Ganho de {brl(ganho)} por ano em relação a atuar como autônomo." if ganho > 0
                        else "Atuar como autônomo é a opção mais vantajosa nestas condições."),
        },
        "cartoes": [
            {"rotulo": "Receita mensal", "valor": brl(res["receita_mensal"])},
            {"rotulo": "Despesas mensais", "valor": brl(e.get("despesas_mensais", 0))},
            {"rotulo": "Contabilidade (CNPJ)", "valor": brl(e.get("contabilidade_mensal", 0))},
        ],
        "grafico_titulo": "Quanto sobra por mês (R$)",
        "grafico": grafico_barras(barras, res["melhor"], cor),
        "grafico_nota": "Receita menos despesas, tributos e contabilidade.",
        "tabelas": [{
            "titulo": "Comparativo mensal",
            "colunas": ["Opção", "Tributos", "Contabilidade", "Sobra no mês", "Observação"],
            "linhas": [{"valores": [o["nome"], brl(o["tributos_mensais"]), brl(o["custos_mensais"]),
                                    brl(o["liquido_mensal"]), o["detalhe"] or "—"]} for o in aplicaveis],
        }],
        "entradas": [
            ("Atividade", ROTULOS_ATIVIDADE.get(e["atividade"], e["atividade"])),
            ("Receita mensal", brl(e["receita_mensal"])),
            ("Despesas mensais", brl(e.get("despesas_mensais", 0))),
            ("Dependentes", str(e.get("dependentes", 0))),
            ("ISS da empresa", pct(e.get("aliquota_iss", 0))),
            ("Pode ser MEI", _sim_nao(e.get("mei_permitido"))),
        ],
        "alertas": res["alertas"] + [x for o in res["opcoes"] for x in o["alertas"]],
        "memorias": [{"titulo": o["nome"], "passos": o["memoria"]} for o in aplicaveis],
        "aviso_extra": "Supõe receita constante e retirada do lucro como dividendos isentos.",
    }


def _rel_pro_labore(sim: Simulacao, cor: str) -> dict[str, Any]:
    res, e = sim.resultado, sim.entrada
    cen = res["cenarios"]
    curtos = ["100% pró-labore", "Pró-labore + dividendos"]
    barras = [{"titulo": t, "total": c["custo_mensal"], "aplicavel": True} for t, c in zip(curtos, cen)]
    mais_barata = curtos[0] if cen[0]["custo_mensal"] <= cen[1]["custo_mensal"] else curtos[1]
    regimes = {"simples": "Simples (anexos I, II, III e V)", "simples_anexo_iv": "Simples — Anexo IV",
               "presumido": "Lucro Presumido", "real": "Lucro Real"}
    return {
        "titulo": "Pró-labore × distribuição de lucros",
        "subtitulo": "Retirada mensal do sócio com as regras de 2026 (Lei 15.270/2025)",
        "destaque": {
            "rotulo": "Estratégia recomendada",
            "valor": res["melhor"],
            "detalhe": f"Economia de {brl(abs(res['economia_anual']))} por ano ({brl(abs(res['economia_mensal']))} por mês).",
        },
        "cartoes": [
            {"rotulo": "Retirada mensal", "valor": brl(e["retirada_mensal"])},
            {"rotulo": "Regime da empresa", "valor": regimes.get(res["regime"], res["regime"])},
            {"rotulo": "Economia anual", "valor": brl(abs(res["economia_anual"]))},
        ],
        "grafico_titulo": "Custo tributário mensal da retirada (R$)",
        "grafico": grafico_barras(barras, mais_barata, cor),
        "tabelas": [{
            "titulo": "Cenários",
            "colunas": ["Cenário", "Pró-labore", "Dividendos", "Custo tributário/mês", "Líquido ao sócio/mês"],
            "linhas": [{"valores": [c["descricao"], brl(c["pro_labore"]), brl(c["dividendos"]),
                                    brl(c["custo_mensal"]), brl(c["liquido_mensal"])]} for c in cen],
        }],
        "entradas": [
            ("Retirada mensal", brl(e["retirada_mensal"])),
            ("Regime da empresa", regimes.get(e.get("regime", ""), e.get("regime", ""))),
        ],
        "alertas": [x for c in cen for x in c["alertas"]],
        "memorias": [{"titulo": c["descricao"], "passos": c["memoria"]} for c in cen],
        "aviso_extra": "Custo tributário inclui INSS do sócio e da empresa, IRPF e retenção sobre dividendos.",
    }


_MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _mes_curto(competencia: str) -> str:
    return f"{_MESES_CURTOS[int(competencia[5:7]) - 1]}/{competencia[2:4]}"


def _rel_recuperacao(sim: Simulacao, cor: str) -> dict[str, Any]:
    res = sim.resultado
    tot, per = res["totais"], res["periodo"]
    com_valor = [m for m in res["meses"] if m["calculado"] and (m["provavel"] or m["a_verificar"])]
    ultimos = res["meses"][-12:]
    certeza = {"provavel": "Provável", "verificar": "Conferir"}
    anexo = {"I": "Anexo I (comércio)", "II": "Anexo II (indústria)"}.get(res["anexo"], res["anexo"])
    anual = res["economia_anual"]
    detalhe = (f"Economia estimada de {brl(anual)} por ano daqui para frente, se a receita desses produtos for "
               "segregada no PGDAS-D." if tot["provavel"] > 0 else "Nenhum produto monofásico ou com ICMS-ST foi identificado nas notas.")
    if tot["a_verificar"] > 0:
        detalhe += f" Mais {brl(tot['a_verificar'])} dependem de conferência do produto."
    return {
        "titulo": "Recuperação de tributos no Simples Nacional",
        "subtitulo": "Produtos com PIS/Cofins monofásico ou ICMS por substituição tributária",
        "destaque": {"rotulo": "Possível pagamento a mais no período analisado", "valor": brl(tot["provavel"]), "detalhe": detalhe},
        "cartoes": [
            {"rotulo": "PIS/Cofins (monofásico)", "valor": brl(tot["pis_cofins"])},
            {"rotulo": "ICMS (substituição tributária)", "valor": brl(tot["icms"])},
            {"rotulo": "A conferir", "valor": brl(tot["a_verificar"])},
        ],
        "grafico_titulo": "Pago a mais por mês (R$)",
        "legenda": [("PIS/Cofins", SERIE_1), ("ICMS", SERIE_2)],
        "grafico": grafico_colunas_empilhadas(
            [{"rotulo": _mes_curto(m["competencia"]), "valores": [m["pis_cofins"], m["icms"]],
              "topo": f"{m['provavel']:,.0f}".replace(",", ".")} for m in ultimos],
            [SERIE_1, SERIE_2],
        ) if any(m["provavel"] for m in ultimos) else None,
        "grafico_nota": "Últimos 12 meses importados. No topo de cada coluna, o total do mês em reais.",
        "tabelas": [
            {
                "titulo": "Meses com produtos identificados",
                "colunas": ["Mês", "Vendas do mês", "Base monofásica", "Base com ST", "Alíquota efetiva", "PIS/Cofins", "ICMS"],
                "linhas": [{"valores": [_mes_curto(m["competencia"]), brl(m["receita"]), brl(m["base_monofasico"]),
                                        brl(m["base_st"]), pct(m["aliquota_efetiva"], 2), brl(m["pis_cofins"]), brl(m["icms"])]}
                           for m in com_valor[-24:]],
            },
            {
                "titulo": "Produtos identificados",
                "colunas": ["NCM", "Produto", "Enquadramento", "Vendido (R$)", "Situação"],
                "esquerda": [1, 2, 4],
                "linhas": [{"valores": [p["ncm"] or "—", (p["descricao"] or "—")[:48],
                                        " · ".join(x for x in (p["monofasico"], p["st"]) if x),
                                        brl(p["valor"]), certeza[p["certeza"]]]} for p in res["produtos"][:15]],
            },
        ],
        "entradas": [
            ("Anexo do Simples Nacional", anexo),
            ("Período analisado", f"{_mes_curto(per['inicio'])} a {_mes_curto(per['fim'])} ({per['meses']} meses)"
             if per["inicio"] else "—"),
            ("Vendas de produtos monofásicos", brl(tot["base_monofasico"])),
            ("Vendas de produtos com ST", brl(tot["base_st"])),
        ],
        "alertas": res["alertas"],
        "memorias": [{"titulo": "Como o valor foi estimado", "passos": res["memoria"]}],
        "aviso_extra": "Os valores são indícios obtidos das notas fiscais e precisam ser conferidos com o PGDAS-D "
                       "de cada mês antes de qualquer retificação ou pedido de restituição.",
    }


def _rel_enquadramento(sim: Simulacao, cor: str) -> dict[str, Any]:
    res, e = sim.resultado, sim.entrada
    cen = res["cenarios"]
    atual = cen[0]
    def curto(c: dict[str, Any]) -> str:
        if c["chave"] == "atual":
            return "Hoje"
        return "Pró-labore até 28%" if c["chave"] == "fator_r" else f"{c['chave'].rsplit('_', 1)[1]}% no Anexo III"

    barras = [{"titulo": curto(c), "total": c["total_com_custo_extra"], "aplicavel": True} for c in cen]
    melhor_cen = next(c for c in cen if c["chave"] == res["recomendado"])
    mudou = melhor_cen["chave"] != "atual" and res["economia_vs_pior"] > 0
    return {
        "titulo": "Enquadramento no Simples Nacional",
        "subtitulo": "Caminhos para sair do Anexo V e o que cada um muda no imposto",
        "destaque": {
            "rotulo": "Caminho que mais reduz o imposto" if mudou else "Situação atual",
            "valor": melhor_cen["descricao"] if mudou else "Manter como está",
            "detalhe": (f"Economia estimada de {brl(res['economia_vs_pior'])} por ano em {melhor_cen['melhor_regime']}, "
                        "já com os custos extras." if mudou else "Nenhum caminho analisado reduz o imposto."),
        },
        "cartoes": [
            {"rotulo": "Receita anual", "valor": brl(res["receita_anual"])},
            {"rotulo": "Fator R hoje", "valor": pct(res["fator_r_atual"])},
            {"rotulo": "Imposto hoje (melhor regime)", "valor": brl(atual["total_com_custo_extra"])},
        ],
        "grafico_titulo": "Tributos por ano em cada caminho (R$)",
        "grafico": grafico_barras(barras, curto(melhor_cen), cor),
        "grafico_nota": "Destacado, o caminho de menor custo. Inclui o INSS do sócio sobre o pró-labore adicional.",
        "tabelas": [{
            "titulo": "Caminhos comparados",
            "colunas": ["Caminho", "Anexo(s)", "Simples", "Melhor regime", "Custo extra", "Total/ano", "Economia"],
            "linhas": [{"valores": [
                c["descricao"], " + ".join(c["anexos_simples"]) or "—",
                brl(c["simples"]["total"]) if c["simples"]["total"] is not None else "não se aplica",
                c["melhor_regime"], brl(c["custo_extra_anual"]) if c["custo_extra_anual"] else "—",
                brl(c["total_com_custo_extra"]), "—" if c["chave"] == "atual" else brl(c["economia_vs_atual"]),
            ]} for c in cen],
        }],
        "entradas": [
            ("Atividade", ROTULOS_ATIVIDADE.get(e["atividade"], e["atividade"])),
            ("Receita bruta anual", brl(e["receita_bruta_anual"])),
            ("Folha CLT anual", brl(e.get("folha_clt_anual", 0))),
            ("Pró-labore anual", brl(e.get("pro_labore_anual", 0))),
        ],
        "alertas": res["alertas"],
        "memorias": [],
        "aviso_extra": "Estimativa para discussão com o contador: cada caminho só vale se for real (pró-labore pago; atividade do "
                       "Anexo III exercida de fato, com CNAE no cadastro e nota do serviço).",
    }


RELATORIOS = {
    "recuperacao": _rel_recuperacao,
    "reforma": _rel_reforma,
    "simples_reforma": _rel_simples_reforma,
    "autonomo": _rel_autonomo,
    "pro_labore": _rel_pro_labore,
    "enquadramento": _rel_enquadramento,
}
