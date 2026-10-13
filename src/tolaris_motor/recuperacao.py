"""Imposto pago a mais no Simples Nacional por não segregar receitas de produtos com PIS/Cofins
monofásico ou ICMS por substituição tributária (ST).

Quem revende esses produtos informa a receita deles separada no PGDAS-D e o programa deixa de
cobrar, sobre ela, a parcela de PIS/Cofins (monofásico) ou de ICMS (ST) da repartição da faixa.
Quando a receita vai toda junta, o cliente paga duas vezes. O motor identifica os itens das notas,
reconstrói a alíquota efetiva de cada mês e estima o quanto foi pago a mais.

Não sabemos o que foi de fato declarado no PGDAS-D: o resultado é um *indício* a ser conferido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import simples, tabelas
from .base import ZERO, D, Resultado, arredondar, brl, pct

BASE_LEGAL_MONOFASICO = "LC 123/2006, art. 18, §4º-A, I; Res. CGSN 140/2018, art. 25"
BASE_LEGAL_ST = "LC 123/2006, art. 13, §1º, XIII, a, e art. 18, §4º-A, I; Res. CGSN 140/2018, art. 25"
BASE_LEGAL_RBT12 = "LC 123/2006, art. 3º, §§ 1º e 2º, e art. 18, §1º"
BASE_LEGAL_PRAZO = "CTN, art. 168"


def _tabela(data: date) -> dict:
    return tabelas.vigente("monofasico", data)


# --- Classificação dos itens das notas ------------------------------------------------------
@dataclass(frozen=True)
class Item:
    """Campos de um item de nota de saída que importam para a classificação."""

    ncm: str | None = None
    cfop: str | None = None
    cst_icms: str | None = None
    """CST de 2 dígitos (regime normal) ou CSOSN de 3 dígitos (Simples)."""
    cst_pis: str | None = None
    cest: str | None = None


@dataclass(frozen=True)
class Classificacao:
    mono: str | None = None
    """``nota`` (CST PIS 04 na própria nota), ``ncm`` (NCM da lista) ou ``verificar`` (NCM de lista parcial)."""
    grupo: str | None = None
    """Id do grupo de NCM que bateu, quando houver."""
    st: str | None = None
    """``nota`` (CSOSN/CST/CFOP de ST na própria nota) ou ``cest`` (item com CEST, sem sinal de ST na nota)."""


def _so_digitos(valor: str | None) -> str:
    return "".join(c for c in (valor or "") if c.isdigit())


def grupo_do_ncm(ncm: str | None, data: date) -> dict | None:
    """Grupo cujo prefixo de NCM é o mais específico para o ``ncm`` informado."""
    ncm = _so_digitos(ncm)
    if not ncm:
        return None
    melhor, tamanho = None, 0
    for grupo in _tabela(data)["grupos"]:
        for prefixo in grupo["prefixos"]:
            if ncm.startswith(prefixo) and len(prefixo) > tamanho:
                melhor, tamanho = grupo, len(prefixo)
    return melhor


def classificar(item: Item, data: date) -> Classificacao:
    t = _tabela(data)
    cfop = _so_digitos(item.cfop)
    grupo = grupo_do_ncm(item.ncm, data)

    mono = None
    if cfop in t["cfop_venda_monofasico"]:
        if _so_digitos(item.cst_pis) in t["cst_pis_monofasico"]:
            mono = "nota"
        elif grupo is not None:
            mono = "ncm" if grupo["nivel"] == "lista" else "verificar"

    st = None
    if cfop in t["cfop_venda_st"]:
        cst = _so_digitos(item.cst_icms)
        sinais = t["st"]
        if cst in (sinais["csosn"] if len(cst) == 3 else sinais["cst"]) or cfop in sinais["cfop"]:
            st = "nota"
        elif _so_digitos(item.cest):
            st = "cest"
    return Classificacao(mono=mono, grupo=grupo["id"] if (grupo and mono) else None, st=st)


# --- Estimativa ------------------------------------------------------------------------------
@dataclass(frozen=True)
class MesBase:
    """Valores de um mês (em reais) já somados por nível de certeza."""

    competencia: str
    """AAAA-MM."""
    receita: Decimal
    """Receita bruta do mês (todas as vendas), usada para reconstruir o RBT12."""
    mono_nota: Decimal = ZERO
    mono_ncm: Decimal = ZERO
    mono_verificar: Decimal = ZERO
    st_nota: Decimal = ZERO
    st_cest: Decimal = ZERO


@dataclass
class MesRecuperacao:
    competencia: str
    receita: Decimal
    base_monofasico: Decimal
    """Provável: itens com CST PIS 04 na nota ou NCM da lista."""
    base_st: Decimal
    base_verificar: Decimal
    """Monofásico de lista parcial + ST só por CEST (não entram no valor provável)."""
    calculado: bool = False
    rbt12: Decimal = ZERO
    rbt12_estimado: bool = False
    faixa: int = 0
    aliquota_efetiva: Decimal = ZERO
    pct_pis_cofins: Decimal = ZERO
    pct_icms: Decimal = ZERO
    pis_cofins: Decimal = ZERO
    icms: Decimal = ZERO
    a_verificar: Decimal = ZERO

    @property
    def provavel(self) -> Decimal:
        return self.pis_cofins + self.icms


@dataclass
class Recuperacao:
    anexo: str
    meses: list[MesRecuperacao]
    pis_cofins: Decimal
    icms: Decimal
    a_verificar: Decimal
    economia_anual: Decimal
    """Média mensal dos últimos 12 meses analisados x 12 (quanto o cliente deixa de pagar por ano daqui para frente)."""
    resultado: Resultado

    @property
    def provavel(self) -> Decimal:
        return self.pis_cofins + self.icms


def _competencia_anterior(comp: str, meses: int) -> str:
    ano, mes = int(comp[:4]), int(comp[5:7])
    indice = ano * 12 + (mes - 1) - meses
    return f"{indice // 12:04d}-{indice % 12 + 1:02d}"


def _rbt12(competencia: str, receitas: dict[str, Decimal], primeira: str) -> tuple[Decimal, bool]:
    """RBT12 do mês: soma dos 12 meses anteriores; se o histórico importado é menor, anualiza a média."""
    anteriores = [_competencia_anterior(competencia, n) for n in range(1, 13)]
    cobertos = [c for c in anteriores if c >= primeira]  # meses dentro do período importado (ausente = sem venda)
    if len(cobertos) == 12:
        return sum((receitas.get(c, ZERO) for c in cobertos), ZERO), False
    if cobertos:
        soma = sum((receitas.get(c, ZERO) for c in cobertos), ZERO)
        return soma / len(cobertos) * 12, True
    return receitas.get(competencia, ZERO) * 12, True  # primeiro mês: sem histórico, anualiza o próprio mês


def estimar(meses: list[MesBase], anexo: str = "I") -> Recuperacao:
    """Estima o PIS/Cofins e o ICMS pagos a mais, mês a mês, para clientes do Anexo I ou II."""
    if anexo not in ("I", "II"):
        raise ValueError("A segregação de monofásico/ST se aplica a comércio (Anexo I) e indústria (Anexo II)")
    ordenados = sorted(meses, key=lambda m: m.competencia)
    receitas = {m.competencia: m.receita for m in ordenados}
    primeira = ordenados[0].competencia if ordenados else ""
    res = Resultado(titulo="Imposto pago a mais no Simples Nacional (estimativa)")
    saida: list[MesRecuperacao] = []
    fora_do_limite: list[str] = []
    sem_tabela: list[str] = []
    sem_icms_acima_sublimite: list[str] = []

    for m in ordenados:
        mes = MesRecuperacao(
            competencia=m.competencia,
            receita=m.receita,
            base_monofasico=m.mono_nota + m.mono_ncm,
            base_st=m.st_nota,
            base_verificar=m.mono_verificar + m.st_cest,
        )
        saida.append(mes)
        if mes.base_monofasico == 0 and mes.base_st == 0 and mes.base_verificar == 0:
            continue
        data = date(int(m.competencia[:4]), int(m.competencia[5:7]), 1)
        rbt12, estimado = _rbt12(m.competencia, receitas, primeira)
        try:
            n_faixa, _ = simples.faixa(anexo, rbt12, data)
            aliquota = simples.aliquota_efetiva(anexo, rbt12, data)
            fracoes = simples.partilha(anexo, rbt12, data)
        except ValueError as erro:
            (fora_do_limite if "excede" in str(erro) else sem_tabela).append(m.competencia)
            continue
        mes.calculado, mes.rbt12, mes.rbt12_estimado, mes.faixa, mes.aliquota_efetiva = True, rbt12, estimado, n_faixa, aliquota
        mes.pct_pis_cofins = fracoes["pis"] + fracoes["cofins"]
        mes.pct_icms = fracoes.get("icms", ZERO)
        mes.pis_cofins = arredondar(mes.base_monofasico * aliquota * mes.pct_pis_cofins)
        mes.icms = arredondar(mes.base_st * aliquota * mes.pct_icms)
        mes.a_verificar = arredondar(
            m.mono_verificar * aliquota * mes.pct_pis_cofins + m.st_cest * aliquota * mes.pct_icms
        )
        if mes.base_st > 0 and mes.pct_icms == 0:
            sem_icms_acima_sublimite.append(m.competencia)

    calculados = [m for m in saida if m.calculado]
    total_pc = sum((m.pis_cofins for m in calculados), ZERO)
    total_icms = sum((m.icms for m in calculados), ZERO)
    total_verificar = sum((m.a_verificar for m in calculados), ZERO)
    janela = [m for m in saida[-12:] if m.receita > 0 or m.calculado]
    anual = sum((m.provavel for m in janela), ZERO) / len(janela) * 12 if janela else ZERO

    res.tributos = {
        "PIS/Cofins pagos a mais (produtos monofásicos)": total_pc,
        "ICMS pago a mais (produtos com ST)": total_icms,
    }
    res.passo(
        "Meses com itens identificados",
        "meses com venda de produto monofásico ou com ST",
        D(len(calculados)),
        BASE_LEGAL_MONOFASICO,
    )
    res.passo(
        "Venda de itens monofásicos (provável)",
        "soma dos itens com CST PIS 04 ou NCM da lista",
        sum((m.base_monofasico for m in calculados), ZERO),
        BASE_LEGAL_MONOFASICO,
    )
    res.passo(
        "Venda de itens com ICMS-ST (provável)",
        "soma dos itens com CSOSN 500/201/202/203, CST 10/30/60/70 ou CFOP de ST",
        sum((m.base_st for m in calculados), ZERO),
        BASE_LEGAL_ST,
    )
    ultimo = next((m for m in reversed(calculados) if m.provavel > 0), None)
    if ultimo:
        rotulo = f"Exemplo: {ultimo.competencia[5:]}/{ultimo.competencia[:4]}"
        res.passo(f"{rotulo} - RBT12" + (" (estimado)" if ultimo.rbt12_estimado else ""),
                  "média dos meses importados x 12" if ultimo.rbt12_estimado else "soma da receita dos 12 meses anteriores",
                  ultimo.rbt12, BASE_LEGAL_RBT12)
        res.passo(f"{rotulo} - alíquota efetiva (faixa {ultimo.faixa})",
                  "(RBT12 x alíquota nominal - parcela a deduzir) / RBT12", ultimo.aliquota_efetiva,
                  "LC 123/2006, art. 18, §1º")
        res.passo(f"{rotulo} - PIS+Cofins na repartição da faixa", "% de PIS + % de Cofins da faixa",
                  ultimo.pct_pis_cofins, "LC 123/2006, Anexo I ou II (repartição)")
        res.passo(f"{rotulo} - PIS/Cofins pagos a mais",
                  f"{brl(ultimo.base_monofasico)} x {pct(ultimo.aliquota_efetiva, 4)} x {pct(ultimo.pct_pis_cofins, 2)}",
                  ultimo.pis_cofins, BASE_LEGAL_MONOFASICO)
        res.passo(f"{rotulo} - ICMS pago a mais",
                  f"{brl(ultimo.base_st)} x {pct(ultimo.aliquota_efetiva, 4)} x {pct(ultimo.pct_icms, 2)}",
                  ultimo.icms, BASE_LEGAL_ST)
    res.passo("PIS/Cofins pagos a mais no período", "soma dos meses", total_pc, BASE_LEGAL_MONOFASICO)
    res.passo("ICMS pago a mais no período", "soma dos meses", total_icms, BASE_LEGAL_ST)
    res.passo("Economia por ano daqui para frente", "média mensal dos últimos 12 meses x 12", anual,
              BASE_LEGAL_MONOFASICO)

    res.alerta("Indício, não certeza: a estimativa supõe que a receita desses itens foi declarada no PGDAS-D sem "
               "segregação. Confira o que foi declarado em cada mês antes de retificar.")
    res.alerta("A lista de NCM é inicial e precisa ser conferida na tabela oficial da Receita Federal; "
               "o NCM completo (subitem) define se o produto é monofásico.")
    if any(m.rbt12_estimado for m in calculados):
        res.alerta("Em meses sem 12 meses de histórico importado, o RBT12 foi estimado pela média das notas "
                   "importadas; importe mais meses ou confira o RBT12 no PGDAS-D.")
    if total_verificar > 0:
        res.alerta(f"Mais {brl(total_verificar)} em itens de lista parcial ou só com CEST: confirme o enquadramento "
                   "de cada produto antes de contar esse valor.")
    if sem_icms_acima_sublimite:
        res.alerta("Em " + ", ".join(sem_icms_acima_sublimite) + " o ICMS já é recolhido fora do DAS (receita acima de "
                   "R$ 3,6 milhões): não há economia de ICMS nesses meses.")
    if fora_do_limite:
        res.alerta("Meses ignorados por RBT12 acima do limite do Simples Nacional: " + ", ".join(fora_do_limite) + ".")
    if sem_tabela:
        res.alerta("Meses anteriores a 2018 não foram calculados (as tabelas do Simples começam em 2018): "
                   + ", ".join(sem_tabela) + ".")
    res.alerta("Valores recolhidos a maior podem ser compensados ou restituídos em até 5 anos "
               f"({BASE_LEGAL_PRAZO}); o cálculo cobre apenas o período importado.")

    return Recuperacao(
        anexo=anexo,
        meses=saida,
        pis_cofins=total_pc,
        icms=total_icms,
        a_verificar=total_verificar,
        economia_anual=arredondar(anual),
        resultado=res,
    )


def anexo_do_cliente(atividade: str | None) -> str | None:
    """Anexo do Simples para quem revende mercadoria: comércio = I, indústria = II."""
    return {"comercio": "I", "industria": "II"}.get(atividade or "")
