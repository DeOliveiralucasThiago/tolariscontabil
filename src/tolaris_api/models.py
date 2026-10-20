"""Modelos do banco. Toda entidade de negócio pertence a um escritório (multi-tenant)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from datetime import date

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, LargeBinary, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc)


class Escritorio(Base):
    __tablename__ = "escritorios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    contador_responsavel: Mapped[str | None] = mapped_column(String(200))
    crc: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(40))
    cor_primaria: Mapped[str] = mapped_column(String(7), default="#1F3A5F")
    logo: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    logo_mime: Mapped[str | None] = mapped_column(String(40))
    honorarios: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    """Tabela de honorários do escritório (base por regime, adicional por funcionário, adesão, serviços e validade)."""
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    usuarios: Mapped[list[Usuario]] = relationship(back_populates="escritorio")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    nome: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(300))
    papel: Mapped[str] = mapped_column(String(20), default="admin")
    ativo: Mapped[bool] = mapped_column(default=True)
    sessao_versao: Mapped[int] = mapped_column(default=0, server_default="0")
    """Muda ao trocar a senha ou desativar: invalida as sessões abertas."""
    totp_segredo_cifrado: Mapped[str | None] = mapped_column(Text)
    """Segredo do aplicativo autenticador (cifrado). Existe desde o início da configuração, mesmo antes de ativar."""
    totp_ativo: Mapped[bool] = mapped_column(default=False, server_default=false())
    totp_ultimo_passo: Mapped[int | None] = mapped_column(BigInteger)
    """Último intervalo de 30 s aceito: um código só vale uma vez."""
    codigos_recuperacao: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True))
    """Hashes (SHA-256) dos códigos de recuperação ainda não usados."""
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    escritorio: Mapped[Escritorio] = relationship(back_populates="usuarios")


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (UniqueConstraint("escritorio_id", "cnpj", name="uq_cliente_cnpj_por_escritorio"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    razao_social: Mapped[str] = mapped_column(String(250))
    nome_fantasia: Mapped[str | None] = mapped_column(String(250))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    cnae_principal: Mapped[str | None] = mapped_column(String(7))
    cnae_descricao: Mapped[str | None] = mapped_column(String(300))
    municipio: Mapped[str | None] = mapped_column(String(120))
    uf: Mapped[str | None] = mapped_column(String(2))
    atividade: Mapped[str | None] = mapped_column(String(30))
    regime_atual: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="prospect", index=True)
    contato_nome: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    telefone: Mapped[str | None] = mapped_column(String(40))
    observacoes: Mapped[str | None] = mapped_column(Text)
    cadastro_pendente: Mapped[bool] = mapped_column(default=False, server_default=false())
    """Veio de importação em lote só com o CNPJ: falta completar razão social, CNAE e atividade pela Receita."""
    criado_em: Mapped[datetime] = mapped_column(default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(default=agora, onupdate=agora)

    simulacoes: Mapped[list[Simulacao]] = relationship(
        back_populates="cliente", cascade="all, delete-orphan", order_by="Simulacao.criado_em.desc()"
    )


class Simulacao(Base):
    __tablename__ = "simulacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    tipo: Mapped[str] = mapped_column(String(20))
    titulo: Mapped[str] = mapped_column(String(200))
    entrada: Mapped[dict[str, Any]] = mapped_column(JSON)
    resultado: Mapped[dict[str, Any]] = mapped_column(JSON)
    versao_motor: Mapped[str] = mapped_column(String(20))
    publicada: Mapped[bool] = mapped_column(default=False, server_default="0")
    """Visível no portal do cliente."""
    publicada_em: Mapped[datetime | None] = mapped_column()
    honorarios: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    """Proposta de honorários anexada a esta simulação."""
    visto_primeira_em: Mapped[datetime | None] = mapped_column()
    visto_ultima_em: Mapped[datetime | None] = mapped_column()
    aberturas: Mapped[int] = mapped_column(default=0, server_default="0")
    """Vezes em que o cliente abriu o relatório no portal (aberturas seguidas em menos de 10 minutos contam uma)."""
    aceite_em: Mapped[datetime | None] = mapped_column()
    aceite_nome: Mapped[str | None] = mapped_column(String(200))
    aceite_ip: Mapped[str | None] = mapped_column(String(45))
    criado_em: Mapped[datetime] = mapped_column(default=agora, index=True)

    cliente: Mapped[Cliente] = relationship(back_populates="simulacoes")
    envios: Mapped[list[Envio]] = relationship(
        back_populates="simulacao", cascade="all, delete-orphan", order_by="Envio.criado_em.desc()"
    )


class TokenAcesso(Base):
    """Token de uso único (redefinição de senha, convite). Só o hash SHA-256 fica no banco."""

    __tablename__ = "tokens_acesso"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(200))
    nome: Mapped[str | None] = mapped_column(String(200))
    papel: Mapped[str | None] = mapped_column(String(20))
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    expira_em: Mapped[datetime] = mapped_column()
    usado_em: Mapped[datetime | None] = mapped_column()
    criado_em: Mapped[datetime] = mapped_column(default=agora)


class TentativaLogin(Base):
    __tablename__ = "tentativas_login"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    sucesso: Mapped[bool] = mapped_column()
    criado_em: Mapped[datetime] = mapped_column(default=agora, index=True)


class Envio(Base):
    """Registro de cada envio de relatório por e-mail."""

    __tablename__ = "envios"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    simulacao_id: Mapped[int] = mapped_column(ForeignKey("simulacoes.id", ondelete="CASCADE"), index=True)
    para: Mapped[str] = mapped_column(String(600))
    assunto: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20))
    erro: Mapped[str | None] = mapped_column(Text)
    enviado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    simulacao: Mapped[Simulacao] = relationship(back_populates="envios")


class PortalCliente(Base):
    """Link de acesso do cliente aos relatórios publicados. Só o hash do token fica no banco."""

    __tablename__ = "portais_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(default=agora)
    ultimo_acesso_em: Mapped[datetime | None] = mapped_column()


class CaixaCliente(Base):
    """Link para o cliente (ou seu emissor) enviar XML de notas sem login. Só o hash do token fica no banco."""

    __tablename__ = "caixas_cliente"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = mapped_column(default=agora)
    ultimo_envio_em: Mapped[datetime | None] = mapped_column()
    total_envios: Mapped[int] = mapped_column(default=0, server_default="0")
    total_notas: Mapped[int] = mapped_column(default=0, server_default="0")
    """Notas novas recebidas por este link (sem contar repetidas)."""


class CaixaEmail(Base):
    """Caixa de e-mail (IMAP) do escritório de onde saem as notas enviadas pelos clientes. A senha fica cifrada."""

    __tablename__ = "caixas_email"

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), unique=True)
    host: Mapped[str] = mapped_column(String(253))
    porta: Mapped[int] = mapped_column(default=993)
    usuario: Mapped[str] = mapped_column(String(254))
    senha_cifrada: Mapped[str] = mapped_column(Text)
    pasta: Mapped[str] = mapped_column(String(200), default="INBOX")
    ativo: Mapped[bool] = mapped_column(default=True)
    uid_validade: Mapped[int | None] = mapped_column(BigInteger)
    ultimo_uid: Mapped[int | None] = mapped_column(BigInteger)
    """Última mensagem já lida: a verificação segue dali, sem mexer nos "lidos" do e-mail."""
    ultima_verificacao_em: Mapped[datetime | None] = mapped_column()
    ultimo_resultado: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    criado_em: Mapped[datetime] = mapped_column(default=agora)


class FinanceiroMensal(Base):
    """Números contábeis do mês trazidos de planilha (receita, compras, folha...). Valores em centavos.

    Campo vazio (None) significa "a planilha não informou"; ao reimportar, só os campos informados são trocados.
    """

    __tablename__ = "financeiro_mensal"
    __table_args__ = (UniqueConstraint("cliente_id", "competencia", name="uq_financeiro_por_mes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    competencia: Mapped[str] = mapped_column(String(7))
    receita_centavos: Mapped[int | None] = mapped_column(BigInteger)
    compras_centavos: Mapped[int | None] = mapped_column(BigInteger)
    folha_centavos: Mapped[int | None] = mapped_column(BigInteger)
    pro_labore_centavos: Mapped[int | None] = mapped_column(BigInteger)
    despesas_creditaveis_centavos: Mapped[int | None] = mapped_column(BigInteger)
    outras_despesas_centavos: Mapped[int | None] = mapped_column(BigInteger)
    receita_exterior_centavos: Mapped[int | None] = mapped_column(BigInteger)
    """Parte da receita que é exportação (já em reais)."""
    variacao_cambial_centavos: Mapped[int | None] = mapped_column(BigInteger)
    """Ganho (positivo) ou perda (negativo) cambial do mês, em reais."""
    importado_em: Mapped[datetime] = mapped_column(default=agora)


class DocumentoFiscal(Base):
    """Documento importado (NF-e XML ou registro C100 do SPED). Valores em centavos."""

    __tablename__ = "documentos_fiscais"
    __table_args__ = (UniqueConstraint("cliente_id", "chave", name="uq_documento_por_cliente"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), index=True)
    origem: Mapped[str] = mapped_column(String(10))
    chave: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(10))
    """saida ou entrada, do ponto de vista do cliente."""
    modelo: Mapped[str | None] = mapped_column(String(4))
    data: Mapped[date] = mapped_column()
    competencia: Mapped[str] = mapped_column(String(7), index=True)
    participante_cnpj: Mapped[str | None] = mapped_column(String(14))
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    icms_centavos: Mapped[int] = mapped_column(BigInteger, default=0)
    ipi_centavos: Mapped[int] = mapped_column(BigInteger, default=0)
    pis_centavos: Mapped[int] = mapped_column(BigInteger, default=0)
    cofins_centavos: Mapped[int] = mapped_column(BigInteger, default=0)
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    itens: Mapped[list[ItemFiscal]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class ItemFiscal(Base):
    """Itens de uma nota de saída, somados por produto e tributação dentro do documento. Valores em centavos.

    Guarda os dados crus (NCM, CFOP, CST/CSOSN, CEST); a classificação em monofásico/ST é feita na
    hora da análise, para acompanhar as atualizações da tabela de produtos.
    """

    __tablename__ = "itens_fiscais"
    __table_args__ = (Index("ix_itens_fiscais_cliente_competencia", "cliente_id", "competencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"), index=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos_fiscais.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(10))
    competencia: Mapped[str] = mapped_column(String(7))
    ncm: Mapped[str | None] = mapped_column(String(8))
    cfop: Mapped[str | None] = mapped_column(String(4))
    cst_icms: Mapped[str | None] = mapped_column(String(3))
    """CST (2 dígitos) ou CSOSN (3 dígitos)."""
    cst_pis: Mapped[str | None] = mapped_column(String(2))
    cest: Mapped[str | None] = mapped_column(String(7))
    descricao: Mapped[str | None] = mapped_column(String(120))
    valor_centavos: Mapped[int] = mapped_column(BigInteger)
    """Valor do produto menos desconto."""
    quantidade_itens: Mapped[int] = mapped_column(default=1)


class RegistroAuditoria(Base):
    """Quem fez o quê e quando, por escritório. Só campos de contexto: nada de senha, token ou dado fiscal."""

    __tablename__ = "registros_auditoria"
    __table_args__ = (Index("ix_auditoria_escritorio_data", "escritorio_id", "criado_em"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    escritorio_id: Mapped[int] = mapped_column(ForeignKey("escritorios.id", ondelete="CASCADE"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    usuario_nome: Mapped[str | None] = mapped_column(String(260))
    """Nome e e-mail na hora do fato; sobra mesmo se o usuário for removido. Vazio para quem age sem login (link)."""
    acao: Mapped[str] = mapped_column(String(60), index=True)
    entidade: Mapped[str | None] = mapped_column(String(40))
    entidade_id: Mapped[int | None] = mapped_column()
    detalhe: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    criado_em: Mapped[datetime] = mapped_column(default=agora)
