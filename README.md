# Tolaris Contábil

Plataforma SaaS para contadores: prospecção em minutos, planejamento tributário,
simulação da Reforma Tributária e relatórios para clientes.

Este repositório está na **Fase 0**: o **motor de cálculo** em Python, sem interface.
Ele é a base de tudo: as telas, os PDFs e os painéis vão consumir este pacote.

## O que o motor calcula

| Módulo | Conteúdo |
|---|---|
| `simples` | Simples Nacional: anexos I a V, 6 faixas, alíquota efetiva, fator R (com FGTS), CPP fora do DAS no Anexo IV, pró-labore mínimo para atingir 28% |
| `presumido` | Lucro Presumido trimestral: presunções por atividade, adicional de IRPJ, PIS/Cofins cumulativos, ISS/ICMS, INSS patronal, acréscimo da LC 224/2025 |
| `real` | Lucro Real anual (estimativa gerencial): PIS/Cofins não cumulativos com créditos, IRPJ + adicional, CSLL, prejuízo fiscal |
| `comparativo` | Comparação entre os três regimes e **simulação expressa** com 3 entradas (faturamento, folha, atividade) |
| `pessoa_fisica` | INSS 2025/2026, IRPF mensal com a redução da Lei 15.270/2025, retenção de 10% sobre dividendos, alíquota do IRPFM, pró-labore × dividendos |
| `reforma` | Transição IBS/CBS ano a ano (2025–2033) com créditos, redução setorial e alíquotas de referência configuráveis |

Todo resultado traz uma **memória de cálculo** (descrição, fórmula, valor e base legal
de cada passo) e **alertas** (premissas e limitações). As tabelas legais ficam em
`src/tolaris_motor/tabelas/*.json`, versionadas por vigência: quando a lei muda,
acrescenta-se uma vigência no JSON, sem mexer no código.

## Uso rápido

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

```python
from datetime import date
from tolaris_motor import simulacao_expressa, PerfilEmpresa, Atividade, comparar
from tolaris_motor import pessoa_fisica, reforma

# As "3 perguntas" da prospecção
print(simulacao_expressa(faturamento_mensal=50_000, folha_mensal=8_000,
                         atividade="servico_fator_r", pro_labore_mensal=5_000).resumo())

# Planejamento completo
perfil = PerfilEmpresa(Atividade.COMERCIO, receita_bruta_anual=2_000_000,
                       folha_clt_anual=240_000, pro_labore_anual=36_000,
                       compras_anual=1_200_000, despesas_creditaveis_anual=80_000)
comp = comparar(perfil)
for passo in comp.melhor.memoria:
    print(passo.descricao, passo.formula, passo.base_legal)

# Pró-labore x dividendos
a, b = pessoa_fisica.comparar_pro_labore_dividendos(20_000, date(2026, 1, 1), regime="presumido")

# Reforma Tributária
anos = reforma.simular(reforma.EntradaReforma(1_000_000, vende_mercadoria=True, compras_anual=600_000))
print(reforma.tabela_resumo(anos))
```

## Validação com contador

`validacao/casos_validacao.xlsx` traz 48 casos (empresas, PF, sócios e reforma) com os
valores do motor, a memória de cálculo e os alertas. O contador preenche a coluna
amarela "Valor correto" e a planilha mostra a diferença. Para regenerar:

```bash
.venv/bin/python scripts/gerar_planilha_validacao.py
```

Premissas, fontes e pontos em aberto: [`docs/premissas.md`](docs/premissas.md).

## Roteiro

- **Fase 0 (atual):** motor de cálculo testado e validado por contador.
- **Fase 1:** login, cadastro de clientes, prospecção com CNPJ, proposta em PDF com a marca do escritório.
- **Fase 2:** simulador da reforma e módulo PF na interface.
- **Fase 3:** painéis, portal do cliente, envio automático por e-mail, importação de XML/SPED.
- **Fase 4:** integrações (Serpro Integra Contador, ERPs), WhatsApp, assistente de IA.

> As estimativas não substituem a análise do contador responsável.
