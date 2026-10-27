"""Gera o kit de teste para os testadores: planilhas e notas de um cliente fictício.

    python scripts/gerar_kit_teste.py            # grava em kit-de-teste/ (com o pacote "Kit de teste Tolaris.zip")

Tudo é inventado, exceto os CNPJ de grandes empresas públicas da lista de clientes (servem para testar a consulta
por CNPJ). O cliente fictício "Mercadinho Estrela" usa um CNPJ válido, mas que não existe na Receita.
Os arquivos são conferidos com os mesmos leitores do sistema, então o que sai daqui entra no Tolaris.
"""

from __future__ import annotations

import random
import shutil
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "kit-de-teste"

CLIENTE = "12345678000195"
CLIENTE_NOME = "Mercadinho Estrela Ltda"
CLIENTE_SERVICOS = "98765432000198"
CLIENTE_SERVICOS_NOME = "Consultoria Aurora Ltda"
FORNECEDORES = {"11444777000161": "Distribuidora Boa Compra Ltda", "11222333000181": "Atacado Preço Justo Ltda"}
CLIENTES_FINAIS = ["45997418000153", "11444777000161", "11222333000181"]

# (descrição, NCM, CFOP, CSOSN, CST PIS, faixa de valor em reais)
PRODUTOS_MONOFASICOS = [
    ("Refrigerante cola 2L (fardo)", "22021000", "5405", "500", "01", (900, 2400)),
    ("Cerveja lata 350ml (caixa)", "22030000", "5405", "500", "01", (1200, 3000)),
    ("Shampoo 350ml (caixa)", "33051000", "5102", "102", "01", (700, 1800)),
    ("Perfume 100ml (caixa)", "33030010", "5102", "102", "01", (900, 2200)),
    ("Analgésico 500mg (caixa)", "30049099", "5102", "102", "01", (800, 2000)),
]
PRODUTOS_COMUNS = [
    ("Arroz tipo 1 5kg (fardo)", "10063021", "5102", "102", "01", (1500, 3800)),
    ("Biscoito recheado (caixa)", "19053100", "5102", "102", "01", (800, 2000)),
    ("Sabão em pó 1kg (caixa)", "34022000", "5102", "102", "01", (600, 1500)),
    ("Café torrado 500g (fardo)", "09012100", "5102", "102", "01", (900, 2300)),
]

MESES_XML = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
MES_SPED = "2026-09"


