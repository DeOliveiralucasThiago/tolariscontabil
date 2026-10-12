# Sem "from __future__ import annotations": as rotas são criadas em laço e o FastAPI
# precisa ler o tipo real do corpo em cada função.
from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Simulacao, Usuario
from ..schemas import SalarioEntrada, SimulacaoSaida
from ..seguranca import usuario_atual
from ..servicos import TIPOS_FASE2, executar_salario
from .clientes import obter_cliente
from .simulacoes import _salvar

router = APIRouter(tags=["calculadoras"])


def _registrar(tipo: str, modelo: type, executor: Any) -> None:
    rota = tipo.replace("_", "-")

    def previa(dados: modelo, _: Usuario = Depends(usuario_atual)) -> dict[str, Any]:  # type: ignore[valid-type]
        return executor(dados)

    def salvar(
        cliente_id: int,
        dados: modelo,  # type: ignore[valid-type]
        usuario: Usuario = Depends(usuario_atual),
        db: Session = Depends(get_db),
    ) -> Simulacao:
        cliente = obter_cliente(db, usuario, cliente_id)
        sim = _salvar(db, usuario, cliente, tipo, dados, executor(dados))
        db.commit()
        return sim

    router.add_api_route(f"/calculadoras/{rota}", previa, methods=["POST"], name=f"previa_{tipo}")
    router.add_api_route(
        f"/clientes/{{cliente_id}}/simulacoes/{rota}",
        salvar,
        methods=["POST"],
        response_model=SimulacaoSaida,
        status_code=status.HTTP_201_CREATED,
        name=f"salvar_{tipo}",
    )


for _tipo, (_modelo, _executor, _) in TIPOS_FASE2.items():
    _registrar(_tipo, _modelo, _executor)


@router.post("/calculadoras/salario-liquido")
def salario_liquido(dados: SalarioEntrada, _: Usuario = Depends(usuario_atual)) -> dict[str, Any]:
    return executar_salario(dados)
