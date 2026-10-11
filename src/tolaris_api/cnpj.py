"""CNPJ: validação dos dígitos, consulta na BrasilAPI e sugestão de atividade pelo CNAE."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from tolaris_motor import Atividade

from .config import get_settings


def so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def dv(base: str, pesos: list[int]) -> str:
        resto = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if resto < 2 else str(11 - resto)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(d[:12], p1)
    d2 = dv(d[:12] + d1, [6] + p1)
    return d[12:] == d1 + d2


def formatar_cnpj(cnpj: str) -> str:
    d = so_digitos(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else cnpj


# --- Sugestão de atividade (anexo do Simples) pelo CNAE ------------------------
# Regras por grupo (3 dígitos) têm prioridade sobre as por divisão (2 dígitos).
_POR_GRUPO: dict[str, tuple[Atividade | None, str]] = {
    "691": (Atividade.SERVICO_ANEXO_IV, "Advocacia: Anexo IV (CPP fora do DAS)"),
    "692": (Atividade.SERVICO_ANEXO_III, "Serviços contábeis: Anexo III"),
    "801": (Atividade.SERVICO_ANEXO_IV, "Vigilância e segurança: Anexo IV"),
    "812": (Atividade.SERVICO_ANEXO_IV, "Limpeza: Anexo IV"),
    "813": (Atividade.SERVICO_ANEXO_IV, "Paisagismo: Anexo IV"),
    "641": (None, "Atividade financeira: em regra vedada ao Simples"),
}
_POR_DIVISAO: list[tuple[range, Atividade | None, str]] = [
    (range(1, 4), None, "Atividade rural: avaliar tributação como produtor rural"),
    (range(5, 34), Atividade.INDUSTRIA, "Indústria (extrativa ou de transformação): Anexo II"),
    (range(35, 40), None, "Utilidades públicas: verificar vedações ao Simples"),
    (range(41, 44), Atividade.SERVICO_ANEXO_IV, "Construção civil: Anexo IV (CPP fora do DAS)"),
    (range(45, 48), Atividade.COMERCIO, "Comércio: Anexo I"),
    (range(49, 54), Atividade.SERVICO_ANEXO_III, "Transporte e correio: Anexo III"),
    (range(55, 56), Atividade.SERVICO_ANEXO_III, "Alojamento: Anexo III"),
    (range(56, 57), Atividade.COMERCIO, "Alimentação (restaurantes e similares): Anexo I"),
    (range(58, 62), Atividade.SERVICO_ANEXO_III, "Edição, audiovisual e telecom: Anexo III"),
    (range(62, 64), Atividade.SERVICO_FATOR_R, "Tecnologia da informação: Anexo III ou V pelo fator R"),
    (range(64, 67), None, "Atividade financeira: em regra vedada ao Simples"),
    (range(68, 69), Atividade.SERVICO_ANEXO_III, "Atividades imobiliárias: Anexo III"),
    (range(70, 76), Atividade.SERVICO_FATOR_R, "Serviços intelectuais/técnicos: Anexo III ou V pelo fator R"),
    (range(77, 80), Atividade.SERVICO_ANEXO_III, "Locação, agências e turismo: Anexo III"),
    (range(80, 82), Atividade.SERVICO_ANEXO_IV, "Vigilância, limpeza e conservação: Anexo IV"),
    (range(82, 86), Atividade.SERVICO_ANEXO_III, "Serviços administrativos e educação: Anexo III"),
    (range(86, 87), Atividade.SERVICO_FATOR_R, "Saúde (medicina, odontologia): Anexo III ou V pelo fator R"),
    (range(87, 100), Atividade.SERVICO_ANEXO_III, "Demais serviços: Anexo III"),
]
_AVISO = " — sugestão automática; confirme no Anexo VI da Resolução CGSN 140/2018."


def sugerir_atividade(cnae: str | None) -> tuple[Atividade | None, str]:
    d = so_digitos(cnae or "")
    if len(d) < 2:
        return None, "CNAE não informado"
    if d[:3] in _POR_GRUPO:
        atividade, motivo = _POR_GRUPO[d[:3]]
        return atividade, motivo + _AVISO
    divisao = int(d[:2])
    for faixa, atividade, motivo in _POR_DIVISAO:
        if divisao in faixa:
            return atividade, motivo + _AVISO
    return None, "CNAE sem regra de sugestão" + _AVISO


# --- Consulta externa ---------------------------------------------------------
class CnpjNaoEncontrado(Exception):
    pass


class CnpjIndisponivel(Exception):
    pass


@dataclass
class DadosCnpj:
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    situacao: str | None
    cnae_principal: str | None
    cnae_descricao: str | None
    municipio: str | None
    uf: str | None
    email: str | None
    telefone: str | None
    opcao_simples: bool | None
    opcao_mei: bool | None

    def como_dict(self) -> dict[str, Any]:
        atividade, motivo = sugerir_atividade(self.cnae_principal)
        regime = "mei" if self.opcao_mei else "simples" if self.opcao_simples else None
        return {
            **self.__dict__,
            "regime_sugerido": regime,
            "atividade_sugerida": atividade,
            "atividade_justificativa": motivo,
        }


def _texto(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def interpretar_brasilapi(dados: dict[str, Any]) -> DadosCnpj:
    cnae = dados.get("cnae_fiscal")
    cnae_txt = str(cnae).zfill(7) if cnae not in (None, "", 0) else None
    telefone = _texto(dados.get("ddd_telefone_1"))
    return DadosCnpj(
        cnpj=so_digitos(str(dados.get("cnpj", ""))),
        razao_social=_texto(dados.get("razao_social")) or "",
        nome_fantasia=_texto(dados.get("nome_fantasia")),
        situacao=_texto(dados.get("descricao_situacao_cadastral")),
        cnae_principal=cnae_txt,
        cnae_descricao=_texto(dados.get("cnae_fiscal_descricao")),
        municipio=_texto(dados.get("municipio")),
        uf=_texto(dados.get("uf")),
        email=(_texto(dados.get("email")) or "").lower() or None,
        telefone=telefone,
        opcao_simples=dados.get("opcao_pelo_simples"),
        opcao_mei=dados.get("opcao_pelo_mei"),
    )


def consultar_brasilapi(cnpj: str, transport: httpx.BaseTransport | None = None) -> DadosCnpj:
    cfg = get_settings()
    try:
        with httpx.Client(timeout=cfg.cnpj_timeout_segundos, transport=transport) as cliente:
            resp = cliente.get(f"{cfg.brasilapi_url}/{so_digitos(cnpj)}")
    except httpx.HTTPError as erro:
        raise CnpjIndisponivel(str(erro)) from erro
    if resp.status_code == 404:
        raise CnpjNaoEncontrado(cnpj)
    if resp.status_code >= 400:
        raise CnpjIndisponivel(f"BrasilAPI respondeu {resp.status_code}")
    return interpretar_brasilapi(resp.json())
