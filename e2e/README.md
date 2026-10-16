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
