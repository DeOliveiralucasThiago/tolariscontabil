# Publicar para testes, sem custo (Render + Neon + Brevo)

Objetivo: um endereço na internet (`https://tolaris-contabil.onrender.com`, por exemplo) para os testadores abrirem no
navegador, sem baixar nada. Serve para uma rodada de testes com **dados fictícios**, não para guardar a carteira real.

| Peça | Serviço gratuito | Para quê |
|---|---|---|
| Site + API | Render (plano Free) | Roda `Dockerfile.nuvem` (os dois num só container) |
| Banco | Neon (PostgreSQL) | Guarda os dados; não expira como o banco gratuito do Render |
| E-mail | Brevo (SMTP) | Convites, redefinição de senha e envio de relatórios |

Os limites e as exigências dos planos gratuitos mudam: confira nas páginas de cada serviço antes de começar.

## 1. Neon (banco)
1. Crie um projeto (região mais próxima, por exemplo `sa-east-1`, se houver).
2. Em **Connect**, desmarque **Connection pooling** e copie a **connection string** (`postgresql://usuario:senha@ep-...neon.tech/neondb?sslmode=require`).
   Pode colar do jeito que vem: o Tolaris converte sozinho para o driver certo.

## 2. Brevo (e-mail)
1. **Senders, domains & dedicated IPs → Senders**: cadastre e verifique o e-mail que será o remetente.
2. **SMTP & API → SMTP**: anote o **login** (`algo@smtp-brevo.com`) e gere uma **chave SMTP**.
   Servidor `smtp-relay.brevo.com`, porta `2525` (o plano gratuito do Render bloqueia a saída pelas portas 25, 465 e 587;
   se o e-mail falhar com `timed out`, é isso).
3. Com remetente de e-mail pessoal (Gmail etc.), parte dos e-mails pode cair no spam. Avise os testadores.

## 3. Render (site + API)
1. **New → Blueprint**, conecte o GitHub, escolha este repositório **e a branch** que contém `render.yaml`.
2. Preencha as variáveis pedidas:
   - `TOLARIS_DATABASE_URL`: a string do Neon;
   - `TOLARIS_EMAIL_REMETENTE`: `Tolaris Contábil <seu-email-verificado@exemplo.com>`;
   - `TOLARIS_SMTP_USUARIO` e `TOLARIS_SMTP_SENHA`: do Brevo;
   - `TOLARIS_URL_PUBLICA`: ainda não se sabe; coloque `https://temporario.onrender.com`.
3. Quando o Render criar o serviço, copie o endereço dele (`https://....onrender.com`), troque `TOLARIS_URL_PUBLICA`
   por esse endereço (Environment) e faça um novo deploy. Esse endereço é o que entra nos links dos e-mails.
4. O primeiro build leva alguns minutos. Ao terminar, `https://seu-endereco/api/saude` responde `{"status":"ok",...}`.

## 4. Conferir
- Crie a conta do escritório; use **Esqueci a senha** com seu e-mail e veja se o e-mail chega.
- Em **Configurações → Registro de atividades**, o IP do seu login deve ser o **seu**. Se aparecer outro (da
  hospedagem), ajuste `TOLARIS_PROXY_SALTOS` (tente `2`). O IP alimenta o limite de tentativas de login e o registro.

## O que esperar do plano gratuito
- O serviço **dorme após cerca de 15 minutos sem uso**; o primeiro acesso depois disso demora até cerca de um minuto.
  Avise os testadores ("se a tela demorar na primeira vez, aguarde"). Um monitor gratuito que acesse `/api/saude`
  a cada 10 minutos (UptimeRobot, por exemplo) evita o sono durante o horário do teste.
- O disco do container não é permanente: **tudo fica no Neon**. Não há pasta `dados`; logos e arquivos enviados vão para o banco.
- Cada atualização do código na branch gera um novo deploy automático.
- O backup do Neon fica por conta do plano dele; para tirar uma cópia, use `pg_dump` com a connection string.

## Cuidados
- O endereço é público: peça **dados fictícios** e ative a **verificação em duas etapas** nas contas de teste.
- Não use a hospedagem gratuita para dados reais de clientes. Para produção, veja a seção "Preparação para produção" do README.
- Sem uma proxy na frente que acrescente o IP de quem acessa (como a do Render), o cabeçalho `X-Forwarded-For` pode ser
  forjado; por isso `TOLARIS_PROXY_SALTOS=1` só vale atrás de uma hospedagem/proxy confiável.

## Kit de teste para os testadores
`kit-de-teste/` traz arquivos fictícios que entram no sistema do jeito que o roteiro descreve: clientes para importar,
12 meses de dados contábeis, notas XML (com 3 arquivos que devem ser recusados de propósito), um SPED e um arquivo de apoio
ao Enquadramento (cliente de serviços, números para preencher e seis CNAEs para procurar). O pacote
pronto para enviar é `kit-de-teste/Kit de teste Tolaris.zip`. Para refazê-lo: `python scripts/gerar_kit_teste.py`
(o teste `tests/api/test_kit_teste.py` confere que o kit continua importando).
