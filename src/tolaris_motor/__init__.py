"""Tolaris — motor de cálculo tributário com memória de cálculo.

Módulos:
- ``simples``: Simples Nacional (anexos, faixas, fator R)
- ``presumido``: Lucro Presumido (trimestral, LC 224/2025)
- ``real``: Lucro Real (estimativa gerencial anual)
- ``comparativo``: comparação entre regimes e simulação expressa
- ``pessoa_fisica``: INSS, IRPF 2026, dividendos, pró-labore x lucros
- ``reforma``: transição IBS/CBS 2025-2033
"""

from .base import Passo, Resultado, brl, pct
from .comparativo import Comparativo, comparar, simulacao_expressa
from .empresa import Atividade, PerfilEmpresa

__all__ = [
    "Atividade",
    "Comparativo",
    "Passo",
    "PerfilEmpresa",
    "Resultado",
    "brl",
    "comparar",
    "pct",
    "simulacao_expressa",
]
__version__ = "0.1.0"