def _dv_chave(base43: str) -> str:
    peso, soma = 2, 0
    for d in reversed(base43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return "0" if resto < 2 else str(11 - resto)


def _chave(competencia: str, cnpj: str, numero: int) -> str:
    aamm = competencia[2:4] + competencia[5:7]
    base = f"35{aamm}{cnpj}55001{numero:09d}1{numero * 7919 % 10**8:08d}"
    return base + _dv_chave(base)


def _moeda(v: Decimal) -> str:
    return f"{v:.2f}"


def _item_xml(n: int, descricao: str, ncm: str, cfop: str, csosn: str, cst_pis: str, valor: Decimal) -> str:
    return f"""    <det nItem="{n}"><prod><cProd>{n:03d}</cProd><xProd>{descricao}</xProd><NCM>{ncm}</NCM><CFOP>{cfop}</CFOP><uCom>CX</uCom><qCom>1.0000</qCom><vUnCom>{_moeda(valor)}</vUnCom><vProd>{_moeda(valor)}</vProd></prod>
      <imposto><ICMS><ICMSSN{csosn}><orig>0</orig><CSOSN>{csosn}</CSOSN></ICMSSN{csosn}></ICMS><PIS><PISAliq><CST>{cst_pis}</CST><vBC>{_moeda(valor)}</vBC><pPIS>0.0000</pPIS><vPIS>0.00</vPIS></PISAliq></PIS></imposto></det>"""


def nfe(competencia: str, numero: int, emit: str, dest: str, itens: list[tuple], dia: int = 10, status: str = "100",
        tp_nf: str = "1") -> tuple[str, bytes, Decimal]:
    chave = _chave(competencia, emit, numero)
    total = sum((i[5] for i in itens), Decimal(0))
    det = "\n".join(_item_xml(n, *item) for n, item in enumerate(itens, start=1))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{chave}" versao="4.00">
    <ide><mod>55</mod><serie>1</serie><nNF>{numero}</nNF><dhEmi>{competencia}-{dia:02d}T10:00:00-03:00</dhEmi><tpNF>{tp_nf}</tpNF></ide>
    <emit><CNPJ>{emit}</CNPJ></emit>
    <dest><CNPJ>{dest}</CNPJ></dest>
{det}
    <total><ICMSTot><vICMS>0.00</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vNF>{_moeda(total)}</vNF></ICMSTot></total>
  </infNFe></NFe>
  <protNFe><infProt><chNFe>{chave}</chNFe><cStat>{status}</cStat></infProt></protNFe>
</nfeProc>"""
    return chave, xml.encode(), total


def _itens_venda(rng: random.Random) -> list[tuple]:
    escolhidos = rng.sample(PRODUTOS_MONOFASICOS, 3) + rng.sample(PRODUTOS_COMUNS, 3)
    itens = []
    for desc, ncm, cfop, csosn, cst, (lo, hi) in escolhidos:
        itens.append((desc, ncm, cfop, csosn, cst, Decimal(rng.randrange(lo * 3, hi * 3, 10))))
    return itens


def gerar_notas() -> tuple[dict[str, bytes], dict[str, Decimal], list[str]]:
    """Retorna (arquivos do zip, receita por mês, linhas do SPED)."""
    rng = random.Random(2026)
    arquivos: dict[str, bytes] = {}
    receita: dict[str, Decimal] = {}
    numero = 100
    for i, comp in enumerate(MESES_XML):
        sazonal = Decimal("1.0") + Decimal("0.18") * (1 if comp.endswith(("-11", "-12")) else 0)
        total_mes = Decimal(0)
        for dia in (8, 22):
            numero += 1
            itens = [(*x[:5], (x[5] * sazonal).quantize(Decimal(1))) for x in _itens_venda(rng)]
            chave, xml, total = nfe(comp, numero, CLIENTE, CLIENTES_FINAIS[numero % 3], itens, dia=dia)
            arquivos[f"vendas/venda-{comp}-{dia:02d}.xml"] = xml
            total_mes += total
        receita[comp] = total_mes
        # uma compra por mês de um fornecedor (entrada: não vira receita)
        numero += 1
        forn = list(FORNECEDORES)[i % 2]
        itens = [("Mercadorias diversas para revenda", "22021000", "5102", "102", "01", Decimal(rng.randrange(36000, 60000, 100)))]
        _, xml, _ = nfe(comp, numero, forn, CLIENTE, itens, dia=5)
        arquivos[f"compras/compra-{comp}.xml"] = xml

    # Notas com problema de propósito: o sistema deve recusar e explicar
    itens = [("Item de teste", "19059090", "5102", "102", "01", Decimal(500))]
    _, xml, _ = nfe("2026-03", 900, CLIENTE, CLIENTES_FINAIS[0], itens, dia=15, status="101")
    arquivos["problemas-de-proposito/nota-cancelada.xml"] = xml
    _, xml, _ = nfe("2026-03", 901, "45997418000153", "11444777000161", itens, dia=15)
    arquivos["problemas-de-proposito/nota-de-outra-empresa.xml"] = xml
    arquivos["problemas-de-proposito/nao-e-nota.xml"] = b'<?xml version="1.0"?><pedido><item>caneta</item></pedido>'

    # SPED Fiscal de setembro/2026 (só as notas, sem itens)
    ini, fim = "01092026", "30092026"
    sped = [
        f"|0000|017|0|{ini}|{fim}|{CLIENTE_NOME.upper()}|{CLIENTE}||SP|123|3550308|||A|0|",
        "|0001|0|",
        f"|0150|C001|CLIENTE FINAL UM|01058|{CLIENTES_FINAIS[0]}||||||||",
        f"|0150|F001|{FORNECEDORES['11444777000161'].upper()}|01058|11444777000161||||||||",
    ]
    total_sped = Decimal(0)
    for n, (dia, valor) in enumerate([(3, 12540), (9, 19575), (17, 16020), (24, 21630), (29, 11880)], start=1):
        v = Decimal(valor)
        total_sped += v
        d = f"{dia:02d}092026"
        sped.append(f"|C100|1|0|C001|55|00|1|{500 + n}||{d}|{d}|{str(v).replace('.', ',')},00|0|0|0|{str(v).replace('.', ',')},00|9|0|0|0|0,00|0,00|0|0|0|0,00|0,00|0|0|")
    sped.append("|C100|0|1|F001|55|00|1|777||12092026|13092026|42800,00|0|0|0|42800,00|9|0|0|0|0,00|0,00|0|0|0|0,00|0,00|0|0|")
    sped.append("|9999|9|")
    receita[MES_SPED] = total_sped
    return arquivos, receita, sped


def gerar_planilha_contabil(receita: dict[str, Decimal]) -> bytes:
    from io import BytesIO

    rng = random.Random(7)
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados contábeis"
    cab = ["Competência", "Receita", "Compras", "Folha", "Pró-labore", "Despesas creditáveis", "Outras despesas"]
    ws.append(cab)
    for comp in sorted(receita):
        r = receita[comp]
        compras = (r * Decimal("0.58") + rng.randrange(-1500, 1500)).quantize(Decimal(1))
        ws.append([comp, float(r), float(compras), 14500.0, 4500.0, float(rng.randrange(1800, 2600, 50)), float(rng.randrange(5200, 7400, 50))])
    for c in range(1, len(cab) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(c)].width = 24
    for linha in ws.iter_rows(min_row=2, min_col=2, max_col=7):
        for cel in linha:
            cel.number_format = "#,##0.00"
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


def gerar_planilha_clientes() -> bytes:
    from io import BytesIO

    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    cab = ["CNPJ", "Razão social", "Atividade", "Regime", "E-mail", "Telefone", "Contato"]
    ws.append(cab)
    linhas = [
        ["12.345.678/0001-95", CLIENTE_NOME, "Comércio", "Simples Nacional", "contato@mercadinhoestrela.example", "(11) 98888-7777", "Dona Estrela"],
        ["98.765.432/0001-98", CLIENTE_SERVICOS_NOME, "Serviços fator R", "Simples Nacional", "contato@consultoriaaurora.example", "(11) 97777-6666", "Seu Álvaro"],
        # só o CNPJ: o sistema completa pela consulta (precisa de internet)
        ["00.000.000/0001-91", "", "", "", "", "", ""],
        ["33.000.167/0001-01", "", "", "", "", "", ""],
        ["47.960.950/0001-21", "", "", "", "", "", ""],
        ["07.526.557/0001-00", "", "", "", "", "", ""],
        ["33.592.510/0001-54", "", "", "", "", "", ""],
        ["71.673.990/0001-77", "", "", "", "", "", ""],
        ["16.670.085/0001-55", "", "", "", "", "", ""],
        # de propósito: um CNPJ errado e um repetido
        ["12.345.678/0001-96", "Empresa com CNPJ digitado errado", "Serviços", "MEI", "", "", ""],
        ["71.673.990/0001-77", "", "", "", "", "", ""],
    ]
    for linha in linhas:
        ws.append(linha)
    for c in range(1, len(cab) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
        ws.column_dimensions[get_column_letter(c)].width = 30
    for linha in ws.iter_rows(min_row=2, max_col=1):
        linha[0].number_format = "@"
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()


LEIA_ME = f"""KIT DE TESTE DO TOLARIS CONTÁBIL
================================

Tudo aqui é inventado. Use só estes arquivos no teste: não coloque dados de clientes reais.

Os clientes fictícios deste kit são o {CLIENTE_NOME} (CNPJ 12.345.678/0001-95, comércio no Simples Nacional) e a
{CLIENTE_SERVICOS_NOME} (CNPJ 98.765.432/0001-98, serviços no Simples Nacional). Os CNPJ são válidos, mas não existem na
Receita Federal; por isso a consulta pelo CNPJ não encontra esses clientes (os dados deles já vêm preenchidos na planilha).

ARQUIVOS

1) 1-clientes-para-importar.xlsx
   Para a tarefa C (Clientes > Importar planilha). Traz 11 linhas:
   - o Mercadinho Estrela (comércio), com todos os dados;
   - a Consultoria Aurora (serviços), com todos os dados, para a tarefa K (Enquadramento);
   - 7 CNPJ de grandes empresas públicas, só com o CNPJ, para testar "Completar pelo CNPJ" (precisa de internet);
   - 1 CNPJ errado e 1 repetido, de propósito: o sistema deve avisar.
   Depois de importar, abra o Mercadinho Estrela e mude a situação para Ativo.

