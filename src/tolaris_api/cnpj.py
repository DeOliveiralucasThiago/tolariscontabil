"""CNPJ: validação dos dígitos, consulta na BrasilAPI e sugestão de atividade pelo CNAE."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from tolaris_motor import Atividade
from tolaris_motor import cnae as cnae_motor

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
def sugerir_atividade(cnae: str | None) -> tuple[Atividade | None, str]:
    """Atividade (e portanto Anexo) provável de um CNAE: vedação oficial, tabela de Anexos ou regra por divisão."""
    c = cnae_motor.classificar(cnae)
    return c.atividade, c.motivo


def _item_cnae(codigo: str, descricao: str | None, principal: bool) -> dict[str, Any]:
    c = cnae_motor.classificar(codigo)
    return {
        "codigo": codigo,
        "descricao": descricao or cnae_motor.descricao(codigo) or "",
        "principal": principal,
        "atividade": c.atividade.value if c.atividade else None,
        "anexo": c.rotulo,
        "vedacao": c.vedacao,
        "confianca": c.confianca,
        "motivo": c.motivo,
    }


def classificar_cnaes(
    principal: str | None, descricao: str | None, secundarios: list[dict[str, str]] | None, atividade_cliente: str | None
) -> dict[str, Any]:
    """CNAEs do cadastro do cliente com o Anexo provável de cada um.

    ``anexo_iii_no_cadastro`` lista os secundários que a tabela põe no Anexo III direto quando a atividade do cliente é do
    fator R: já estão no cadastro, então bastam ser exercidos de fato para segregar a receita. Para conhecer CNAEs que o
    cliente ainda não tem, use a busca de CNAEs (``/cnae``).
    """
    itens = []
    if principal:
        itens.append(_item_cnae(so_digitos(principal).zfill(7), descricao, True))
    itens += [_item_cnae(c["codigo"], c.get("descricao"), False) for c in (secundarios or []) if c.get("codigo")]
    fator_r = atividade_cliente == Atividade.SERVICO_FATOR_R.value or (
        bool(itens) and itens[0]["principal"] and itens[0]["atividade"] == Atividade.SERVICO_FATOR_R.value
    )
    candidatos = (
        [i for i in itens if not i["principal"] and i["atividade"] == Atividade.SERVICO_ANEXO_III.value and not i["vedacao"]]
        if fator_r
        else []
    )
    return {
        "cnaes": itens,
        "atividade_fator_r": fator_r,
        "anexo_iii_no_cadastro": candidatos,
        "vedados": [i for i in itens if i["vedacao"]],
        "aviso": "O Anexo vem da tabela de CNAEs e é orientativo: a Resolução CGSN 140/2018 (art. 25, § 1º) define o Anexo pela "
        "atividade realmente exercida, não só pelo código cadastrado. Vedações: Anexos VI e VII da mesma Resolução.",
    }


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
    cnaes_secundarios: list[dict[str, str]] = field(default_factory=list)

    def como_dict(self) -> dict[str, Any]:
        atividade, motivo = sugerir_atividade(self.cnae_principal)
        regime = "mei" if self.opcao_mei else "simples" if self.opcao_simples else None
        return {
            **self.__dict__,
            "regime_sugerido": regime,
            "atividade_sugerida": atividade,
            "atividade_justificativa": motivo,
            "cnaes_classificados": classificar_cnaes(
                self.cnae_principal, self.cnae_descricao, self.cnaes_secundarios,
                atividade.value if atividade else None,
            ),
        }


def _texto(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _cnaes_secundarios(bruto: Any) -> list[dict[str, str]]:
    """CNAEs secundários da BrasilAPI (``[{"codigo": 6209100, "descricao": "..."}]``); o código 0 é o "sem secundário"."""
    achados: dict[str, str] = {}
    for item in bruto if isinstance(bruto, list) else []:
        try:
            codigo = str(int(item["codigo"])).zfill(7)
        except (KeyError, TypeError, ValueError):
            continue
        if len(codigo) == 7 and codigo != "0000000":
            achados.setdefault(codigo, (_texto(item.get("descricao")) or "")[:300])
    return [{"codigo": c, "descricao": d} for c, d in achados.items()]


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
        cnaes_secundarios=_cnaes_secundarios(dados.get("cnaes_secundarios")),
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
