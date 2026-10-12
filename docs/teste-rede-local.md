# Teste na rede local (LAN)

Um computador do escritório roda o Tolaris e os outros computadores e celulares da mesma rede
(mesmo Wi-Fi ou cabo) acessam pelo navegador. Não há custo e nada fica exposto na internet.

O computador que roda o sistema precisa ficar ligado durante o uso. A consulta de CNPJ e o envio
de e-mail continuam precisando de internet nesse computador.

## 1. Instalar o Docker

Baixe e instale o **Docker Desktop** (Windows ou Mac): https://www.docker.com/products/docker-desktop/
No Windows, o instalador pede para ativar o WSL 2; aceite e reinicie se ele pedir.

## 2. Baixar o Tolaris

No GitHub, botão **Code → Download ZIP** no branch do projeto. Descompacte numa pasta, por exemplo
`C:\tolaris`.

## 3. Descobrir o endereço do computador na rede

- Windows: abra o **Prompt de Comando** e digite `ipconfig`. Anote o "Endereço IPv4" do adaptador
  em uso, algo como `192.168.0.15`.
- Mac: Ajustes do Sistema → Rede → Detalhes.

Se possível, fixe esse endereço no roteador (reserva de DHCP). Se ele mudar, os links já enviados
por e-mail deixam de funcionar.

## 4. Criar o arquivo `.env`

Na pasta do Tolaris, copie `.env.example` para `.env` e preencha:

```ini
POSTGRES_PASSWORD=uma-senha-qualquer-longa
# 48 ou mais caracteres aleatórios. No PowerShell:
#   [Convert]::ToBase64String((1..48 | % { Get-Random -Max 256 }))
TOLARIS_SECRET_KEY=cole-aqui-o-texto-gerado
TOLARIS_COOKIE_SECURE=false
TOLARIS_URL_PUBLICA=http://192.168.0.15:3000
```

### E-mail pelo Gmail (opcional, sem domínio próprio)

Para a recuperação de senha, os convites e o envio de relatórios funcionarem de verdade, dá para usar
uma conta Gmail. Ative a verificação em duas etapas na conta e crie uma **senha de app** em
https://myaccount.google.com/apppasswords. Depois:

```ini
TOLARIS_EMAIL_BACKEND=smtp
TOLARIS_EMAIL_REMETENTE=Tolaris Contábil <sua.conta@gmail.com>
TOLARIS_SMTP_HOST=smtp.gmail.com
TOLARIS_SMTP_PORTA=587
TOLARIS_SMTP_USUARIO=sua.conta@gmail.com
TOLARIS_SMTP_SENHA=a-senha-de-app-de-16-letras
```

O Gmail limita o volume diário de envios; para teste é suficiente. Sem essa configuração o sistema
funciona, mas nenhum e-mail sai (eles aparecem só no log: `docker compose logs api`).

## 5. Subir

Abra o terminal na pasta do Tolaris e rode:

```bash
docker compose up -d --build
```

A primeira vez leva alguns minutos. Depois, abra `http://192.168.0.15:3000` (com o seu endereço)
em qualquer computador ou celular da rede. Se o Windows perguntar sobre o firewall, permita o
acesso em **redes privadas**.

## Uso no dia a dia

| O quê | Comando |
|---|---|
| Parar | `docker compose stop` |
| Ligar de novo | `docker compose start` |
| Atualizar para uma versão nova (baixe o ZIP novo na mesma pasta) | `docker compose up -d --build` |
| Ver erros | `docker compose logs api` |
| Cópia de segurança do banco | `docker compose exec db pg_dump -U tolaris tolaris > backup.sql` |

Os dados ficam guardados no Docker e não se perdem ao parar ou atualizar. **Não** rode
`docker compose down -v`: o `-v` apaga o banco.

## Limitações do teste em rede local

- Só funciona para quem está na mesma rede. Para alguém de fora, é preciso hospedar.
- Sem HTTPS: o tráfego na rede local não é criptografado. Use para teste, não com dados reais de
  clientes de terceiros.
- Links do portal do cliente e de e-mail só abrem dentro da rede.