2) 2-dados-contabeis-12-meses.xlsx
   Para a tarefa E (aba Dados contábeis do Mercadinho Estrela): receita, compras, folha, pró-labore e despesas de
   outubro/2025 a setembro/2026. Depois de importar, clique em "Usar no planejamento".

3) 3-notas-xml.zip
   Para a tarefa E (aba Movimento fiscal do Mercadinho Estrela): envie o arquivo .zip direto, sem descompactar.
   Traz 22 notas de venda e 11 de compra (outubro/2025 a agosto/2026). As vendas misturam refrigerante, cerveja,
   perfume, shampoo e remédio (produtos com PIS/Cofins monofásico) com arroz, café e biscoito. Por isso o cartão
   "Imposto pago a mais" deve mostrar um valor.
   Na pasta "problemas-de-proposito" há 3 arquivos que o sistema deve RECUSAR com uma explicação: uma nota
   cancelada, uma nota de outra empresa e um XML que não é nota.

4) 4-sped-fiscal-2026-09.txt
   Para a tarefa E também: SPED Fiscal de setembro/2026 do Mercadinho Estrela (cinco vendas e uma compra).

5) Para a tarefa D: use a aba Novo planejamento do Mercadinho Estrela. Os números de faturamento anual podem ser
   os de qualquer simulação sua; o regime atual é Simples Nacional.

