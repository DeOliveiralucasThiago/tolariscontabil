"""Conferência dos impedimentos do Simples Nacional (LC 123/2006, art. 3º, § 4º, e art. 17).

O Tolaris não tem como saber, sozinho, quem são os sócios, se a empresa deve ao INSS ou o que ela vende; por isso o contador responde às perguntas
no cadastro do cliente. Cada pergunta, respondida "sim", vira um impedimento. Três delas (art. 3º, § 4º, III, IV e V) só impedem quando a receita bruta
global (a da empresa mais a das outras empresas do sócio) passa do limite de R$ 4.800.000; sem a receita das outras empresas, o impedimento fica
"depende da receita". A natureza jurídica (sociedade por ações, cooperativa) é conferida à parte, em ``natureza_juridica``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .base import ZERO, D, Numero, brl

LIMITE_RECEITA_GLOBAL = D("4800000")
BASE_ART3 = "LC 123/2006, art. 3º, § 4º"
BASE_ART17 = "LC 123/2006, art. 17"


@dataclass(frozen=True)
class Pergunta:
    chave: str
    grupo: str
    texto: str
    base_legal: str
    ajuda: str = ""
    depende_da_receita_global: bool = False


PERGUNTAS: tuple[Pergunta, ...] = (
    # Sócios e participações (art. 3º, § 4º)
    Pergunta("socio_pessoa_juridica", "Sócios e participações", "Algum sócio é pessoa jurídica (outra empresa participa do capital)?",
             f"{BASE_ART3}, I"),
    Pergunta("participa_do_capital", "Sócios e participações", "A empresa participa do capital de outra pessoa jurídica?", f"{BASE_ART3}, VII",
             "Não impede a participação em cooperativas de crédito, centrais de compras, bolsas de subcontratação, consórcio do art. 50 e sociedade de propósito específico do art. 56 (art. 3º, § 5º)."),
    Pergunta("socio_exterior", "Sócios e participações", "Algum titular ou sócio é domiciliado no exterior?", f"{BASE_ART17}, II"),
    Pergunta("capital_publico", "Sócios e participações", "Entidade da administração pública (federal, estadual ou municipal) participa do capital?", f"{BASE_ART17}, III"),
    Pergunta("socio_empresario_ou_socio_de_outra", "Sócios e participações",
             "Algum sócio é inscrito como empresário ou é sócio de outra empresa que também tem tratamento diferenciado (Simples ou MEI)?", f"{BASE_ART3}, III",
             "Só impede se a receita bruta global (esta empresa mais as outras) passar de R$ 4,8 milhões.", True),
    Pergunta("socio_mais_de_10_por_cento", "Sócios e participações",
             "Algum sócio tem mais de 10% do capital de outra empresa que não é beneficiada pelo Simples?", f"{BASE_ART3}, IV",
             "Só impede se a receita bruta global passar de R$ 4,8 milhões.", True),
    Pergunta("socio_administrador_de_outra", "Sócios e participações",
             "Algum sócio é administrador (de fato ou de direito) de outra pessoa jurídica com fins lucrativos?", f"{BASE_ART3}, V",
             "Só impede se a receita bruta global passar de R$ 4,8 milhões.", True),
    Pergunta("pessoalidade_subordinacao", "Sócios e participações",
             "Os sócios têm, ao mesmo tempo, pessoalidade, subordinação e habitualidade com quem contrata o serviço (pejotização)?", f"{BASE_ART3}, XI"),
    Pergunta("cisao_5_anos", "Sócios e participações", "A empresa resulta de cisão ou desmembramento ocorrido nos últimos 5 anos-calendário?", f"{BASE_ART3}, IX"),
    Pergunta("filial_no_pais_de_matriz_exterior", "Sócios e participações",
             "É filial, sucursal, agência ou representação no Brasil de empresa com sede no exterior?", f"{BASE_ART3}, II"),
    Pergunta("filial_no_exterior", "Sócios e participações", "Tem filial, sucursal, agência ou representação no exterior?", f"{BASE_ART3}, XII"),
    # Atividade
    Pergunta("atividade_financeira", "Atividade",
             "Exerce atividade de banco, sociedade de crédito, financiamento e investimento, corretora ou distribuidora de valores e câmbio, arrendamento mercantil, seguros privados, capitalização ou previdência complementar?",
             f"{BASE_ART3}, VIII"),
    Pergunta("factoring_credito", "Atividade",
             "Explora, de forma cumulativa e contínua, factoring, gestão de crédito, administração de contas a pagar e a receber ou empréstimo com recursos próprios a micro e pequenas empresas?",
             f"{BASE_ART17}, I"),
    Pergunta("transporte_intermunicipal_passageiros", "Atividade",
             "Presta transporte intermunicipal ou interestadual de passageiros?", f"{BASE_ART17}, VI",
             "Não impede o transporte fluvial, o de característica urbana ou metropolitana e o fretamento contínuo em área metropolitana de estudantes ou trabalhadores."),
    Pergunta("energia_eletrica", "Atividade", "É geradora, transmissora, distribuidora ou comercializadora de energia elétrica?", f"{BASE_ART17}, VII"),
    Pergunta("automoveis_motos", "Atividade", "Importa ou fabrica automóveis ou motocicletas?", f"{BASE_ART17}, VIII"),
    Pergunta("importacao_combustiveis", "Atividade", "Importa combustíveis?", f"{BASE_ART17}, IX"),
    Pergunta("produtos_vedados", "Atividade",
             "Produz ou vende no atacado cigarros, charutos, armas, munições, explosivos, cerveja sem álcool ou bebidas alcoólicas?", f"{BASE_ART17}, X",
             "Há exceção para micro e pequenas cervejarias, vinícolas, produtores de licores e micro e pequenas destilarias."),
    Pergunta("cessao_mao_de_obra", "Atividade", "Realiza cessão ou locação de mão de obra?", f"{BASE_ART17}, XII",
             "Não impede quem atua nas atividades do Anexo IV (construção, vigilância, limpeza etc.), nos termos do art. 18, § 5º-H."),
    Pergunta("loteamento_incorporacao", "Atividade", "Dedica-se a loteamento ou incorporação de imóveis?", f"{BASE_ART17}, XIV"),
    Pergunta("locacao_imoveis_proprios", "Atividade", "Realiza atividade de locação de imóveis próprios?", f"{BASE_ART17}, XV",
             "Não impede a locação de imóveis para eventos, salões de festas e semelhantes, que é serviço do Anexo III."),
    # Regularidade
    Pergunta("debito_exigivel", "Regularidade", "Tem débito com o INSS ou com as Fazendas Públicas (federal, estadual ou municipal) com exigibilidade não suspensa?",
             f"{BASE_ART17}, V"),
    Pergunta("irregularidade_cadastral", "Regularidade", "Está sem inscrição ou com irregularidade em cadastro fiscal federal, estadual ou municipal, quando exigível?",
             f"{BASE_ART17}, XVI"),
)
POR_CHAVE = {p.chave: p for p in PERGUNTAS}
TITULOS = {
    "socio_pessoa_juridica": "Sócio pessoa jurídica no capital",
    "participa_do_capital": "Participação no capital de outra pessoa jurídica",
    "socio_exterior": "Titular ou sócio domiciliado no exterior",
    "capital_publico": "Entidade da administração pública no capital",
    "socio_empresario_ou_socio_de_outra": "Sócio empresário ou sócio de outra empresa com tratamento diferenciado, com receita global acima do limite",
    "socio_mais_de_10_por_cento": "Sócio com mais de 10% do capital de outra empresa não beneficiada, com receita global acima do limite",
    "socio_administrador_de_outra": "Sócio administrador de outra pessoa jurídica com fins lucrativos, com receita global acima do limite",
    "pessoalidade_subordinacao": "Sócios com pessoalidade, subordinação e habitualidade com o contratante",
    "cisao_5_anos": "Empresa resultante de cisão ou desmembramento nos últimos 5 anos",
    "filial_no_pais_de_matriz_exterior": "Filial, sucursal, agência ou representação de empresa com sede no exterior",
    "filial_no_exterior": "Filial, sucursal, agência ou representação no exterior",
    "atividade_financeira": "Atividade financeira, de seguros, capitalização ou previdência complementar",
    "factoring_credito": "Factoring, gestão de crédito ou empréstimo a micro e pequenas empresas",
    "transporte_intermunicipal_passageiros": "Transporte intermunicipal ou interestadual de passageiros",
    "energia_eletrica": "Geração, transmissão, distribuição ou comercialização de energia elétrica",
    "automoveis_motos": "Importação ou fabricação de automóveis e motocicletas",
    "importacao_combustiveis": "Importação de combustíveis",
    "produtos_vedados": "Produção ou venda no atacado de cigarros, armas, bebidas ou outros produtos vedados",
    "cessao_mao_de_obra": "Cessão ou locação de mão de obra",
    "loteamento_incorporacao": "Loteamento ou incorporação de imóveis",
    "locacao_imoveis_proprios": "Locação de imóveis próprios",
    "debito_exigivel": "Débito com o INSS ou as Fazendas Públicas com exigibilidade não suspensa",
    "irregularidade_cadastral": "Ausência de inscrição ou irregularidade em cadastro fiscal",
}


@dataclass(frozen=True)
class Achado:
    chave: str
    status: str
    """``impede`` ou ``depende_da_receita`` (confirmado, mas só impede com receita global acima do limite e a das outras empresas não foi informada)."""
    texto: str
    base_legal: str


def avaliar(
    respostas: dict[str, bool | None],
    receita_propria: Numero = 0,
    receita_outras_empresas: Numero | None = None,
) -> list[Achado]:
    """Impedimentos confirmados (resposta ``True``). As perguntas ``None`` ou ausentes não entram: veja ``pendentes``."""
    achados = []
    for chave, resposta in respostas.items():
        p = POR_CHAVE.get(chave)
        if p is None or resposta is not True:
            continue
        status = "impede"
        if p.depende_da_receita_global:
            if receita_outras_empresas is None:
                status = "depende_da_receita"
            elif D(receita_propria) + D(receita_outras_empresas) <= LIMITE_RECEITA_GLOBAL:
                continue  # a receita global não passa do limite: este impedimento não se aplica
        achados.append(Achado(chave, status, TITULOS[chave], p.base_legal))
    return achados


def pendentes(respostas: dict[str, bool | None]) -> list[Pergunta]:
    return [p for p in PERGUNTAS if respostas.get(p.chave) is None]


def textos_que_impedem(achados: list[Achado]) -> list[str]:
    """Descrições para o cálculo do Simples: só os que impedem de fato."""
    return [f"{a.texto} ({a.base_legal})" for a in achados if a.status == "impede"]


def receita_global(receita_propria: Numero, receita_outras_empresas: Numero | None) -> Decimal:
    return D(receita_propria) + (D(receita_outras_empresas) if receita_outras_empresas is not None else ZERO)


def resumo_receita_global(receita_propria: Numero, receita_outras_empresas: Numero | None) -> str:
    if receita_outras_empresas is None:
        return "Receita das outras empresas dos sócios não informada."
    return f"Receita global de {brl(receita_global(receita_propria, receita_outras_empresas))} (limite de {brl(LIMITE_RECEITA_GLOBAL)})."
