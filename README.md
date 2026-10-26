# Tolaris Contábil

Plataforma SaaS para contadores: prospecção em minutos, planejamento tributário,
simulação da Reforma Tributária e relatórios para clientes.

Este repositório está na **Fase 3**: aplicação web multi-escritório sobre o motor de
cálculo, com Reforma Tributária, pessoa física, equipe, envio de relatórios por e-mail,
portal do cliente, importação de NF-e/SPED, recuperação de tributos (monofásico e ST), central de avisos, proposta de honorários com aceite pelo portal,
receitas do exterior, enquadramento do Simples (Anexo V ao III) com busca de CNAEs e as tabelas do Simples de 2027 a 2033.

## Estrutura

| Pasta | O que é |
|---|---|
| `src/tolaris_motor/` | Motor de cálculo tributário (Python puro, sem dependências) |
| `src/tolaris_api/` | API FastAPI: login, escritórios, clientes, CNPJ, simulações e PDF |
| `migrations/` | Migrações do banco (Alembic) |
| `web/` | Site em Next.js (React + TypeScript + Tailwind) |
| `e2e/` | Teste ponta a ponta no navegador (Playwright) |
| `tests/` | Testes do motor e da API (pytest) |
| `docs/` | Premissas e pontos para o contador validar, fontes da legislação, publicação na nuvem e teste na rede local |
| `scripts/` | Geradores: tabela de CNAEs, tabelas do Simples de 2027 a 2033, kit de teste e planilha de validação |
| `kit-de-teste/` | Arquivos fictícios para os testadores (clientes, dados contábeis, notas XML, SPED e apoio ao Enquadramento) |
| `validacao/` | Planilha de casos para o contador conferir os números do motor |
| `portatil/` | Versão portátil para Windows, montada e testada pelo GitHub Actions |

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
- **Simples na Reforma:** recolher IBS/CBS dentro do DAS ou por fora (regime regular), nos anos de 2027 a 2033
  (o contador escolhe quais comparar), com o peso das vendas a empresas (B2B), ponto de equilíbrio e créditos nas compras.
  O DAS e a fatia de IBS/CBS de cada ano vêm das tabelas da Resolução CGSN 190/2026.
- **Pessoa física:** "vale abrir CNPJ?" (autônomo × MEI × Simples × Presumido, com honorários
  contábeis), pró-labore × dividendos (Lei 15.270/2025) e salário líquido.
- Tudo pode ser **salvo no cliente** e vira **relatório em PDF** com a marca do escritório.

## Fase 3 e preparação para produção

- **Conta e segurança:** esqueci/redefinir senha por e-mail (link de uso único, 1 hora), troca de
  senha, sessões derrubadas ao trocar a senha ou desativar o usuário, limite de tentativas de login
  (5 por e-mail e 30 por IP a cada 15 minutos).
- **Equipe:** convites por e-mail (válidos por 7 dias), papéis administrador/membro, desativação;
  o escritório nunca fica sem administrador.
- **Envio por e-mail:** o relatório em PDF vai para o cliente em nome do escritório (respostas vão
  para o e-mail do escritório), com histórico de envios.
- **Portal do cliente:** link exclusivo por cliente com a marca do escritório, mostrando só os
  relatórios marcados como publicados; gerar um novo link desativa o anterior.
- **Movimento fiscal:** importação de XML de NF-e/NFC-e (soltos ou em ZIP) e do SPED Fiscal
  (EFD ICMS/IPI), sem duplicar notas; vendas, compras e tributos por mês; um clique leva os
  últimos 12 meses para o planejamento.
- **Recuperação de tributos:** a importação guarda os itens das vendas (NCM, CFOP, CST/CSOSN, CEST). O sistema
  identifica produtos com PIS/Cofins monofásico e ICMS-ST, reconstrói a alíquota efetiva de cada mês e estima o
  quanto o cliente do Simples pode ter pago a mais por não segregar a receita no PGDAS-D. Sai com gráfico, memória
  de cálculo e PDF, e entra no histórico e no portal do cliente. É um indício a conferir; a tabela de NCM é inicial.
