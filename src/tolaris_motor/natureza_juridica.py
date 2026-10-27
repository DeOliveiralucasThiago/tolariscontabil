"""Natureza jurídica da empresa (tabela da Receita/IBGE) e o que ela decide no Simples Nacional e no MEI.

A BrasilAPI devolve o código e a descrição da natureza jurídica do CNPJ. A classificação aqui parte da **descrição** (palavras que não mudam entre as
versões da tabela) e, sem descrição, do primeiro dígito do código: 1 administração pública, 2 entidades empresariais, 3 entidades sem fins lucrativos,
4 pessoas físicas, 5 organizações internacionais.

Base legal (texto na pasta ``legislação/``):

- LC 123/2006, art. 3º, ``caput``: são microempresas ou empresas de pequeno porte a sociedade empresária, a sociedade simples, a empresa individual de
  responsabilidade limitada e o empresário do art. 966 do Código Civil (o empresário individual).
- LC 123/2006, art. 3º, § 4º, VI e X: não podem optar as cooperativas (salvo as de consumo) e as sociedades por ações.
- LC 123/2006, art. 18-A, § 1º: o MEI é empresário individual (ou o empreendedor rural); mudar para outra natureza o desenquadra (art. 18-A, § 16, I).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

BASE_LEGAL_ELEGIBILIDADE = "LC 123/2006, art. 3º, caput e § 4º, VI e X"
BASE_LEGAL_MEI = "LC 123/2006, art. 18-A, § 1º"


@dataclass(frozen=True)
class Natureza:
    tipo: str
    rotulo: str
    simples: str
    """``sim`` (pode optar), ``vedado`` (a lei veda), ``nao_se_aplica`` (não é microempresa nem empresa de pequeno porte) ou ``conferir``."""
    mei: bool
    """Só o empresário individual pode ser MEI."""
    explicacao: str


NATUREZAS: dict[str, Natureza] = {
    "empresario_individual": Natureza(
        "empresario_individual", "Empresário individual", "sim", True,
        "Empresário individual (art. 966 do Código Civil): pode optar pelo Simples Nacional e, se a receita couber, ser MEI.",
    ),
    "sociedade_empresaria": Natureza(
        "sociedade_empresaria", "Sociedade empresária (limitada, nome coletivo etc.)", "sim", False,
        "Sociedade empresária: pode optar pelo Simples Nacional (LC 123/2006, art. 3º, caput).",
    ),
    "sociedade_simples": Natureza(
        "sociedade_simples", "Sociedade simples", "sim", False,
        "Sociedade simples (inclusive as sociedades de profissionais e de advogados): pode optar pelo Simples Nacional (LC 123/2006, art. 3º, caput).",
    ),
    "eireli": Natureza(
        "eireli", "Empresa individual de responsabilidade limitada (EIRELI)", "sim", False,
        "EIRELI: pode optar pelo Simples Nacional. A EIRELI foi extinta em 2021 e as que restam viraram sociedades limitadas unipessoais; confira o cadastro.",
    ),
    "sociedade_por_acoes": Natureza(
        "sociedade_por_acoes", "Sociedade por ações", "vedado", False,
        "Sociedade por ações (anônima, aberta ou fechada, ou em comandita por ações): a LC 123/2006, art. 3º, § 4º, X, veda o Simples Nacional. "
        "Pode usar o Lucro Presumido ou o Lucro Real.",
    ),
    "cooperativa": Natureza(
        "cooperativa", "Cooperativa", "vedado", False,
        "Cooperativa: a LC 123/2006, art. 3º, § 4º, VI, veda o Simples Nacional, salvo as cooperativas de consumo. Confira o tipo da cooperativa.",
    ),
    "cooperativa_consumo": Natureza(
        "cooperativa_consumo", "Cooperativa de consumo", "sim", False,
        "Cooperativa de consumo: única cooperativa que pode optar pelo Simples Nacional (LC 123/2006, art. 3º, § 4º, VI).",
    ),
    "sem_fins_lucrativos": Natureza(
        "sem_fins_lucrativos", "Associação, fundação ou entidade sem fins lucrativos", "nao_se_aplica", False,
        "Entidade sem fins lucrativos não é microempresa nem empresa de pequeno porte (LC 123/2006, art. 3º, caput): o Simples Nacional não se aplica.",
    ),
    "administracao_publica": Natureza(
        "administracao_publica", "Administração pública", "nao_se_aplica", False,
        "Órgão ou entidade da administração pública não é microempresa nem empresa de pequeno porte: o Simples Nacional não se aplica.",
    ),
    "pessoa_fisica": Natureza(
        "pessoa_fisica", "Pessoa física ou equiparada (produtor rural, contribuinte individual)", "nao_se_aplica", False,
        "Pessoa física equiparada a empresa não opta pelo Simples Nacional como microempresa; para o empresário individual use \"Empresário individual\".",
    ),
    "outra": Natureza(
        "outra", "Outra natureza jurídica", "conferir", False,
        "Natureza jurídica não reconhecida pelo Tolaris: confira se ela é sociedade empresária, sociedade simples, EIRELI ou empresário individual (LC 123/2006, art. 3º).",
    ),
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def classificar(descricao: str | None, codigo: str | None = None) -> Natureza | None:
    """Classifica pela descrição (e, sem ela, pelo primeiro dígito do código); ``None`` se não há informação."""
    d = _normalizar(descricao or "")
    cod = re.sub(r"\D", "", codigo or "")
    if not d and not cod:
        return None
    if d:
        if "anonima" in d or "comandita por acoes" in d or "sociedade por acoes" in d:
            return NATUREZAS["sociedade_por_acoes"]
        if "cooperativ" in d:
            return NATUREZAS["cooperativa_consumo" if "consumo" in d else "cooperativa"]
        if "empresario" in d and "individual" in d and "sociedade" not in d and "limitada" not in d:
            return NATUREZAS["empresario_individual"]
        if "individual de responsabilidade limitada" in d or "eireli" in d:
            return NATUREZAS["eireli"]
        if "sociedade simples" in d or "advog" in d:
            return NATUREZAS["sociedade_simples"]
        if "sociedade empresaria" in d or "nome coletivo" in d or "comandita" in d or "limitada" in d or "conta de participacao" in d:
            return NATUREZAS["sociedade_empresaria"]
        if any(p in d for p in ("associacao", "fundacao", "organizacao religiosa", "sindicato", "partido politico", "servico social", "entidade sem fins")):
            return NATUREZAS["sem_fins_lucrativos"]
        if any(p in d for p in ("empresa publica", "economia mista", "autarquia", "municipio", "estado ou distrito", "uniao", "orgao publico", "fundo publico")):
            return NATUREZAS["administracao_publica"]
        if any(p in d for p in ("produtor rural", "segurado especial", "contribuinte individual", "pessoa fisica")):
            return NATUREZAS["pessoa_fisica"]
    if cod:
        return {"1": NATUREZAS["administracao_publica"], "3": NATUREZAS["sem_fins_lucrativos"], "4": NATUREZAS["pessoa_fisica"]}.get(cod[0], NATUREZAS["outra"])
    return NATUREZAS["outra"]


def impede_simples(natureza: Natureza | None) -> bool:
    """A natureza jurídica, sozinha, impede o Simples Nacional (vedada em lei ou fora do conceito de ME/EPP)."""
    return natureza is not None and natureza.simples in ("vedado", "nao_se_aplica")


def aviso_regime_normal(natureza: Natureza | None) -> str | None:
    """Aviso para o Lucro Presumido e o Lucro Real quando a natureza jurídica não é a de uma empresa comum."""
    if natureza is None or natureza.tipo not in ("sem_fins_lucrativos", "administracao_publica", "pessoa_fisica"):
        return None
    return (
        f"Natureza jurídica \"{natureza.rotulo}\": o cálculo do Tolaris é o de uma empresa com fins lucrativos. Entidades sem fins lucrativos podem ter "
        "imunidade ou isenção e órgãos públicos não pagam como empresa; use o resultado só como referência e confira com o contador."
    )
