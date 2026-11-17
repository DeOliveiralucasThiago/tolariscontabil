# Loja Melty Velas

Site estático (Fase 1: vitrine + carrinho). Sem dependências nem build.

## Ver no computador
```bash
cd loja-melty
python3 -m http.server 8000
```
Abra http://localhost:8000. (Não abra o index.html com duplo clique: o navegador bloqueia a leitura dos arquivos de dados.)

## Onde editar
- `data/produtos.json`: produtos, preços, estoque, descrição e foto de cada vela.
- `data/config.json`: nome da loja, WhatsApp, Instagram, e-mail e texto do aviso de prazo.
- `assets/style.css`: cores (variáveis no topo do arquivo).
- Fotos: coloque em `assets/` e troque o campo `imagem` do produto.

## Próximas fases
Painel e estoque, pagamento, frete (Melhor Envio), e-mails automáticos.
