"""CNAE: catálogo completo (IBGE), vedações do Simples (Res. CGSN 140/2018, Anexos VI e VII) e Anexo provável de cada código.

Níveis de confiança de ``classificar``:
- ``oficial``: o CNAE está nos Anexos VI ou VII da Resolução CGSN 140/2018 (impeditivo ou ambíguo para o Simples);
- ``tabela``: o Anexo vem de uma tabela comercial (Contabilizei), que interpreta a lei por código. A Resolução define o Anexo
  pela descrição da atividade (art. 25, § 1º), não por CNAE, então confira antes de decidir;
- ``divisao``: regra aproximada pela divisão do CNAE, só para os códigos que a tabela não cobre.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from . import tabelas
from .empresa import Atividade

ROTULO_ANEXO = {
    Atividade.COMERCIO: "Anexo I (comércio)",
    Atividade.INDUSTRIA: "Anexo II (indústria)",
    Atividade.SERVICO_ANEXO_III: "Anexo III",
    Atividade.SERVICO_ANEXO_IV: "Anexo IV",
    Atividade.SERVICO_FATOR_R: "Anexo III ou V (fator R)",
    Atividade.LOCACAO_BENS_MOVEIS: "Anexo III sem ISS (locação de bens móveis)",
    Atividade.INDUSTRIA_IPI_ISS: "Anexo II com ISS (IPI e ISS)",
    Atividade.TRANSPORTE_CARGAS_ICMS: "Anexo III com ICMS (transporte de cargas)",
    Atividade.TRANSPORTE_PASSAGEIROS_ICMS: "Anexo III com ICMS (transporte de passageiros)",
    Atividade.COMUNICACAO_ICMS: "Anexo III com ICMS (comunicação)",
}

# Regras aproximadas, só para CNAEs fora da tabela de Anexos. Grupo (3 dígitos) vence divisão (2 dígitos).
_POR_GRUPO: dict[str, tuple[Atividade, str]] = {
    "691": (Atividade.SERVICO_ANEXO_IV, "Advocacia: Anexo IV (CPP fora do DAS)"),
    "692": (Atividade.SERVICO_ANEXO_III, "Serviços contábeis: Anexo III"),
    "801": (Atividade.SERVICO_ANEXO_IV, "Vigilância e segurança: Anexo IV"),
    "812": (Atividade.SERVICO_ANEXO_IV, "Limpeza: Anexo IV"),
    "813": (Atividade.SERVICO_ANEXO_IV, "Paisagismo: Anexo IV"),
}
_POR_DIVISAO: list[tuple[range, Atividade, str]] = [
    (range(5, 34), Atividade.INDUSTRIA, "Indústria (extrativa ou de transformação): Anexo II"),
    (range(41, 44), Atividade.SERVICO_ANEXO_IV, "Construção civil: Anexo IV (CPP fora do DAS)"),
    (range(45, 48), Atividade.COMERCIO, "Comércio: Anexo I"),
    (range(49, 54), Atividade.SERVICO_ANEXO_III, "Transporte e correio: Anexo III"),
    (range(55, 56), Atividade.SERVICO_ANEXO_III, "Alojamento: Anexo III"),
    (range(56, 57), Atividade.COMERCIO, "Alimentação (restaurantes e similares): Anexo I"),
    (range(58, 62), Atividade.SERVICO_ANEXO_III, "Edição, audiovisual e telecom: Anexo III"),
    (range(62, 64), Atividade.SERVICO_FATOR_R, "Tecnologia da informação: Anexo III ou V pelo fator R"),
    (range(68, 69), Atividade.SERVICO_ANEXO_III, "Atividades imobiliárias: Anexo III"),
    (range(70, 76), Atividade.SERVICO_FATOR_R, "Serviços intelectuais/técnicos: Anexo III ou V pelo fator R"),
    (range(77, 80), Atividade.SERVICO_ANEXO_III, "Locação, agências e turismo: Anexo III"),
    (range(80, 82), Atividade.SERVICO_ANEXO_IV, "Vigilância, limpeza e conservação: Anexo IV"),
    (range(82, 86), Atividade.SERVICO_ANEXO_III, "Serviços administrativos e educação: Anexo III"),
    (range(86, 87), Atividade.SERVICO_FATOR_R, "Saúde (medicina, odontologia): Anexo III ou V pelo fator R"),
    (range(87, 100), Atividade.SERVICO_ANEXO_III, "Demais serviços: Anexo III"),
]
_SEM_REGRA: dict[range, str] = {
    range(1, 4): "Atividade rural: avaliar tributação como produtor rural",
    range(35, 40): "Utilidades públicas: verificar vedações ao Simples",
    range(64, 67): "Atividade financeira: em regra vedada ao Simples",
}


def _dados() -> dict[str, Any]:
    return tabelas.carregar("cnae")


def so_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar(codigo: str | None) -> str | None:
    """Código com 7 dígitos (``6201-5/01`` → ``6201501``) ou ``None``."""
    d = so_digitos(codigo)
    return d.zfill(7) if 1 <= len(d) <= 7 else None


def formatar(codigo: str) -> str:
    return f"{codigo[:4]}-{codigo[4]}/{codigo[5:]}" if len(codigo) == 7 else codigo


@dataclass(frozen=True)
class Classificacao:
    atividade: Atividade | None
    """Atividade do motor (define o Anexo); ``None`` quando é vedado, ambíguo ou não há regra."""
    anexos: tuple[str, ...]
    fator_r: bool
    vedacao: str | None
    """``impeditivo`` (Anexo VI) ou ``ambiguo`` (Anexo VII da Resolução CGSN 140/2018)."""
    confianca: str
    """``oficial``, ``tabela`` ou ``divisao`` (ver o módulo)."""
    motivo: str

    @property
    def rotulo(self) -> str:
        if self.vedacao == "impeditivo":
            return "Vedado ao Simples"
        if self.atividade:
            return ROTULO_ANEXO[self.atividade]
        if self.anexos:
            return "Anexo " + " ou ".join(self.anexos) + " (depende da atividade)"
        return "Sem enquadramento automático"


def _atividade_da_tabela(anexos: list[str], fator_r: bool) -> Atividade | None:
    conjunto = set(anexos)
    if fator_r and conjunto <= {"III", "V"}:
        return Atividade.SERVICO_FATOR_R
    return {
        frozenset({"III"}): Atividade.SERVICO_ANEXO_III,
        frozenset({"IV"}): Atividade.SERVICO_ANEXO_IV,
        frozenset({"I"}): Atividade.COMERCIO,
        frozenset({"II"}): Atividade.INDUSTRIA,
    }.get(frozenset(conjunto))


def _por_divisao(codigo: str) -> tuple[Atividade | None, str]:
    if codigo[:3] in _POR_GRUPO:
        return _POR_GRUPO[codigo[:3]]
    divisao = int(codigo[:2])
    for faixa, atividade, motivo in _POR_DIVISAO:
        if divisao in faixa:
            return atividade, motivo
    for faixa, motivo in _SEM_REGRA.items():
        if divisao in faixa:
            return None, motivo
    return None, "CNAE sem regra de enquadramento"


def classificar(codigo: str | None) -> Classificacao:
    cod = normalizar(codigo)
    if cod is None or len(so_digitos(codigo)) < 2:
        return Classificacao(None, (), False, None, "divisao", "CNAE não informado")
    dados = _dados()
    vedacao = dados["vedacao"].get(cod)
    entrada = dados["anexos"].get(cod)
    anexos = tuple(entrada["anexos"]) if entrada else ()
    fator_r = bool(entrada and entrada["fator_r"])
    if vedacao == "impeditivo":
        return Classificacao(
            None, anexos, fator_r, vedacao, "oficial",
            "CNAE impeditivo ao Simples Nacional (Res. CGSN 140/2018, Anexo VI): a empresa com esta atividade não pode optar",
        )
    if entrada:
        atividade = _atividade_da_tabela(entrada["anexos"], fator_r)
        motivo = "Anexo pela tabela da Contabilizei (fonte comercial): confira na descrição da atividade (Res. CGSN 140/2018, art. 25, § 1º)"
        if vedacao == "ambiguo":
            motivo = "CNAE ambíguo: abrange atividade impeditiva e permitida ao Simples (Res. CGSN 140/2018, Anexo VII). " + motivo
        return Classificacao(atividade, anexos, fator_r, vedacao, "tabela", motivo)
    atividade, motivo = _por_divisao(cod)
    motivo += " (regra aproximada pela divisão do CNAE; este código não está na tabela de Anexos)"
    if vedacao == "ambiguo":
        motivo = "CNAE ambíguo: abrange atividade impeditiva e permitida ao Simples (Res. CGSN 140/2018, Anexo VII). " + motivo
    return Classificacao(atividade, anexos, fator_r, vedacao, "divisao", motivo)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def descricao(codigo: str) -> str | None:
    return _dados()["subclasses"].get(codigo)


def item(codigo: str) -> dict[str, Any] | None:
    """Dados completos de um CNAE do catálogo (ou ``None`` se o código não existe)."""
    cod = normalizar(codigo)
    dados = _dados()
    if cod is None or cod not in dados["subclasses"]:
        return None
    div = dados["divisoes"].get(cod[:2], {})
    c = classificar(cod)
    return {
        "codigo": cod,
        "codigo_formatado": formatar(cod),
        "descricao": dados["subclasses"][cod],
        "secao": div.get("secao"),
        "secao_nome": dados["secoes"].get(div.get("secao", ""), ""),
        "divisao": cod[:2],
        "divisao_nome": div.get("nome", ""),
        "atividade": c.atividade.value if c.atividade else None,
        "anexo": c.rotulo,
        "anexos": list(c.anexos),
        "fator_r": c.fator_r,
        "vedacao": c.vedacao,
        "confianca": c.confianca,
        "motivo": c.motivo,
    }


FILTROS_ANEXO = {
    "iii_direto": "Anexo III direto (sem fator R)",
    "fator_r": "Anexo III ou V pelo fator R",
    "iv": "Anexo IV",
    "comercio": "Comércio (Anexo I)",
    "industria": "Indústria (Anexo II)",
    "vedado": "Vedado ou ambíguo no Simples",
}


def _passa_no_filtro(it: dict[str, Any], filtro: str) -> bool:
    if filtro == "iii_direto":
        return it["atividade"] == Atividade.SERVICO_ANEXO_III.value and not it["vedacao"]
    if filtro == "fator_r":
        return it["atividade"] == Atividade.SERVICO_FATOR_R.value and not it["vedacao"]
    if filtro == "iv":
        return it["atividade"] == Atividade.SERVICO_ANEXO_IV.value and not it["vedacao"]
    if filtro == "comercio":
        return it["atividade"] == Atividade.COMERCIO.value and not it["vedacao"]
    if filtro == "industria":
        return it["atividade"] == Atividade.INDUSTRIA.value and not it["vedacao"]
    if filtro == "vedado":
        return bool(it["vedacao"])
    return True


def buscar(
    texto: str = "", anexo: str | None = None, divisao: str | None = None, so_da_tabela: bool = False, limite: int = 60
) -> dict[str, Any]:
    """Procura no catálogo por código ou palavras da descrição, com filtros. ``total`` conta todos os achados."""
    dados = _dados()
    termos = _sem_acento(texto).split()
    digitos = so_digitos(texto)
    so_codigo = bool(termos) and re.fullmatch(r"[\d\s\-/.]+", texto.strip()) is not None
    achados: list[dict[str, Any]] = []
    for cod in sorted(dados["subclasses"]):
        if divisao and cod[:2] != divisao:
            continue
        if termos:
            if so_codigo:
                if not cod.startswith(digitos):
                    continue
            elif not all(t in _sem_acento(dados["subclasses"][cod]) for t in termos):
                continue
        it = item(cod)
        assert it is not None
        if so_da_tabela and it["confianca"] != "tabela" and not it["vedacao"]:
            continue
        if anexo and not _passa_no_filtro(it, anexo):
            continue
        achados.append(it)
    return {"total": len(achados), "itens": achados[: max(1, limite)]}


def divisoes() -> list[dict[str, str]]:
    dados = _dados()
    return [{"codigo": c, "nome": v["nome"], "secao": v["secao"]} for c, v in sorted(dados["divisoes"].items())]


def fontes() -> dict[str, str]:
    dados = _dados()
    return {**dados["fontes"], "atualizado_em": dados["atualizado_em"]}