6) 5-enquadramento-apoio.txt
   Para a tarefa K (Enquadramento): os números para preencher no cliente de serviços (Consultoria Aurora), o que a tela
   deve mostrar e seis CNAEs para procurar na busca, com o Anexo esperado de cada um.

7) 6-casos-de-validacao.xlsx
   Opcional, para quem for conferir os números do cálculo com a própria conta. São 127 casos (empresas nos três regimes,
   pessoa física, Reforma Tributária, Simples na Reforma de 2027 a 2033 e Enquadramento, casos ENQ1 a ENQ6). Cada caso traz
   o valor calculado pelo Tolaris, a memória de cálculo com a base legal e os avisos. Na aba "Casos", preencha a coluna
   amarela "Valor correto" com o que você apuraria: a diferença aparece sozinha. O ENQ1 é o mesmo caso do arquivo 5.

8) 7-reforma-e-pessoa-fisica-apoio.txt
   Para as tarefas L (Reforma Tributária e Simples de 2027 a 2033) e M (Pessoa física): os dados para preencher e os
   valores que a tela deve mostrar, ano a ano no caso do Simples na Reforma.

DICA: se algo for importado duas vezes, o sistema avisa e não soma de novo. Isso também é parte do teste.
"""


APOIO_ENQUADRAMENTO = f"""APOIO À TAREFA K: ENQUADRAMENTO (ANEXO V OU III) E BUSCA DE CNAEs
==============================================================

