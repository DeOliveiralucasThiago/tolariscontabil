# Onde ler a legislação (e o que cada fonte entrega)

Testado em 26/10/2026. O texto de uma lei prevalece sobre qualquer resumo do Tolaris.

| Fonte | Endereço | O que entrega |
|---|---|---|
| Receita Federal, normas | `normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{id}/visao/{original,multivigente}` e `.../ato/{id}/anexo/{idArquivo}` | Texto completo de Resoluções CGSN, INs e portarias (em JSON), com histórico de alterações e os anexos em PDF. O `id` aparece no histórico do ato alterado. |
| Câmara dos Deputados | `dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PLP&numero=186&ano=2026` e `.../proposicoes/{id}/tramitacoes` | Dados do projeto e a tramitação. Cada passo traz a `url` do documento (PDF em `camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=...`). O **autógrafo** (enviado à sanção) é o texto da lei antes dos vetos. A tramitação diz em que lei complementar o projeto virou. |
| Senado Federal | `legis.senado.leg.br/dadosabertos/legislacao/lista?tipo=LCP&numero=214&ano=2025` e `.../legislacao/{id}` | Dados da norma e o mapa de alterações (quais artigos foram alterados e por qual norma posterior). **Não traz o texto corrido.** |

Limites: o Planalto não responde a acesso automático; o texto consolidado de leis sem projeto na Câmara precisa ser colado. A Câmara e o
Senado devem ser consultados com poucas chamadas e sem insistir quando houver verificação de robô.

Projetos citados com frequência: PLP 68/2024 virou a LC 214/2025; PLP 108/2024 virou a LC 227/2026; PLP 186/2026 virou a LC 238/2026
(limite do MEI). O PLP 108/2021 (MEI de R$ 130 mil) e o PLP 116/2021 (suspensão de prazos de 20/12 a 20/01) ainda tramitam.