- **Central de avisos:** acompanha a carteira toda: fator R abaixo (ou perto) de 28% com o ganho líquido de elevar o
  pró-labore, proximidade dos limites do MEI, do Simples e do Presumido, possível imposto pago a mais em produtos
  monofásicos e simulações que deixaram de valer por mudança de regra (com "Recalcular", que guarda a versão
  anterior e mostra o antes e o depois). Traz também a lista das mudanças na legislação já incorporadas ao motor.
- **Honorários na proposta:** o escritório cadastra a tabela (base por regime, adicional por funcionário, adesão,
  serviços e validade); cada simulação ganha uma proposta com valor sugerido e ajustável, que aparece no PDF junto com
  a economia estimada. No portal o cliente vê a proposta e a **aceita** com nome, data, hora e IP; o escritório
  recebe e-mail e um aviso, e a proposta aceita fica travada.
- **Confirmação de leitura e WhatsApp:** cada relatório mostra se e quando o cliente o abriu no portal, e a central de
  avisos lembra do que não foi aberto em 3 dias ou da proposta vista sem resposta. Ao gerar o link do portal, o botão
  "Enviar pelo WhatsApp" abre a conversa com o telefone do cliente e uma mensagem editável.
- **Notas sem atrito:** (1) o escritório gera, na aba Movimento fiscal, um **link de envio** por cliente: o cliente (ou o
  emissor dele) manda XML/ZIP/SPED sem criar conta e as notas entram sozinhas, sem duplicar; (2) **dados contábeis por
  planilha**: CSV ou XLSX exportado do sistema contábil, com mapeamento de colunas sugerido pelo cabeçalho, prévia,
  linhas inválidas explicadas e botão "Usar no planejamento" (últimos 12 meses ou média anualizada); (3) **caixa de
  e-mail (IMAP)** nas Configurações: os anexos que chegam nela são lidos, o cliente é identificado pelo CNPJ dentro do
  arquivo e a nota entra no movimento dele. A caixa só é lida (nada é apagado nem marcado como lido). Clientes ativos
  com notas paradas há mais de 2 meses ganham um aviso. **Não** há ainda download direto da SEFAZ (ver `docs/premissas.md`).
- **Importação de clientes em lote:** em Clientes > Importar planilha, um .csv ou .xlsx com uma linha por cliente
  (só o CNPJ é obrigatório; razão social, atividade, regime, e-mail, telefone e contato são opcionais). O sistema
  sugere as colunas, confere (novos, já cadastrados, repetidos, CNPJ inválido) antes de gravar e cria os clientes; os que
  vieram só com CNPJ são completados em lotes pela consulta de CNPJ (razão social, CNAE, atividade e regime), sem
  sobrescrever nada que o escritório digitou.
- **Planejado × realizado e projeção de limites:** a aba Acompanhamento do cliente compara o último planejamento com a
  receita, compras, folha e despesas dos últimos 12 meses (notas importadas e planilha contábil), refaz o comparativo
  de regimes com os números reais ("a recomendação ainda vale?"), mostra o fator R real e projeta o RBT12 pela tendência
  da receita: "no ritmo atual, passa do limite do Simples em out/26". A central de avisos usa a mesma projeção
  (junto aos avisos de limite) e avisa quando o realizado fugiu do planejado.
- **Segurança e LGPD:** verificação em duas etapas por aplicativo autenticador (com 8 códigos de recuperação, redefinição
  pelo administrador e sem atalho pelo "esqueci a senha"); registro de atividades por escritório (quem, o quê, quando e
  de que IP, com filtros e CSV); exportação completa dos dados de um cliente (JSON) e exclusão definitiva sem sobras, só
  para administradores; backup com verificação (SQLite e PostgreSQL) e backup diário automático no pacote portátil;
  cabeçalhos de segurança no site e na API.