Tudo aqui é inventado. A {CLIENTE_SERVICOS_NOME} (CNPJ 98.765.432/0001-98) é um cliente de serviços que vem na planilha
1-clientes-para-importar.xlsx; ela não existe na Receita Federal, então a consulta pelo CNPJ não a encontra. Depois de
importar a planilha, escolha-a na lista "Cliente cadastrado" da tela Enquadramento.

DADOS PARA PREENCHER (campos da tela Enquadramento)
- Atividade: serviço com fator R (o padrão da tela)
- Receita bruta anual: R$ 600.000,00
- Folha CLT anual: R$ 0,00 (sem empregados)
- Pró-labore anual: R$ 36.000,00 (R$ 3.000,00 por mês)
- Outras despesas dedutíveis: R$ 60.000,00

O QUE DEVE APARECER (valores de referência; confira se a lógica faz sentido para você)
- Fator R de 6,00%: a empresa tributa hoje no Anexo V do Simples.
- Cenário "Pró-labore a mais até o fator R de 28%": cerca de R$ 11.000,00 a mais por mês, com o INSS de 11% somado como custo.
- Cenários de 25%, 50% e 100% da receita no Anexo III, com o aviso de que só valem se a empresa exerce de fato a atividade.
- Campo "Cenário próprio": digite 30 para ver o cenário de 30% da receita no Anexo III.

BUSCA DE CNAEs (use o campo de busca da própria tela e os filtros de Anexo)
Código       | Atividade                         | O que a tela deve mostrar
6201-5/01    | Desenvolvimento de software       | Anexo III ou V (fator R), selo "Tabela comercial"
7020-4/00    | Consultoria em gestão empresarial | Anexo III ou V (fator R), selo "Tabela comercial"
6911-7/01    | Serviços advocatícios             | Anexo IV
6421-2/00    | Bancos comerciais                 | Vedado ao Simples, selo "Resolução CGSN"
4781-4/00    | Comércio de roupas e acessórios   | Anexo I (comércio)
6920-6/01    | Atividades de contabilidade       | Anexo III, selo "Aproximado" (regra pela divisão, fora da tabela)

LEMBRETE: o Anexo de cada CNAE é uma referência. Quem decide é a descrição da atividade realmente exercida; o
Tolaris não troca o enquadramento de ninguém, só mostra o efeito de cada caminho no imposto.
"""


APOIO_REFORMA_PF = """APOIO ÀS TAREFAS L E M: REFORMA TRIBUTÁRIA, SIMPLES DE 2027 A 2033 E PESSOA FÍSICA
=============================================================================

Tudo aqui é inventado. Os valores abaixo são os que o Tolaris calcula hoje, com as alíquotas de referência estimadas de
CBS e IBS (a Reforma ainda não tem alíquotas oficiais). Se você mudar as alíquotas de referência, os números mudam.
Confira se a lógica faz sentido; quem decide é o contador.

TAREFA L (menu Reforma Tributária)

Aba "Transição 2025-2033": receita bruta anual R$ 1.000.000, vende mercadoria, compras de R$ 600.000.
- Tributos sobre o consumo: R$ 108.500 em 2025 e 2026, R$ 102.536 em 2027 e 2028, R$ 101.478 em 2029, R$ 100.420 em 2030,
  R$ 99.362 em 2031, R$ 98.304 em 2032 e R$ 91.955 em 2033 (carga de 11,74% em 2033).

