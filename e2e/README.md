# Teste ponta a ponta

Percorre o fluxo principal no navegador (cadastro, marca do escritório, prospecção
com consulta de CNPJ, proposta em PDF, planejamento completo, painel, celular e logout)
e salva capturas de tela em `e2e/saida/`.

```bash
# 1. BrasilAPI falsa (CNPJ 11.222.333/0001-81) — não depende de rede externa
python e2e/mock_brasilapi.py &

# 2. API com banco limpo apontando para a BrasilAPI falsa
export TOLARIS_DATABASE_URL=sqlite:///./e2e.db TOLARIS_BRASILAPI_URL=http://127.0.0.1:8099/api/cnpj/v1
alembic upgrade head && uvicorn tolaris_api.main:app --port 8000 &

# 3. Site
(cd web && npm run build && npm start) &

# 4. Fluxo
cd e2e && npm install && npx playwright install chromium && npm run fluxo
```

Rode sempre com um banco novo: o fluxo cadastra o e-mail `marcos@silva.com.br`.

O fluxo da Fase 2 (reforma, Simples na reforma, autônomo × CNPJ, pró-labore, salário líquido,
histórico do cliente e celular) usa um e-mail novo a cada execução:

```bash
node fluxo_fase2.mjs saida
```

O fluxo da Fase 3 (esqueci a senha, convite, importação, envio por e-mail e portal) lê os e-mails
de uma pasta. Suba a API com o backend de arquivo:

```bash
export TOLARIS_EMAIL_BACKEND=arquivo TOLARIS_EMAIL_PASTA=/tmp/emails TOLARIS_URL_PUBLICA=http://127.0.0.1:3000
uvicorn tolaris_api.main:app --port 8000 &
cd e2e && EMAIL_DIR=/tmp/emails node fluxo_fase3.mjs saida
```

O fluxo de recuperação de tributos (importa NF-e com itens, vê o imposto pago a mais, gera o relatório e o PDF)
também usa e-mail novo a cada execução e não precisa de e-mail nem da BrasilAPI:

```bash
node fluxo_recuperacao.mjs saida
```

O fluxo da central de avisos (fator R, MEI, painel, filtros, mudanças na legislação e recálculo) cria a carteira pela
API. O passo "simulação desatualizada" altera um resultado salvo no SQLite; informe o arquivo em `E2E_DB`:

```bash
E2E_DB=./e2e.db node fluxo_avisos.mjs saida
```

O fluxo de honorários (tabela do escritório, proposta na simulação, WhatsApp, leitura e aceite no portal, avisos)
também usa e-mail novo a cada execução:

```bash
node fluxo_honorarios.mjs saida
```

O fluxo de notas sem atrito (link de envio para o cliente sem login, planilha de dados contábeis com mapeamento de
colunas, caixa de e-mail nas Configurações e aviso de notas paradas) também usa e-mail novo a cada execução. A
verificação da caixa de e-mail tenta conectar de verdade e só confere que a falha aparece de forma legível; defina
`TOLARIS_IMAP_TIMEOUT_SEGUNDOS=3` na API para não esperar. O servidor IMAP de mentira está em `tests/api/test_caixa_email.py`.

```bash
node fluxo_notas.mjs saida
```

O fluxo de importação de clientes em lote (planilha com CNPJ, conferência, importação e complemento pela consulta de
CNPJ) precisa da BrasilAPI falsa (`python e2e/mock_brasilapi.py`, API com `TOLARIS_BRASILAPI_URL` apontando para ela):

```bash
node fluxo_clientes_lote.mjs saida
```

O fluxo do acompanhamento (planejado × realizado, recomendação com os números reais, projeção dos limites, avisos e
celular) cria a carteira pela API e também usa e-mail novo a cada execução:

```bash
node fluxo_acompanhamento.mjs saida
```

O fluxo de segurança (ativar a verificação em duas etapas pela tela, entrar com o código, código errado, código de
recuperação, registro de atividades com CSV, exportar e excluir os dados de um cliente e cabeçalhos HTTP) calcula o
código do autenticador no próprio teste e também usa e-mail novo a cada execução:

```bash
node fluxo_seguranca.mjs saida
```

O fluxo do funil comercial (quatro propostas em etapas diferentes, conversões, valores, ações sugeridas, filtros e celular)
cria tudo pela API, usa o portal do cliente para o aceite e também usa e-mail novo a cada execução:

```bash
node fluxo_funil.mjs saida
```

O fluxo do tour (abre sozinho no primeiro acesso, 11 passos, não reabre depois de concluído, "Ajuda desta tela" em todas as
páginas, balão junto do elemento certo e celular com o menu aberto pelo tour) força a abertura automática e também usa
e-mail novo a cada execução:

```bash
node fluxo_tour.mjs saida
```

O fluxo da receita do exterior (Anexos explicados no seletor, bloco opcional do planejamento, conversor de moeda pela PTAX,
variação cambial e planilha com colunas do exterior) precisa da PTAX falsa, que o `mock_brasilapi.py` também responde.
Suba a API com `TOLARIS_PTAX_URL`:

```bash
export TOLARIS_PTAX_URL=http://127.0.0.1:8099/ptax
node fluxo_exterior.mjs saida
```

O fluxo do enquadramento (CNAEs secundários vindos da Receita, classificação, comparação dos caminhos para o Anexo III e PDF)
usa o `mock_brasilapi.py` e um e-mail novo a cada execução:

```bash
node fluxo_enquadramento.mjs saida
```

As capturas da apresentação saem de `capturas_apresentacao.mjs` (escritório fictício completo) e de `capturas_apresentacao_extra.mjs`
(Simples na Reforma de 2027 a 2033, Pessoa física e Mudanças na legislação). Ambas pedem o site sem `TOLARIS_AMBIENTE_TESTE` e um banco novo.

O fluxo das sociedades de profissionais (ISS fixo no Presumido e no Real, serviços hospitalares e o bloco que não aparece para comércio)
não usa rede externa:

```bash
node fluxo_profissionais.mjs saida
```

O aviso do prazo da opção pelo regime regular de IBS/CBS (até 30/10/2026) aparece na Central de Avisos e abre o Simples na Reforma com a receita e a
atividade do cliente. O fluxo só roda até 30/10/2026; depois dessa data ele encerra sem testar nada:

```bash
node fluxo_regime_regular.mjs saida
```

O fluxo do Presumido e do Real a partir de 2027 (CBS e IBS no lugar de PIS e Cofins, redução de 30% e ano na prospecção) não usa rede externa:

```bash
node fluxo_regimes_2027.mjs saida
```

O fluxo das sociedades uniprofissionais na Reforma (ISS fixo na transição, profissão do art. 127 e planejamento de 2027) também não usa rede externa:

```bash
node fluxo_uniprofissional.mjs saida
```

O fluxo das atividades mistas (receita por Anexo no planejamento e no Enquadramento) também não usa rede externa:

```bash
node fluxo_atividades_mistas.mjs saida
```

O fluxo da natureza jurídica usa a BrasilAPI falsa e a API apontando para ela (como o fluxo principal):

```bash
node fluxo_natureza_juridica.mjs saida
```

O fluxo das segregações do art. 25 (locação de bens móveis, transporte intermunicipal e atividade mista) não usa rede externa:

```bash
node fluxo_segregacoes.mjs saida
```

O fluxo da conferência dos impedimentos do Simples (respostas, receita global, simulação e Central de Avisos) não usa rede externa:

```bash
node fluxo_impedimentos.mjs saida
```