- **Funil comercial:** a página Funil comercial mostra, para um período, quantas propostas de honorários foram criadas,
  enviadas (portal ou e-mail), abertas pelo cliente e aceitas, com a conversão de cada etapa, o valor mensal em cada uma, a
  taxa de aceite, o tempo médio até abrir e aceitar e a lista de propostas por urgência com a ação sugerida (enviar,
  lembrar, ligar, renovar). Conta uma proposta por cliente (a mais recente).
- **Tour de primeiro acesso e ajuda por tela:** no primeiro acesso, um tour guiado (balão e destaque sobre cada menu)
  explica para que serve cada área; o botão **? Ajuda**, no canto de qualquer tela, refaz o tour e explica os botões e as
  áreas da página aberta. Funciona no celular (abre o menu sozinho). O conteúdo está em `web/src/lib/tour.ts`; os alvos são
  achados por seletor ou pelo texto do botão, então um passo cujo botão sumiu aparece no centro da tela em vez de quebrar.
- **Enquadramento e CNAEs:** para empresa de serviços no Anexo V do Simples, a tela *Enquadramento* compara o caminho do pró-labore
  (fator R de 28%) com o de exercer, de fato, atividade do Anexo III (25%, 50%, 100% ou um percentual do contador). O cliente é
  escolhido na lista ou o CNPJ é digitado na própria tela: os CNAEs principal e secundários vêm da Receita, ficam guardados no cadastro
  e aparecem com o Anexo provável e a confiança de cada um. Há busca em todos os CNAEs, com as vedações do Simples, e PDF salvo no cliente.
  É um comparativo para o contador decidir; o Anexo vale pela atividade exercida (detalhes abaixo e em `docs/premissas.md`).

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

Para uma rodada de testes na internet, sem custo (Render + Neon + Brevo), veja
[`docs/publicar-na-nuvem.md`](docs/publicar-na-nuvem.md).

Para testar na rede do escritório (outros computadores e celulares acessando pelo IP da máquina),
siga o passo a passo em [`docs/teste-rede-local.md`](docs/teste-rede-local.md). Sem Docker, há uma
versão portátil para Windows (pasta `portatil/`), montada e testada pelo GitHub Actions.

### Configuração da API (variáveis `TOLARIS_*`)

| Variável | Padrão | Uso |
|---|---|---|
| `TOLARIS_DATABASE_URL` | `sqlite:///./tolaris.db` | Em produção: `postgresql+psycopg://...` |
| `TOLARIS_SECRET_KEY` | chave de desenvolvimento | Assina a sessão. Obrigatória (32+ caracteres) quando `TOLARIS_AMBIENTE=producao` |
| `TOLARIS_COOKIE_SECURE` | `false` | `true` atrás de HTTPS |
| `TOLARIS_BRASILAPI_URL` | BrasilAPI pública | Consulta de CNPJ |
| `TOLARIS_PTAX_URL` | serviço Olinda do Banco Central | Taxa PTAX para converter receita em moeda estrangeira |
| `TOLARIS_SESSAO_HORAS` | `12` | Duração da sessão |
| `TOLARIS_URL_PUBLICA` | `http://localhost:3000` | Endereço do site nos links enviados por e-mail |
| `TOLARIS_EMAIL_BACKEND` | `console` | `console` (não envia), `arquivo` (grava em `TOLARIS_EMAIL_PASTA`), `smtp` ou `resend` |
| `TOLARIS_EMAIL_REMETENTE` | `Tolaris Contábil <nao-responda@localhost>` | Remetente; o nome exibido vira "Escritório X via Tolaris" |
| `TOLARIS_SMTP_*` / `TOLARIS_RESEND_API_KEY` | — | Credenciais do provedor de e-mail |
| `TOLARIS_IMPORTACAO_MAX_MB` | `25` | Limite por envio de arquivos fiscais |
| `TOLARIS_IMAP_AUTOMATICO` | só em produção | Liga a leitura periódica das caixas de e-mail; sem valor, liga quando `TOLARIS_AMBIENTE=producao` |
| `TOLARIS_IMAP_INTERVALO_MINUTOS` | `10` | Intervalo da leitura automática (0 desliga) |
| `TOLARIS_IMAP_PERMITIR_REDE_PRIVADA` | `false` | Aceita servidor IMAP em rede interna e portas diferentes de 993 (por padrão é bloqueado contra SSRF) |
| `TOLARIS_PROXY_SALTOS` | `0` (compose e portátil: `1`) | Quantos proxies confiáveis ficam na frente da API; define de onde sai o IP do cliente (limite de login e registro de atividades) |
| `TOLARIS_AUDITORIA_RETENCAO_MESES` | `24` | Tempo de guarda do registro de atividades |
| `TOLARIS_AMBIENTE_TESTE` | desligado | Variável do **site** (Next): com `true`, mostra a barra "Ambiente de testes" no topo de todas as telas |

