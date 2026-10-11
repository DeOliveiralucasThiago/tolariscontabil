"""Carregamento das tabelas legais (arquivos JSON versionados por vigência).

Cada arquivo traz uma lista ``vigencias`` ordenada; cada item tem ``inicio``
(AAAA-MM-DD) e os parâmetros válidos a partir dessa data. Atualizar a lei =
acrescentar uma vigência no JSON, sem mexer no código de cálculo.
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=None)
def carregar(nome: str) -> dict[str, Any]:
    texto = resources.files(__package__).joinpath(f"{nome}.json").read_text(encoding="utf-8")
    return json.loads(texto)


def vigente(nome: str, data: date) -> dict[str, Any]:
    """Retorna a vigência da tabela ``nome`` aplicável na ``data``."""
    escolhida = None
    for vig in carregar(nome)["vigencias"]:
        if date.fromisoformat(vig["inicio"]) <= data:
            escolhida = vig
    if escolhida is None:
        raise ValueError(f"Tabela '{nome}' não tem vigência para {data.isoformat()}")
    return escolhida
