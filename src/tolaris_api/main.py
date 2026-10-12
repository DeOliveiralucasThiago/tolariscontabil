"""Aplicação FastAPI. Todas as rotas ficam sob /api (o frontend faz proxy para cá)."""

from __future__ import annotations

from fastapi import APIRouter, FastAPI

import tolaris_motor

from .config import get_settings
from .routers import auth, calculadoras, clientes, cnpj, escritorio, simulacoes

CHAVE_PADRAO = "dev-somente-local-troque-esta-chave-em-producao"


def criar_app() -> FastAPI:
    cfg = get_settings()
    if cfg.ambiente == "producao" and (cfg.secret_key == CHAVE_PADRAO or len(cfg.secret_key) < 32):
        raise RuntimeError("Defina TOLARIS_SECRET_KEY com pelo menos 32 caracteres em produção")

    app = FastAPI(
        title="Tolaris Contábil API",
        version=tolaris_motor.__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    api = APIRouter(prefix="/api")
    for r in (auth.router, escritorio.router, clientes.router, cnpj.router, simulacoes.router, calculadoras.router):
        api.include_router(r)

    @api.get("/saude", tags=["infra"])
    def saude() -> dict[str, str]:
        return {"status": "ok", "motor": tolaris_motor.__version__}

    app.include_router(api)
    return app


app = criar_app()