### Backup e restauração

```bash
# Cria o backup (SQLite: cópia consistente mesmo com o sistema aberto; PostgreSQL: pg_dump, precisa do postgresql-client)
python -m tolaris_api.backup criar --destino /var/backups/tolaris --manter 14
# Confere um arquivo; no PostgreSQL, --restaurar-em faz uma restauração de verdade num banco temporário e o apaga
python -m tolaris_api.backup verificar /var/backups/tolaris/tolaris-AAAAMMDD-HHMMSS.dump --restaurar-em postgresql+psycopg://usuario:senha@servidor/postgres
```

Agende o `criar` (cron ou Agendador de Tarefas) e copie a pasta para outro lugar: backup guardado só no mesmo servidor não
protege contra a perda do servidor. Teste a restauração de tempos em tempos. O backup tem dados pessoais e fiscais e **não é
criptografado pelo Tolaris**: guarde-o em disco ou nuvem com criptografia. Para restaurar: SQLite, pare o sistema e
substitua o arquivo do banco pela cópia; PostgreSQL, `pg_restore --clean --no-owner -d tolaris arquivo.dump`. Depois suba a
API (as migrações rodam sozinhas). Use a mesma `TOLARIS_SECRET_KEY`: sem ela, a senha da caixa de e-mail e os códigos de
verificação em duas etapas guardados no banco não podem ser lidos (o usuário reconfigura).

### Segurança adotada

- Senhas com scrypt (biblioteca padrão do Python); login com tempo constante para e-mail inexistente.
- Sessão em cookie `httpOnly` + `SameSite=Lax`; o JavaScript do site nunca vê o token.
- Toda consulta filtra pelo escritório do usuário (testado: um escritório não acessa dados de outro).
- Logo validada pelo conteúdo (PNG/JPG, até 512 KB).
- Tokens de redefinição, convite e portal: 256 bits aleatórios; no banco fica só o hash SHA-256.
- Importação fiscal: XML lido com `defusedxml` (sem XXE nem "billion laughs"), ZIP com limites de
  quantidade e tamanho, CNPJ do cliente conferido em cada documento.
- Verificação em duas etapas (TOTP) opcional por usuário, com códigos de recuperação em hash, uso único e limite de
  tentativas; o segredo e a senha da caixa de e-mail ficam cifrados (Fernet, chave derivada de `TOLARIS_SECRET_KEY`).
- Registro de atividades (24 meses) com IP, sem senha nem token; exportação e exclusão de dados de cliente (LGPD) só para
  administradores.
- Links públicos (portal e envio de notas): só o hash no banco, limite de envios por hora, sem acesso a mais nada.
- Caixa de e-mail (IMAP): só TLS na porta 993, servidor validado contra SSRF, caixa aberta somente para leitura.
- Cabeçalhos de segurança no site e na API; planilhas exportadas protegidas contra injeção de fórmula.
- O gerador de PDF só aceita recursos embutidos (`data:`); nunca busca URLs (evita SSRF),
  e textos do cliente são escapados no HTML e no CSS do rodapé.

## O que o motor calcula

