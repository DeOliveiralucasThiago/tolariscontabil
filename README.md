# Tolaris Contábil

Plataforma SaaS para contadores: prospecção em minutos, planejamento tributário,
simulação da Reforma Tributária e relatórios para clientes.

Este repositório está na **Fase 2**: aplicação web multi-escritório sobre o motor de
cálculo, com simulador da Reforma Tributária e módulo de pessoa física.

## Estrutura

| Pasta | O que é |
|---|---|
| `src/tolaris_motor/` | Motor de cálculo tributário (Python puro, sem dependências) |
| `src/tolaris_api/` | API FastAPI: login, escritórios, clientes, CNPJ, simulações e PDF |
| `migrations/` | Migrações do banco (Alembic) |
| `web/` | Site em Next.js (React + TypeScript + Tailwind) |
| `e2e/` | Teste ponta a ponta no navegador (Playwright) |
| `tests/` | Testes do motor e da API (pytest) |

## O que a aplicação faz (Fase 1)

- **Cadastro e login** de escritórios. Cada escritório só enxerga os próprios dados.
- **Marca do escritório:** logo, cor, CRC e contatos aplicados no sistema e nas propostas.
- **Prospecção rápida:** digita o CNPJ, a Receita preenche razão social, CNAE e município, e o
  sistema sugere a atividade (anexo do Simples). Com faturamento, folha e pró-labore, sai o
  comparativo Simples × Presumido × Real com gráfico, alertas e memória de cálculo.
- **Proposta em PDF** com logo e cor do escritório, comparativo, pontos de atenção,
  assinatura do contador e memória de cálculo completa.
- **Clientes:** cadastro, busca, situação (prospect/ativo/inativo), histórico de simulações
  e **planejamento completo** (compras, despesas creditáveis, ISS/ICMS).
- **Painel:** clientes, prospects, simulações do mês e economia identificada.

## Fase 2

- **Reforma Tributária — transição 2025–2033:** carga sobre o consumo ano a ano (PIS/Cofins,
  IPI e ICMS/ISS dando lugar a CBS e IBS), com créditos sobre compras, redução setorial
  (30%, 60%, alíquota zero) e alíquotas de referência ajustáveis.
- **Simples na Reforma:** recolher IBS/CBS dentro do DAS ou por fora (regime regular), em 2027 e
  2033, com o peso das vendas a empresas (B2B), ponto de equilíbrio e créditos nas compras.
- **Pessoa física:** "vale abrir CNPJ?" (autônomo × MEI × Simples × Presumido, com honorários
  contábeis), pró-labore × dividendos (Lei 15.270/2025) e salário líquido.
- Tudo pode ser **salvo no cliente** e vira **relatório em PDF** com a marca do escritório.

## Rodando localmente

```bash
# API
python -m venv .venv && .venv/bin/pip install -e ".[api,dev]"
.venv/bin/alembic upgrade head            # cria o banco SQLite (tolaris.db)
.venv/bin/uvicorn tolaris_api.main:app --reload --port 8000

# Site (outro terminal)
cd web && npm install && npm run dev      # http://localhost:3000
```

O site encaminha `/api/*` para a API (`TOLARIS_API_URL`, padrão `http://127.0.0.1:8000`).
A documentação interativa da API fica em http://localhost:8000/api/docs.

### Com Docker (PostgreSQL + API + site)

```bash
cp .env.example .env    # preencha POSTGRES_PASSWORD e TOLARIS_SECRET_KEY
docker compose up -d --build
```

### Configuração da API (variáveis `TOLARIS_*`)

| Variável | Padrão | Uso |
|---|---|---|
| `TOLARIS_DATABASE_URL` | `sqlite:///./tolaris.db` | Em produção: `postgresql+psycopg://...` |
| `TOLARIS_SECRET_KEY` | chave de desenvolvimento | Assina a sessão. Obrigatória (32+ caracteres) quando `TOLARIS_AMBIENTE=producao` |
| `TOLARIS_COOKIE_SECURE` | `false` | `true` atrás de HTTPS |
| `TOLARIS_BRASILAPI_URL` | BrasilAPI pública | Consulta de CNPJ |
| `TOLARIS_SESSAO_HORAS` | `12` | Duração da sessão |

