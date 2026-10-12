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