| Módulo | Conteúdo |
|---|---|
| `simples` | Simples Nacional: anexos I a V, 6 faixas, alíquota efetiva, fator R (com FGTS, ou a folha informada pelo contador), CPP fora do DAS no Anexo IV, pró-labore mínimo para atingir 28%; parte da receita em atividade do Anexo III; **receita do exterior** (exportação) com a alíquota de cada mercado pelo seu próprio RBT12, sem ISS/ICMS/IPI e PIS/Cofins (de 2027, sem CBS/IBS/ICMS/ISS/IPI); tabelas de 2018 a 2026 e de **2027 a 2033** (CBS e IBS na partilha, teto de ISS decrescente) |
| `enquadramento` | Caminhos do Anexo V ao III: pró-labore até o fator R de 28% (com o INSS do sócio) e parte da receita no Anexo III, cada um comparado nos três regimes |
| `cnae` | Catálogo de 1.334 subclasses do IBGE com vedações do Simples (Resolução CGSN 140/2018) e Anexo provável de cada CNAE, com o nível de confiança |
| `recuperacao` | Imposto pago a mais no Simples por produtos monofásicos e ICMS-ST, mês a mês, a partir dos itens das notas |
| `projecao` | Projeção do RBT12 pela tendência da receita, para avisar quando um limite será atingido |
| `avisos` | Fator R, limites do MEI, do Simples e do Presumido e simulações que deixaram de valer por mudança de regra |
| `presumido` | Lucro Presumido trimestral: presunções por atividade, adicional de IRPJ, PIS/Cofins cumulativos, ISS/ICMS, INSS patronal, acréscimo da LC 224/2025; exportação fora de PIS/Cofins/ISS/ICMS e **variação cambial** ativa na base |
| `real` | Lucro Real anual (estimativa gerencial): PIS/Cofins não cumulativos com créditos, IRPJ + adicional, CSLL, prejuízo fiscal; exportação e variação cambial (ganho soma, perda deduz) |
| `comparativo` | Comparação entre os três regimes e **simulação expressa** com 3 entradas (faturamento, folha, atividade) |
| `reforma_simples` | Simples na Reforma: partilha do DAS de cada ano (2027 a 2033), IBS/CBS no DAS × por fora, ponto de equilíbrio B2B |
| `autonomo` | Autônomo (carnê-leão) × MEI × Simples × Presumido, valores mensais |
| `pessoa_fisica` | INSS 2025/2026, IRPF mensal com a redução da Lei 15.270/2025, retenção de 10% sobre dividendos, alíquota do IRPFM, pró-labore × dividendos |
| `reforma` | Transição IBS/CBS ano a ano (2025–2033) com créditos, redução setorial e alíquotas de referência configuráveis |

**Receitas do exterior:** o planejamento completo, a simulação expressa e a planilha de dados contábeis aceitam a parte da receita
que vem do exterior e a variação cambial; a tela traz um conversor de moeda pela PTAX do Banco Central, com todas as moedas que ele cota (a taxa pode ser trocada à mão).
A partir de 2027 o DAS da receita exportada deixa de contar CBS e IBS (e ICMS, ISS e IPI), conforme a LC 123, art. 18, §§ 14 e 14-A.
As premissas e o que o contador precisa validar estão em `docs/premissas.md` (itens 60 a 68 e 75).

**Enquadramento (Anexo V → III):** a tela *Enquadramento* compara, para empresa de serviços do fator R, a situação de hoje com
o pró-labore que leva o fator R a 28% e com parte da receita em atividade do Anexo III, mostra os CNAEs do cliente (principal e
secundários da Receita) e gera o PDF. Há também uma busca em todos os CNAEs do IBGE (1.334 subclasses) com o Anexo provável, as
vedações do Simples (Anexos VI e VII da Resolução CGSN 140/2018) e a fonte de cada informação; a tabela fica em
`src/tolaris_motor/tabelas/cnae.json` e é refeita por `scripts/gerar_tabela_cnae.py`. Só vale se a atividade for exercida de
fato; veja os itens 69 a 71 de `docs/premissas.md`. O Anexo de cada CNAE é uma referência (tabela comercial, com selo de confiança
na tela): a Resolução CGSN 140/2018 define o Anexo pela descrição da atividade, não pelo código.