Aba "Simples: IBS/CBS no DAS ou por fora": comércio, receita R$ 2.000.000, vendas a empresas (B2B) em 80%, compras de
fornecedores do regime regular de R$ 1.200.000. Por padrão a tela compara os sete anos, de 2027 a 2033. O "no DAS" é de
R$ 1.801.300 em todos os anos; o que muda é o "por fora" e a diferença a favor dele:

Ano       | Por fora compensa a partir de | Diferença a favor do "por fora" (por ano)
2027-2028 | 10% de vendas B2B             | R$ 84.191
2029      | 8%                            | R$ 101.591
2030      | 6%                            | R$ 119.088
2031      | 5%                            | R$ 136.675
2032      | 3%                            | R$ 154.347
2033      | qualquer % de vendas B2B      | R$ 261.870

Use o seletor "Anos a comparar": clique em "Limpar", tente comparar sem escolher nenhum ano (a tela avisa) e depois escolha só
2027 e 2030. O resultado deve trazer só esses dois anos.

TAREFA M (menu Pessoa física)

- Autônomo ou CNPJ: receita de R$ 15.000 por mês, despesas de R$ 1.000 e contabilidade de R$ 400. Sobra por mês: R$ 12.238 no
  Simples Nacional (melhor), R$ 10.647,99 no Lucro Presumido e R$ 9.829,78 como autônomo. O MEI não se aplica (a receita passa
  do limite). O ganho frente ao autônomo é de R$ 28.898,64 por ano.
- Pró-labore x dividendos: retirada mensal de R$ 20.000 no Lucro Presumido. O melhor caminho é pró-labore de R$ 1.621,00 mais
  dividendos: sobram R$ 19.821,69 por mês, contra R$ 14.732,81 com tudo como pró-labore (R$ 8.764,68 a mais por mês).
- Salário líquido: salário bruto de R$ 5.900,00. Líquido de R$ 4.924,35, com INSS de R$ 627,51 e IRRF de R$ 348,14.
"""


def main() -> None:
    SAIDA.mkdir(exist_ok=True)
    arquivos, receita, sped = gerar_notas()

    zip_notas = SAIDA / "3-notas-xml.zip"
    with zipfile.ZipFile(zip_notas, "w", zipfile.ZIP_DEFLATED) as zf:
        for nome, conteudo in sorted(arquivos.items()):
            zf.writestr(nome, conteudo)
    (SAIDA / "4-sped-fiscal-2026-09.txt").write_bytes("\r\n".join(sped).encode("latin-1"))
    (SAIDA / "2-dados-contabeis-12-meses.xlsx").write_bytes(gerar_planilha_contabil(receita))
    (SAIDA / "1-clientes-para-importar.xlsx").write_bytes(gerar_planilha_clientes())
    validacao = RAIZ / "validacao" / "casos_validacao.xlsx"
    shutil.copyfile(validacao, SAIDA / "6-casos-de-validacao.xlsx")
    (SAIDA / "5-enquadramento-apoio.txt").write_bytes(("﻿" + APOIO_ENQUADRAMENTO.replace("\n", "\r\n")).encode("utf-8"))
    (SAIDA / "7-reforma-e-pessoa-fisica-apoio.txt").write_bytes(("﻿" + APOIO_REFORMA_PF.replace("\n", "\r\n")).encode("utf-8"))
    (SAIDA / "LEIA-ME.txt").write_bytes(("﻿" + LEIA_ME.replace("\n", "\r\n")).encode("utf-8"))

    pacote = SAIDA / "Kit de teste Tolaris.zip"
    pacote.unlink(missing_ok=True)
    with zipfile.ZipFile(pacote, "w", zipfile.ZIP_DEFLATED) as zf:
        for arq in sorted(f for f in SAIDA.iterdir() if f != pacote):
            zf.write(arq, f"Kit de teste Tolaris/{arq.name}")
    print("Kit gerado em", SAIDA, "e", pacote.name)
    print("Receita por mês:", {k: float(v) for k, v in sorted(receita.items())})


if __name__ == "__main__":
    main()
