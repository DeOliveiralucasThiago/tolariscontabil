from __future__ import annotations

from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..cambio import MOEDAS, CambioIndisponivel, CotacaoNaoEncontrada, Ptax, consultar_ptax
from ..models import Usuario
from ..seguranca import usuario_atual

router = APIRouter(prefix="/cambio", tags=["câmbio"])

ConsultaPtax = Callable[[str, date], Ptax]


def get_consulta_ptax() -> ConsultaPtax:
    """Dependência substituível nos testes (sem rede)."""
    return consultar_ptax


@router.get("/moedas")
def moedas(_: Usuario = Depends(usuario_atual)) -> list[dict[str, str]]:
    return [{"codigo": c, "nome": n} for c, n in MOEDAS.items()]


@router.get("/ptax")
def ptax(
    moeda: str = Query(min_length=3, max_length=3),
    data: date = Query(),
    _: Usuario = Depends(usuario_atual),
    consulta: ConsultaPtax = Depends(get_consulta_ptax),
) -> dict:
    if moeda.upper() not in MOEDAS:
        raise HTTPException(422, "Moeda sem cotação PTAX do Banco Central")
    if data > date.today():
        raise HTTPException(422, "A data não pode ser futura")
    try:
        return consulta(moeda.upper(), data).como_dict()
    except CotacaoNaoEncontrada:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sem cotação PTAX para essa data; informe a taxa manualmente") from None
    except CambioIndisponivel:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Consulta de câmbio indisponível no momento; informe a taxa manualmente"
        ) from None
