"""Câmbio: taxa PTAX do Banco Central para converter receita em moeda estrangeira para reais.

A PTAX é a média das cotações que o Banco Central apura em quatro janelas por dia útil; o boletim de fechamento
é o último do dia. Para um dia sem cotação (fim de semana, feriado) vale o último dia útil anterior.
O contrato de câmbio fecha a taxa real da operação: a PTAX serve de referência e a tela deixa o contador trocar a taxa.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import httpx

from .config import get_settings

MOEDAS = {
    "USD": "Dólar dos EUA",
    "CAD": "Dólar canadense",
    "EUR": "Euro",
    "GBP": "Libra esterlina",
    "AUD": "Dólar australiano",
    "CHF": "Franco suíço",
    "JPY": "Iene",
    "DKK": "Coroa dinamarquesa",
    "NOK": "Coroa norueguesa",
    "SEK": "Coroa sueca",
}
"""Moedas mais comuns, com o nome em português. Servem de lista de reserva quando o Banco Central não responde
e de nome para as moedas que ele lista só em maiúsculas."""

VALIDADE_LISTA_SEGUNDOS = 24 * 3600
"""Por quanto tempo a lista de moedas do Banco Central fica guardada em memória."""

_CODIGO = re.compile(r"^[A-Z]{3}$")
_lista_guardada: tuple[float, dict[str, str]] | None = None

JANELA_DIAS = 10
"""Quantos dias para trás procurar uma cotação (cobre fins de semana e feriados prolongados)."""


class CambioIndisponivel(Exception):
    """Banco Central fora do ar ou resposta inesperada."""


class CotacaoNaoEncontrada(Exception):
    """Nenhuma cotação PTAX na janela consultada."""


@dataclass(frozen=True)
class Ptax:
    moeda: str
    data_solicitada: date
    data_cotacao: date
    compra: Decimal
    venda: Decimal
    boletim: str

    def como_dict(self) -> dict:
        return {
            "moeda": self.moeda,
            "nome": nome_da_moeda(self.moeda),
            "data_solicitada": self.data_solicitada.isoformat(),
            "data_cotacao": self.data_cotacao.isoformat(),
            "compra": float(self.compra),
            "venda": float(self.venda),
            "boletim": self.boletim,
            "dia_anterior": self.data_cotacao != self.data_solicitada,
        }


def nome_da_moeda(codigo: str) -> str:
    if codigo in MOEDAS:
        return MOEDAS[codigo]
    if _lista_guardada and codigo in _lista_guardada[1]:
        return _lista_guardada[1][codigo]
    return codigo


def listar_moedas(transport: httpx.BaseTransport | None = None) -> dict[str, str]:
    """Todas as moedas com PTAX segundo o Banco Central (serviço ``Moedas``), guardadas por um dia.

    Se o Banco Central não responder, devolve as moedas mais comuns; a tela segue funcionando e a taxa manual continua valendo.
    """
    global _lista_guardada
    agora = time.monotonic()
    if _lista_guardada and agora - _lista_guardada[0] < VALIDADE_LISTA_SEGUNDOS:
        return _lista_guardada[1]
    cfg = get_settings()
    try:
        with httpx.Client(timeout=cfg.cnpj_timeout_segundos, transport=transport) as cliente:
            resp = cliente.get(f"{cfg.ptax_url}/Moedas", params={"$format": "json"})
        resp.raise_for_status()
        registros = resp.json()["value"]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return dict(MOEDAS)
    achadas: dict[str, str] = {}
    for r in registros:
        try:
            codigo = str(r["simbolo"]).strip().upper()
        except (KeyError, TypeError):
            continue
        if codigo == "BRL" or not _CODIGO.match(codigo):
            continue
        nome = MOEDAS.get(codigo) or str(r.get("nomeFormatado") or "").strip().capitalize() or codigo
        achadas[codigo] = nome
    if not achadas:
        return dict(MOEDAS)
    # as comuns primeiro e na ordem de sempre; as demais em ordem alfabética do nome
    ordenadas = {c: achadas[c] for c in MOEDAS if c in achadas}
    ordenadas.update(sorted(((c, n) for c, n in achadas.items() if c not in ordenadas), key=lambda x: x[1]))
    _lista_guardada = (agora, ordenadas)
    return ordenadas


def escolher_cotacao(moeda: str, data: date, registros: list[dict]) -> Ptax:
    """Do conjunto devolvido pelo Banco Central, o boletim de fechamento do último dia útil até ``data``."""
    candidatos = []
    for r in registros:
        try:
            quando = datetime.fromisoformat(str(r["dataHoraCotacao"]).replace(" ", "T")[:19])
            compra, venda = Decimal(str(r["cotacaoCompra"])), Decimal(str(r["cotacaoVenda"]))
        except (KeyError, ValueError, ArithmeticError):
            continue
        if quando.date() <= data and compra > 0 and venda > 0:
            candidatos.append((quando, compra, venda, str(r.get("tipoBoletim") or "")))
    if not candidatos:
        raise CotacaoNaoEncontrada(f"Sem cotação PTAX de {moeda} até {data.isoformat()}")
    dia = max(c[0].date() for c in candidatos)
    do_dia = sorted((c for c in candidatos if c[0].date() == dia), key=lambda c: c[0])
    quando, compra, venda, boletim = do_dia[-1]  # o último boletim do dia é o de fechamento
    return Ptax(moeda, data, dia, compra, venda, boletim)


def consultar_ptax(moeda: str, data: date, transport: httpx.BaseTransport | None = None) -> Ptax:
    moeda = moeda.upper()
    if not _CODIGO.match(moeda):
        raise CotacaoNaoEncontrada(f"Moeda sem PTAX: {moeda}")
    cfg = get_settings()
    inicio = data - timedelta(days=JANELA_DIAS)
    url = f"{cfg.ptax_url}/CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    params = {
        "@moeda": f"'{moeda}'",
        "@dataInicial": f"'{inicio.strftime('%m-%d-%Y')}'",
        "@dataFinalCotacao": f"'{data.strftime('%m-%d-%Y')}'",
        "$top": "200",
        "$format": "json",
    }
    try:
        with httpx.Client(timeout=cfg.cnpj_timeout_segundos, transport=transport) as cliente:
            resp = cliente.get(url, params=params)
    except httpx.HTTPError as erro:
        raise CambioIndisponivel(str(erro)) from erro
    if resp.status_code >= 400:
        raise CambioIndisponivel(f"Banco Central respondeu {resp.status_code}")
    try:
        registros = resp.json()["value"]
    except (ValueError, KeyError, TypeError) as erro:
        raise CambioIndisponivel("Resposta inesperada do Banco Central") from erro
    return escolher_cotacao(moeda, data, registros)
