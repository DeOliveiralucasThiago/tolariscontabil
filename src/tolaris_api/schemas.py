"""Esquemas de entrada e saída da API (Pydantic)."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from tolaris_motor import Atividade

from .cnpj import cnpj_valido, so_digitos

Dinheiro = Decimal
Status = Literal["prospect", "ativo", "inativo"]
Regime = Literal["mei", "simples", "presumido", "real", "outro"]


# --- Honorários -----------------------------------------------------------------------------
class HonorariosConfig(BaseModel):
    """Tabela de honorários do escritório (valores mensais, exceto a adesão)."""

    base: dict[Literal["mei", "simples", "presumido", "real"], Dinheiro] = Field(default_factory=dict)
    por_funcionario: Dinheiro = Field(default=Decimal(0), ge=0, le=100000)
    adesao: Dinheiro = Field(default=Decimal(0), ge=0, le=1000000)
    servicos: str = Field(default="", max_length=2000)
    validade_dias: int = Field(default=15, ge=1, le=90)

    @field_validator("base")
    @classmethod
    def _base(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for valor in v.values():
            if valor < 0 or valor > 1000000:
                raise ValueError("Valor de honorários fora do intervalo")
        return v


class HonorariosEntrada(BaseModel):
    """Proposta de honorários de uma simulação; o que ficar em branco vem da tabela do escritório."""

    funcionarios: int = Field(default=0, ge=0, le=10000)
    valor_mensal: Dinheiro | None = Field(default=None, ge=0, le=1000000)
    adesao: Dinheiro | None = Field(default=None, ge=0, le=1000000)
    servicos: str | None = Field(default=None, max_length=2000)
    validade_dias: int | None = Field(default=None, ge=1, le=90)



# --- Autenticação -----------------------------------------------------------
class CadastroEntrada(BaseModel):
    escritorio_nome: str = Field(min_length=2, max_length=200)
    nome: str = Field(min_length=2, max_length=200)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=200)


class LoginEntrada(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    papel: str
    totp_ativo: bool = False


class EscritorioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    cnpj: str | None
    contador_responsavel: str | None
    crc: str | None
    email: str | None
    telefone: str | None
    cor_primaria: str
    tem_logo: bool = False
    honorarios: dict[str, Any] | None = None


class SessaoSaida(BaseModel):
    usuario: UsuarioSaida
    escritorio: EscritorioSaida


class EscritorioAtualizar(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=200)
    cnpj: str | None = None
    contador_responsavel: str | None = Field(default=None, max_length=200)
    crc: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=40)
    cor_primaria: str | None = None
    honorarios: HonorariosConfig | None = None

    @field_validator("cor_primaria")
    @classmethod
    def _cor(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("Cor deve estar no formato #RRGGBB")
        return v

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str | None) -> str | None:
        return _validar_cnpj_opcional(v)


def _validar_cnpj_opcional(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    d = so_digitos(v)
    if not cnpj_valido(d):
        raise ValueError("CNPJ inválido")
    return d


# --- Clientes ---------------------------------------------------------------
class CnaeItem(BaseModel):
    codigo: str = Field(min_length=7, max_length=7, pattern=r"^\d{7}$")
    descricao: str = Field(default="", max_length=300)


class ClienteBase(BaseModel):
    razao_social: str = Field(min_length=2, max_length=250)
    nome_fantasia: str | None = Field(default=None, max_length=250)
    cnpj: str | None = None
    cnae_principal: str | None = Field(default=None, max_length=7)
    cnae_descricao: str | None = Field(default=None, max_length=300)
    cnaes_secundarios: list[CnaeItem] | None = Field(default=None, max_length=200)
    municipio: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, max_length=2)
    atividade: Atividade | None = None
    regime_atual: Regime | None = None
    status: Status = "prospect"
    contato_nome: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=40)
    observacoes: str | None = Field(default=None, max_length=5000)

    @field_validator("cnpj")
    @classmethod
    def _cnpj(cls, v: str | None) -> str | None:
        return _validar_cnpj_opcional(v)

    @field_validator("email", mode="before")
    @classmethod
    def _email_vazio(cls, v: Any) -> Any:
        return None if v == "" else v


class ClienteEntrada(ClienteBase):
    pass


class ClienteAtualizar(ClienteBase):
    razao_social: str | None = Field(default=None, min_length=2, max_length=250)  # type: ignore[assignment]
    status: Status | None = None  # type: ignore[assignment]


class ClienteSaida(ClienteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cadastro_pendente: bool = False
    criado_em: datetime
    atualizado_em: datetime
    total_simulacoes: int = 0
    ultima_simulacao_em: datetime | None = None


# --- CNPJ -------------------------------------------------------------------
class CnpjSaida(BaseModel):
    cnpj: str
    razao_social: str
    nome_fantasia: str | None
    situacao: str | None
    cnae_principal: str | None
    cnae_descricao: str | None
    cnaes_secundarios: list[CnaeItem] = Field(default_factory=list)
    municipio: str | None
    uf: str | None
    email: str | None
    telefone: str | None
    opcao_simples: bool | None
    opcao_mei: bool | None
    regime_sugerido: Regime | None
    atividade_sugerida: Atividade | None
    atividade_justificativa: str
    cnaes_classificados: dict[str, Any] = Field(default_factory=dict)


# --- Simulações -------------------------------------------------------------
class ExpressaEntrada(BaseModel):
    faturamento_mensal: Dinheiro = Field(gt=0)
    folha_mensal: Dinheiro = Field(ge=0)
    pro_labore_mensal: Dinheiro = Field(default=Decimal(0), ge=0)
    atividade: Atividade
    margem_lucro: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    receita_exterior_mensal: Dinheiro = Field(default=Decimal(0), ge=0)
    """Parte do faturamento mensal que vem do exterior (exportação), em reais."""
    ano: int = Field(default=2026, ge=2025, le=2033)
    reducao_ibs_cbs: Decimal = Field(default=Decimal(0), ge=0, le=1)
    """Redução de IBS e CBS a partir de 2027: 0, 0,3 (profissões regulamentadas), 0,6 (saúde) ou 1."""

    @field_validator("reducao_ibs_cbs")
    @classmethod
    def _reducao_valida(cls, v: Decimal) -> Decimal:
        if v not in (Decimal(0), Decimal("0.3"), Decimal("0.6"), Decimal(1)):
            raise ValueError("A redução de IBS e CBS deve ser 0%, 30%, 60% ou 100%")
        return v

    @model_validator(mode="after")
    def _exterior_cabe_no_faturamento(self) -> "ExpressaEntrada":
        if self.receita_exterior_mensal > self.faturamento_mensal:
            raise ValueError("A receita do exterior não pode passar do faturamento mensal")
        return self


class CompletaEntrada(BaseModel):
    atividade: Atividade
    receita_bruta_anual: Dinheiro = Field(gt=0)
    folha_clt_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    pro_labore_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    compras_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    despesas_creditaveis_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    outras_despesas_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    aliquota_iss: Decimal = Field(default=Decimal("0.05"), ge=0, le=Decimal("0.05"))
    aliquota_icms: Decimal = Field(default=Decimal("0.18"), ge=0, le=Decimal("0.35"))
    rat: Decimal = Field(default=Decimal("0.02"), ge=0, le=Decimal("0.06"))
    terceiros: Decimal = Field(default=Decimal("0.058"), ge=0, le=Decimal("0.10"))
    folha_fator_r_anual: Dinheiro | None = Field(default=None, ge=0)
    receita_exterior_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    """Parte da receita bruta que é exportação (de serviços ou de mercadorias), em reais."""
    variacao_cambial_anual: Dinheiro = Field(default=Decimal(0), ge=-Decimal("100000000000"), le=Decimal("100000000000"))
    """Variação cambial líquida do ano, em reais: positiva é ganho, negativa é perda."""
    receita_anexo_iii_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    """Parte da receita de serviços em atividade que tributa direto no Anexo III (só para a atividade do fator R)."""
    sociedade_profissionais: bool = False
    """Sociedade uniprofissional com ISS fixo por profissional (Lucro Presumido e Lucro Real)."""
    profissionais: int = Field(default=0, ge=0, le=1000)
    iss_fixo_por_profissional_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    iss_fixo_no_simples: bool = False
    """Escritório de serviços contábeis (Anexo III) que recolhe o ISS fixo ao Município também como optante do Simples."""
    servicos_hospitalares: bool = False
    """Presunção reduzida de serviços hospitalares no Lucro Presumido (IRPJ 8% e CSLL 12%)."""
    ano: int = Field(default=2026, ge=2025, le=2033)
    reducao_ibs_cbs: Decimal = Field(default=Decimal(0), ge=0, le=1)
    """Redução de IBS e CBS a partir de 2027: 0, 0,3 (profissões regulamentadas), 0,6 (saúde) ou 1."""

    @field_validator("reducao_ibs_cbs")
    @classmethod
    def _reducao_valida(cls, v: Decimal) -> Decimal:
        if v not in (Decimal(0), Decimal("0.3"), Decimal("0.6"), Decimal(1)):
            raise ValueError("A redução de IBS e CBS deve ser 0%, 30%, 60% ou 100%")
        return v

    @model_validator(mode="after")
    def _exterior_cabe_na_receita(self) -> "CompletaEntrada":
        mercadoria = self.atividade in (Atividade.COMERCIO, Atividade.INDUSTRIA)
        if self.sociedade_profissionais:
            if mercadoria:
                raise ValueError("O ISS fixo de sociedade de profissionais só vale para serviços")
            if self.profissionais < 1 or self.iss_fixo_por_profissional_anual <= 0:
                raise ValueError("Informe a quantidade de profissionais e o ISS fixo anual de cada um")
        if self.iss_fixo_no_simples and not (self.sociedade_profissionais and self.atividade is Atividade.SERVICO_ANEXO_III):
            raise ValueError("O ISS fixo no Simples é do escritório de serviços contábeis (Anexo III) e exige a sociedade de profissionais com ISS fixo")
        if self.servicos_hospitalares and mercadoria:
            raise ValueError("A presunção de serviços hospitalares só vale para serviços")
        if self.receita_exterior_anual > self.receita_bruta_anual:
            raise ValueError("A receita do exterior não pode passar da receita bruta anual")
        if self.receita_anexo_iii_anual > self.receita_bruta_anual:
            raise ValueError("A receita do Anexo III não pode passar da receita bruta anual")
        if self.receita_anexo_iii_anual and self.atividade is not Atividade.SERVICO_FATOR_R:
            raise ValueError("A receita separada do Anexo III só vale para a atividade \"serviços do fator R\"")
        return self


class EnquadramentoEntrada(CompletaEntrada):
    """Os dados da empresa como ela é hoje; o Tolaris compara os caminhos para o Anexo III."""

    percentual_anexo_iii: Decimal | None = Field(default=None, gt=0, le=1)
    """Parcela da receita que viria de atividade do Anexo III, para um cenário próprio além dos de 25%, 50% e 100%."""


class ProspeccaoEntrada(BaseModel):
    """Salva um prospect (ou reaproveita o cliente com o mesmo CNPJ) e sua simulação expressa."""

    cliente: ClienteEntrada
    simulacao: ExpressaEntrada


class SimulacaoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    tipo: str
    titulo: str
    entrada: dict[str, Any]
    resultado: dict[str, Any]
    versao_motor: str
    publicada: bool = False
    publicada_em: datetime | None = None
    honorarios: dict[str, Any] | None = None
    visto_primeira_em: datetime | None = None
    visto_ultima_em: datetime | None = None
    aberturas: int = 0
    aceite_em: datetime | None = None
    aceite_nome: str | None = None
    criado_em: datetime


class ProspeccaoSaida(BaseModel):
    cliente: ClienteSaida
    simulacao: SimulacaoSaida


class PainelSaida(BaseModel):
    clientes_ativos: int
    prospects: int
    simulacoes_mes: int
    economia_identificada_mes: float
    ultimas_simulacoes: list[dict[str, Any]]


# --- Fase 2: calculadoras ---------------------------------------------------------
Fracao = Decimal


class ReformaEntrada(BaseModel):
    receita_bruta_anual: Dinheiro = Field(gt=0)
    vende_mercadoria: bool
    pis_cofins_nao_cumulativo: bool = False
    compras_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    despesas_creditaveis_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    aliquota_icms: Fracao = Field(default=Decimal("0.18"), ge=0, le=Decimal("0.35"))
    aliquota_iss: Fracao = Field(default=Decimal("0.05"), ge=0, le=Decimal("0.05"))
    aliquota_ipi: Fracao = Field(default=Decimal(0), ge=0, le=Decimal("0.5"))
    iss_fixo_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    """ISS fixo anual total da sociedade uniprofissional (profissionais x valor de cada um); só para serviços."""
    reducao_setorial: Fracao = Field(default=Decimal(0), ge=0, le=1)
    fracao_credito_compras: Fracao = Field(default=Decimal(1), ge=0, le=1)
    cbs_referencia: Fracao | None = Field(default=None, ge=0, le=Decimal("0.2"))
    ibs_referencia: Fracao | None = Field(default=None, ge=0, le=Decimal("0.3"))

    @model_validator(mode="after")
    def _iss_fixo_so_em_servicos(self) -> "ReformaEntrada":
        if self.iss_fixo_anual and self.vende_mercadoria:
            raise ValueError("O ISS fixo de sociedade uniprofissional só vale para serviços")
        return self


class SimplesReformaEntrada(BaseModel):
    atividade: Atividade
    receita_bruta_anual: Dinheiro = Field(gt=0, le=Decimal("4800000"))
    percentual_b2b: Fracao = Field(ge=0, le=1)
    compras_creditaveis_anual: Dinheiro = Field(default=Decimal(0), ge=0)
    folha_fator_r_anual: Dinheiro | None = Field(default=None, ge=0)
    reducao_setorial: Fracao = Field(default=Decimal(0), ge=0, le=1)
    cbs_referencia: Fracao | None = Field(default=None, ge=0, le=Decimal("0.2"))
    ibs_referencia: Fracao | None = Field(default=None, ge=0, le=Decimal("0.3"))
    anos: list[int] = Field(default_factory=lambda: list(range(2027, 2034)), min_length=1, max_length=7)
    """Anos comparados (de 2027 a 2033); sem informar, todos."""

    @field_validator("anos")
    @classmethod
    def _anos_validos(cls, anos: list[int]) -> list[int]:
        if any(a < 2027 or a > 2033 for a in anos):
            raise ValueError("Anos disponíveis: 2027 a 2033")
        return sorted(set(anos))


class AutonomoEntrada(BaseModel):
    receita_mensal: Dinheiro = Field(gt=0)
    atividade: Atividade = Atividade.SERVICO_FATOR_R
    despesas_mensais: Dinheiro = Field(default=Decimal(0), ge=0)
    dependentes: int = Field(default=0, ge=0, le=20)
    iss_fixo_autonomo_mensal: Dinheiro = Field(default=Decimal(0), ge=0)
    aliquota_iss: Fracao = Field(default=Decimal("0.05"), ge=0, le=Decimal("0.05"))
    mei_permitido: bool = False
    contabilidade_mensal: Dinheiro = Field(default=Decimal(0), ge=0)


class ProLaboreEntrada(BaseModel):
    retirada_mensal: Dinheiro = Field(gt=0)
    regime: Literal["simples", "simples_anexo_iv", "presumido", "real"] = "presumido"
    pro_labore_otimizado: Dinheiro | None = Field(default=None, ge=0)


class SalarioEntrada(BaseModel):
    salario_bruto: Dinheiro = Field(gt=0)
    dependentes: int = Field(default=0, ge=0, le=20)
    pensao_alimenticia: Dinheiro = Field(default=Decimal(0), ge=0)


# --- Senha e equipe -------------------------------------------------------------------
class EsqueciSenhaEntrada(BaseModel):
    email: EmailStr


class RedefinirSenhaEntrada(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    senha: str = Field(min_length=8, max_length=200)


class AlterarSenhaEntrada(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=200)
    nova_senha: str = Field(min_length=8, max_length=200)


class ConviteEntrada(BaseModel):
    email: EmailStr
    nome: str | None = Field(default=None, max_length=200)
    papel: Literal["admin", "membro"] = "membro"


class ConviteSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    nome: str | None
    papel: str | None
    expira_em: datetime
    criado_em: datetime


class MembroSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    papel: str
    ativo: bool
    totp_ativo: bool = False
    criado_em: datetime


class EquipeSaida(BaseModel):
    membros: list[MembroSaida]
    convites: list[ConviteSaida]


class MembroAtualizar(BaseModel):
    papel: Literal["admin", "membro"] | None = None
    ativo: bool | None = None


class ConvitePublico(BaseModel):
    escritorio: str
    email: str
    nome: str | None
    papel: str | None


class AceitarConviteEntrada(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nome: str = Field(min_length=2, max_length=200)
    senha: str = Field(min_length=8, max_length=200)


# --- Fase 3: envio e portal -------------------------------------------------------------
class EnviarEntrada(BaseModel):
    para: list[EmailStr] = Field(min_length=1, max_length=5)
    assunto: str | None = Field(default=None, max_length=200)
    mensagem: str | None = Field(default=None, max_length=3000)


class EnvioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    para: str
    assunto: str
    status: str
    erro: str | None
    criado_em: datetime


class PublicarEntrada(BaseModel):
    publicada: bool


class PortalEstado(BaseModel):
    ativo: bool
    criado_em: datetime | None = None
    ultimo_acesso_em: datetime | None = None
    publicadas: int = 0


class PortalGerarEntrada(BaseModel):
    enviar_para: list[EmailStr] = Field(default_factory=list, max_length=5)
    mensagem: str | None = Field(default=None, max_length=3000)


class PortalLink(BaseModel):
    link: str
    enviado_para: list[str]
    envio_erro: str | None = None


class PortalSimulacao(BaseModel):
    id: int
    tipo: str
    titulo: str
    resultado: dict[str, Any]
    criado_em: datetime
    honorarios: dict[str, Any] | None = None
    aceite_em: datetime | None = None
    aceite_nome: str | None = None


class AceiteEntrada(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    confirmo: bool

    @field_validator("nome")
    @classmethod
    def _nome(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("confirmo")
    @classmethod
    def _confirmo(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Confirme que leu e aceita a proposta")
        return v


class AceiteSaida(BaseModel):
    aceite_em: datetime
    aceite_nome: str


class PortalPublico(BaseModel):
    escritorio: dict[str, Any]
    cliente: str
    simulacoes: list[PortalSimulacao]


# --- Fase 3: importação fiscal -----------------------------------------------------------
class ImportacaoSaida(BaseModel):
    importados: int
    duplicados: int
    atualizados: int = 0
    """Notas já importadas antes que receberam seus itens agora."""
    ignorados: list[dict[str, str]]
    total_ignorados: int
    competencias: list[str]


class MesMovimento(BaseModel):
    competencia: str
    saidas: float
    entradas: float
    icms: float
    ipi: float
    pis: float
    cofins: float
    documentos: int


class MovimentoSaida(BaseModel):
    meses: list[MesMovimento]
    receita_12m: float
    compras_12m: float
    meses_12m: int
    documentos: int


class RecuperacaoPedido(BaseModel):
    anexo: Literal["I", "II"] | None = None
    """Anexo do Simples; por padrão, o da atividade do cliente (comércio = I, indústria = II)."""


class RecuperacaoEntrada(BaseModel):
    """O que fica registrado na simulação salva."""

    anexo: Literal["I", "II"]
    periodo_inicio: str | None
    periodo_fim: str | None



# --- Caixa de envio de notas do cliente ----------------------------------------------------
class CaixaEstado(BaseModel):
    ativo: bool
    criado_em: datetime | None = None
    ultimo_envio_em: datetime | None = None
    total_envios: int = 0
    total_notas: int = 0


class CaixaGerarEntrada(BaseModel):
    enviar_para: list[EmailStr] = Field(default_factory=list, max_length=5)
    mensagem: str | None = Field(default=None, max_length=3000)


class CaixaLink(BaseModel):
    link: str
    enviado_para: list[str] = Field(default_factory=list)
    envio_erro: str | None = None


class CaixaPublica(BaseModel):
    escritorio: dict[str, Any]
    cliente: str
    limite_mb: int


# --- Dados contábeis por planilha -----------------------------------------------------------
class FinanceiroPrevia(BaseModel):
    cabecalhos: list[str]
    amostra: list[list[str]]
    total_linhas: int
    sugestao: dict[str, int | None]
    """Índice da coluna sugerida para cada campo (competencia, receita, compras...)."""
    rotulos: dict[str, str]


class FinanceiroMes(BaseModel):
    competencia: str
    receita: float | None
    compras: float | None
    folha: float | None
    pro_labore: float | None
    despesas_creditaveis: float | None
    outras_despesas: float | None
    receita_exterior: float | None = None
    variacao_cambial: float | None = None


class FinanceiroImportacaoSaida(BaseModel):
    meses_novos: int
    meses_atualizados: int
    competencias: list[str]
    ignoradas: list[dict[str, str | int]]
    total_ignoradas: int
    avisos: list[str]


class FinanceiroPlanejamento(BaseModel):
    """Totais para o formulário do planejamento: últimos 12 meses ou, com menos meses, a média anualizada."""

    meses: int
    anualizado: bool
    periodo_inicio: str
    periodo_fim: str
    receita_bruta_anual: float
    compras_anual: float
    folha_clt_anual: float
    pro_labore_anual: float
    despesas_creditaveis_anual: float
    outras_despesas_anual: float
    receita_exterior_anual: float = 0
    variacao_cambial_anual: float = 0


class FinanceiroSaida(BaseModel):
    meses: list[FinanceiroMes]
    planejamento: FinanceiroPlanejamento | None


# --- Caixa de entrada de notas por e-mail ---------------------------------------------------------------
class CaixaEmailEntrada(BaseModel):
    host: str = Field(min_length=3, max_length=253)
    porta: int = Field(default=993, ge=1, le=65535)
    usuario: str = Field(min_length=1, max_length=254)
    senha: str | None = Field(default=None, min_length=1, max_length=200)
    """Obrigatória na primeira vez e sempre que servidor, porta ou usuário mudam; senão mantém a guardada."""
    pasta: str = Field(default="INBOX", min_length=1, max_length=200)
    ativo: bool = True


class CaixaEmailSaida(BaseModel):
    configurada: bool
    host: str | None = None
    porta: int | None = None
    usuario: str | None = None
    pasta: str | None = None
    ativo: bool = False
    ultima_verificacao_em: datetime | None = None
    ultimo_resultado: dict[str, Any] | None = None
    automatico: bool = False
    intervalo_minutos: int = 0


# --- Importação de clientes em lote -------------------------------------------------------------
class ClientesPrevia(BaseModel):
    cabecalhos: list[str]
    amostra: list[list[str]]
    total_linhas: int
    sugestao: dict[str, int | None]
    rotulos: dict[str, str]


class ClientesLinha(BaseModel):
    linha: int
    cnpj: str | None
    situacao: str
    """novo, existente, repetido ou invalido."""
    motivo: str | None = None


class ClientesAnalise(BaseModel):
    novos: int
    existentes: int
    repetidos: int
    invalidos: int
    avisos: list[str]
    problemas: list[ClientesLinha]
    """Até 30 linhas que não serão importadas, com o motivo."""
    total_problemas: int


class ClientesImportacaoSaida(ClientesAnalise):
    criados: int
    pendentes: int
    """Clientes criados que ainda precisam completar o cadastro pelo CNPJ."""


class CompletarSaida(BaseModel):
    completados: int
    nao_encontrados: list[dict[str, str]]
    restantes: int
    indisponivel: bool


# --- Verificação em duas etapas -----------------------------------------------------------------------
class Requer2faSaida(BaseModel):
    requer_2fa: Literal[True] = True
    token_2fa: str


class Login2faEntrada(BaseModel):
    token_2fa: str = Field(min_length=10, max_length=2000)
    codigo: str = Field(min_length=6, max_length=32)


class SenhaEntrada(BaseModel):
    senha: str = Field(min_length=1, max_length=200)


class Configurar2faSaida(BaseModel):
    segredo: str
    uri: str
    qr_svg: str


class CodigoEntrada(BaseModel):
    codigo: str = Field(min_length=6, max_length=32)


class SenhaCodigoEntrada(CodigoEntrada):
    senha: str = Field(min_length=1, max_length=200)


class CodigosRecuperacaoSaida(BaseModel):
    codigos_recuperacao: list[str]


# --- Registro de atividades ---------------------------------------------------------------------------
class AuditoriaItem(BaseModel):
    id: int
    quando: datetime
    usuario: str | None
    acao: str
    rotulo: str
    entidade: str | None
    entidade_id: int | None
    detalhe: dict[str, Any] | None
    ip: str | None


class AuditoriaPagina(BaseModel):
    total: int
    itens: list[AuditoriaItem]
    acoes: list[dict[str, str]]
    """Todas as ações possíveis (código e rótulo) para o filtro."""
    retencao_meses: int