### Segurança adotada

- Senhas com scrypt (biblioteca padrão do Python); login com tempo constante para e-mail inexistente.
- Sessão em cookie `httpOnly` + `SameSite=Lax`; o JavaScript do site nunca vê o token.
- Toda consulta filtra pelo escritório do usuário (testado: um escritório não acessa dados de outro).
- Logo validada pelo conteúdo (PNG/JPG, até 512 KB).
- O gerador de PDF só aceita recursos embutidos (`data:`); nunca busca URLs (evita SSRF),
  e textos do cliente são escapados no HTML e no CSS do rodapé.

## O que o motor calcula

| Módulo | Conteúdo |
|---|---|
| `simples` | Simples Nacional: anexos I a V, 6 faixas, alíquota efetiva, fator R (com FGTS), CPP fora do DAS no Anexo IV, pró-labore mínimo para atingir 28% |
| `presumido` | Lucro Presumido trimestral: presunções por atividade, adicional de IRPJ, PIS/Cofins cumulativos, ISS/ICMS, INSS patronal, acréscimo da LC 224/2025 |
| `real` | Lucro Real anual (estimativa gerencial): PIS/Cofins não cumulativos com créditos, IRPJ + adicional, CSLL, prejuízo fiscal |
| `comparativo` | Comparação entre os três regimes e **simulação expressa** com 3 entradas (faturamento, folha, atividade) |
| `reforma_simples` | Simples na Reforma: partilha do DAS, IBS/CBS no DAS × por fora, ponto de equilíbrio B2B |
| `autonomo` | Autônomo (carnê-leão) × MEI × Simples × Presumido, valores mensais |
| `pessoa_fisica` | INSS 2025/2026, IRPF mensal com a redução da Lei 15.270/2025, retenção de 10% sobre dividendos, alíquota do IRPFM, pró-labore × dividendos |
| `reforma` | Transição IBS/CBS ano a ano (2025–2033) com créditos, redução setorial e alíquotas de referência configuráveis |

Todo resultado traz uma **memória de cálculo** (descrição, fórmula, valor e base legal
de cada passo) e **alertas** (premissas e limitações). As tabelas legais ficam em
`src/tolaris_motor/tabelas/*.json`, versionadas por vigência: quando a lei muda,
acrescenta-se uma vigência no JSON, sem mexer no código.

## Uso rápido

```bash
python -m venv .venv && .venv/bin/pip install -e ".[api,dev]"
.venv/bin/pytest                      # motor + API (SQLite)
TOLARIS_TEST_DATABASE_URL=postgresql+psycopg://... .venv/bin/pytest tests/api   # API no PostgreSQL
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

`validacao/casos_validacao.xlsx` traz 64 casos (empresas, PF, sócios, reforma, Simples na reforma e autônomo × CNPJ) com os
valores do motor, a memória de cálculo e os alertas. O contador preenche a coluna
amarela "Valor correto" e a planilha mostra a diferença. Para regenerar:

```bash
.venv/bin/python scripts/gerar_planilha_validacao.py
```

Premissas, fontes e pontos em aberto: [`docs/premissas.md`](docs/premissas.md).

## Roteiro

- **Fase 0 (concluída):** motor de cálculo testado; validação com contador em andamento.
- **Fase 1 (concluída):** login, cadastro de clientes, prospecção com CNPJ, proposta em PDF com a marca do escritório.
- **Fase 2 (atual):** simulador da reforma, Simples na reforma e módulo de pessoa física, com relatórios em PDF.
- **Fase 3:** painéis, portal do cliente, envio automático por e-mail, importação de XML/SPED.
- **Fase 4:** integrações (Serpro Integra Contador, ERPs), WhatsApp, assistente de IA.

> As estimativas não substituem a análise do contador responsável.
