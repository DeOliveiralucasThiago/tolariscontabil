from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status

from ..cnpj import CnpjIndisponivel, CnpjNaoEncontrado, DadosCnpj, cnpj_valido, consultar_brasilapi, so_digitos
from ..models import Usuario
from ..schemas import CnpjSaida
from ..seguranca import usuario_atual

router = APIRouter(prefix="/cnpj", tags=["CNPJ"])

ConsultaCnpj = Callable[[str], DadosCnpj]


def get_consulta_cnpj() -> ConsultaCnpj:
    """Dependência substituível nos testes (sem rede)."""
    return consultar_brasilapi


@router.get("/{cnpj}", response_model=CnpjSaida)
def consultar(
    cnpj: str, _: Usuario = Depends(usuario_atual), consulta: ConsultaCnpj = Depends(get_consulta_cnpj)
) -> dict:
    digitos = so_digitos(cnpj)
    if not cnpj_valido(digitos):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "CNPJ inválido")
    try:
        return consulta(digitos).como_dict()
    except CnpjNaoEncontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "CNPJ não encontrado na Receita Federal") from None
    except CnpjIndisponivel:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Consulta de CNPJ indisponível no momento; preencha os dados manualmente"
        ) from None
