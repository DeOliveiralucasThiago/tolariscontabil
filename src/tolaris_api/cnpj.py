"""CNPJ: validação dos dígitos, consulta na BrasilAPI e sugestão de atividade pelo CNAE."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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


_ROTULO_ATIVIDADE = {
    Atividade.COMERCIO: "Anexo I (comércio)",
    Atividade.INDUSTRIA: "Anexo II (indústria)",
    Atividade.SERVICO_ANEXO_III: "Anexo III",
    Atividade.SERVICO_ANEXO_IV: "Anexo IV",
    Atividade.SERVICO_FATOR_R: "Anexo III ou V (fator R)",
}


def _item_cnae(codigo: str, descricao: str | None, principal: bool) -> dict[str, Any]:
    atividade, motivo = sugerir_atividade(codigo)
    return {
        "codigo": codigo,
        "descricao": descricao or "",
        "principal": principal,
        "atividade": atividade.value if atividade else None,
        "anexo": _ROTULO_ATIVIDADE[atividade] if atividade else "Sem enquadramento automático",
        "motivo": motivo,
    }


def classificar_cnaes(
    principal: str | None, descricao: str | None, secundarios: list[dict[str, str]] | None, atividade_cliente: str | None
) -> dict[str, Any]:
    """CNAEs do cadastro do cliente com o Anexo provável de cada um (regra orientativa por divisão do CNAE).

    ``anexo_iii_no_cadastro`` lista os secundários que a regra põe no Anexo III quando a atividade do cliente é do
    fator R: já estão no cadastro, então bastam ser exercidos de fato para segregar a receita. Sugerir CNAEs que o
    cliente ainda não tem exigiria a tabela oficial (Res. CGSN 140/2018, Anexo VI), que o Tolaris não carrega.
    """
    itens = []
    if principal:
        itens.append(_item_cnae(so_digitos(principal).zfill(7), descricao, True))
    itens += [_item_cnae(c["codigo"], c.get("descricao"), False) for c in (secundarios or []) if c.get("codigo")]
    fator_r = atividade_cliente == Atividade.SERVICO_FATOR_R.value or (
        bool(itens) and itens[0]["principal"] and itens[0]["atividade"] == Atividade.SERVICO_FATOR_R.value
    )
    candidatos = [i for i in itens if not i["principal"] and i["atividade"] == Atividade.SERVICO_ANEXO_III.value] if fator_r else []
    return {
        "cnaes": itens,
        "atividade_fator_r": fator_r,
        "anexo_iii_no_cadastro": candidatos,
        "aviso": "Classificação orientativa por divisão do CNAE; confirme cada código no Anexo VI da Resolução CGSN 140/2018. "
        "O Anexo vale pela atividade realmente exercida, não só pelo CNAE cadastrado.",
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
