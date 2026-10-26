from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from tolaris_motor import cnae

from ..models import Usuario
from ..seguranca import usuario_atual

router = APIRouter(prefix="/cnae", tags=["cnae"])


@router.get("")
def buscar(
    q: str = Query(default="", max_length=100),
    anexo: str | None = Query(default=None, pattern=r"^(iii_direto|fator_r|iv|comercio|industria|vedado)$"),
    divisao: str | None = Query(default=None, pattern=r"^\d{2}$"),
    so_da_tabela: bool = False,
    limite: int = Query(default=60, ge=1, le=300),
    _: Usuario = Depends(usuario_atual),
) -> dict[str, Any]:
    """Procura CNAEs por código ou palavras da descrição, com o Anexo provável e a vedação de cada um."""
    return {**cnae.buscar(q, anexo, divisao, so_da_tabela, limite), "fontes": cnae.fontes()}


@router.get("/divisoes")
def divisoes(_: Usuario = Depends(usuario_atual)) -> dict[str, Any]:
    return {
        "divisoes": cnae.divisoes(),
        "filtros": [{"codigo": k, "nome": v} for k, v in cnae.FILTROS_ANEXO.items()],
    }


@router.get("/{codigo}")
def detalhe(codigo: str, _: Usuario = Depends(usuario_atual)) -> dict[str, Any]:
    dados = cnae.item(codigo)
    if dados is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CNAE não encontrado")
    return {**dados, "fontes": cnae.fontes()}
