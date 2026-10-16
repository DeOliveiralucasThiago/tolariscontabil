"""Aplicação FastAPI. Todas as rotas ficam sob /api (o frontend faz proxy para cá)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request

import tolaris_motor

from .acesso import ip_cliente
from .auditoria import ip_da_requisicao
from .caixa_email import automatico_ligado, iniciar_rotina
from .config import get_settings
from .db import SessionLocal
from .routers import acompanhamento, auth, auditoria, avisos, caixa, caixa_email, calculadoras, clientes, clientes_lote, cnpj, compartilhamento, dois_fatores, equipe, escritorio, financeiro, fiscal, honorarios, simulacoes

CHAVE_PADRAO = "dev-somente-local-troque-esta-chave-em-producao"


def criar_app() -> FastAPI:
    cfg = get_settings()
    if cfg.ambiente == "producao" and (cfg.secret_key == CHAVE_PADRAO or len(cfg.secret_key) < 32):
        raise RuntimeError("Defina TOLARIS_SECRET_KEY com pelo menos 32 caracteres em produção")
    if cfg.ambiente == "producao" and cfg.email_backend in ("console", "arquivo"):
        logging.getLogger("tolaris").warning(
            "TOLARIS_EMAIL_BACKEND=%s em produção: e-mails (senha, convites, relatórios) não serão entregues.",
            cfg.email_backend,
        )

    @asynccontextmanager
    async def ciclo_de_vida(_: FastAPI):
        parar = iniciar_rotina(SessionLocal) if automatico_ligado() else None
        try:
            yield
        finally:
            if parar is not None:
                parar.set()

    app = FastAPI(
        lifespan=ciclo_de_vida,
        title="Tolaris Contábil API",
        version=tolaris_motor.__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    @app.middleware("http")
    async def contexto_e_cabecalhos(request: Request, call_next):  # noqa: ANN001, ANN202
        token = ip_da_requisicao.set(ip_cliente(request))
        try:
            resposta = await call_next(request)
        finally:
            ip_da_requisicao.reset(token)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "same-origin")
        if request.url.path.startswith("/api/") and "cache-control" not in resposta.headers:
            resposta.headers["Cache-Control"] = "no-store"  # respostas da API têm dado do escritório: nada de cache
        return resposta

    api = APIRouter(prefix="/api")
    for r in (auditoria.router, acompanhamento.router, auth.router, dois_fatores.router, avisos.router, caixa.router, caixa_email.router, escritorio.router, clientes.router, clientes_lote.router, cnpj.router, simulacoes.router, calculadoras.router, equipe.router, compartilhamento.router, financeiro.router, fiscal.router, honorarios.router):
        api.include_router(r)

    @api.get("/saude", tags=["infra"])
    def saude() -> dict[str, str]:
        return {"status": "ok", "motor": tolaris_motor.__version__}

    app.include_router(api)
    return app


app = criar_app()