**Simples de 2027 a 2033:** `simples_nacional.json` traz as tabelas da Resolução CGSN 190/2026 (CBS e IBS na partilha do DAS, teto de ISS
decrescente de 5% a 3% até 2032 e fim do ISS em 2033), geradas por `scripts/gerar_simples_2027.py`; o Simples na Reforma e o cálculo do
Simples usam a tabela da data. A simulação completa e o comparativo entre regimes seguem limitados a 2025 e 2026, porque Lucro Presumido e
Lucro Real ainda calculam PIS/Cofins (a transição desses regimes está na calculadora da Reforma). Veja o item 75 de `docs/premissas.md`.

**Legislação lida:** LC 123/2006 (texto completo), LC 214/2025 (pontos do Simples), LC 227/2026 e LC 238/2026 (MEI de R$ 110 mil em 2027 e
R$ 140 mil em 2028) e as Resoluções CGSN 190, 191, 194 e 195 (itens 71 a 75 de `docs/premissas.md`). `docs/fontes-da-legislacao.md` diz onde
cada texto foi lido e o que cada fonte entrega. O feed de mudanças (`tabelas/mudancas.json`) marca o que ainda não entrou no cálculo
(por exemplo, os limites do MEI de 2027 em diante). Leis e instruções normativas que não foram lidas no texto original (Leis 9.249 e 9.430,
Decreto 9.580/2018, INs da Receita) constam só por resumos e precisam de conferência.

**Fora do escopo (decisão do produto):** folha de pagamento dos clientes e split payment não serão implementados no Tolaris. A "folha" que o
motor usa é só o dado de entrada do cálculo (salários e encargos, para o fator R e o INSS patronal).

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

`validacao/casos_validacao.xlsx` traz 85 casos (empresas, PF, sócios, reforma, Simples na reforma de 2027 a 2033, enquadramento do Anexo V ao III, autônomo × CNPJ, recuperação de tributos e avisos de fator R) com os
valores do motor, a memória de cálculo e os alertas. O contador preenche a coluna
amarela "Valor correto" e a planilha mostra a diferença. Para regenerar:

```bash
.venv/bin/python scripts/gerar_planilha_validacao.py
```

Premissas, fontes e pontos em aberto: [`docs/premissas.md`](docs/premissas.md).

## Teste com contadores

Para uma rodada de testes com usuários, publique o ambiente conforme [`docs/publicar-na-nuvem.md`](docs/publicar-na-nuvem.md) e entregue o
roteiro de teste junto com o `kit-de-teste/Kit de teste Tolaris.zip` (clientes, dados contábeis, notas XML e SPED do Mercadinho Estrela, a
Consultoria Aurora, o apoio do Enquadramento, o apoio da Reforma Tributária e da Pessoa física, e a planilha de validação). Tudo é fictício. Para refazer o kit: `python scripts/gerar_kit_teste.py`; o teste
`tests/api/test_kit_teste.py` confere que ele continua entrando no sistema e que a ferramenta cumpre o que o arquivo de apoio promete.
As capturas de tela da apresentação saem de `e2e/capturas_apresentacao.mjs` (veja `e2e/README.md`).

## Roteiro

- **Fase 0 (concluída):** motor de cálculo testado; validação com contador em andamento.
- **Fase 1 (concluída):** login, cadastro de clientes, prospecção com CNPJ, proposta em PDF com a marca do escritório.
- **Fase 2 (concluída):** simulador da reforma, Simples na reforma e módulo de pessoa física, com relatórios em PDF.
- **Fase 3 (atual):** equipe, recuperação de senha, envio por e-mail, portal do cliente, importação de XML/SPED, recuperação de tributos (monofásico e ST), central de avisos, recálculo por mudança de regra, honorários na proposta, leitura e aceite no portal, receitas do exterior, enquadramento do Simples com busca de CNAEs e tabelas do Simples de 2027 a 2033.
- **Próximos:** cobrança da assinatura, NFS-e, resumo semanal dos avisos por e-mail, envio recorrente, limites do MEI de 2027 em diante nos avisos.
- **Fase 4:** integrações (Serpro Integra Contador, ERPs), WhatsApp, assistente de IA.

> As estimativas não substituem a análise do contador responsável.
