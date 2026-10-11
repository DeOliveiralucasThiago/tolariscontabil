from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Escritorio, Usuario
from ..schemas import EscritorioAtualizar, SessaoSaida
from ..seguranca import usuario_atual
from .auth import sessao

router = APIRouter(prefix="/escritorio", tags=["escritório"])

_TIPOS_LOGO = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def _somente_admin(usuario: Usuario) -> None:
    if usuario.papel != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas administradores podem alterar o escritório")


@router.patch("", response_model=SessaoSaida)
def atualizar(
    dados: EscritorioAtualizar, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> SessaoSaida:
    _somente_admin(usuario)
    esc = usuario.escritorio
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(esc, campo, valor)
    db.commit()
    return sessao(usuario)


@router.put("/logo", response_model=SessaoSaida)
async def enviar_logo(
    arquivo: UploadFile, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)
) -> SessaoSaida:
    _somente_admin(usuario)
    limite = get_settings().logo_max_bytes
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Logo deve ter até {limite // 1024} KB")
    mime = next((m for assinatura, m in _TIPOS_LOGO.items() if conteudo.startswith(assinatura)), None)
    if mime is None:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Envie a logo em PNG ou JPG")
    esc = usuario.escritorio
    esc.logo, esc.logo_mime = conteudo, mime
    db.commit()
    return sessao(usuario)


@router.delete("/logo", response_model=SessaoSaida)
def remover_logo(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> SessaoSaida:
    _somente_admin(usuario)
    esc = usuario.escritorio
    esc.logo, esc.logo_mime = None, None
    db.commit()
    return sessao(usuario)


@router.get("/logo")
def obter_logo(usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)) -> Response:
    esc = db.get(Escritorio, usuario.escritorio_id)
    if esc is None or esc.logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escritório sem logo")
    return Response(esc.logo, media_type=esc.logo_mime, headers={"Cache-Control": "private, max-age=60"})
