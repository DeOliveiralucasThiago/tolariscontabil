# Onde ler a legislação (e o que cada fonte entrega)

**Os textos já estão na pasta `legislação/` do repositório** (lei por lei, com o índice em `legislação/LEIA-ME.md`). Quem precisar de uma norma nova
roda `python scripts/baixar_legislacao.py LEI:9249:1995` (ou `--receita CGSN:Resol.:140:2018`, `--proposicao PLP:108:2021`); o script usa as fontes abaixo,
prefere a compilação vigente e anota no cabeçalho de cada arquivo qual versão baixou e quando. Sem argumentos, ele baixa de novo a lista padrão.

Testado em 26/10/2026. O texto de uma lei prevalece sobre qualquer resumo do Tolaris.

| Fonte | Endereço | O que entrega |
|---|---|---|
| Receita Federal, normas | `normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{id}/visao/{original,multivigente}` e `.../ato/{id}/anexo/{idArquivo}` | Texto completo de Resoluções CGSN, INs e portarias (em JSON), com histórico de alterações e os anexos em PDF. O `id` aparece no histórico do ato alterado. |
| Câmara dos Deputados | `dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PLP&numero=186&ano=2026` e `.../proposicoes/{id}/tramitacoes` | Dados do projeto e a tramitação. Cada passo traz a `url` do documento (PDF em `camara.leg.br/proposicoesWeb/prop_mostrarintegra?codteor=...`). O **autógrafo** (enviado à sanção) é o texto da lei antes dos vetos. A tramitação diz em que lei complementar o projeto virou. |
| Senado Federal | `legis.senado.leg.br/dadosabertos/legislacao/lista?tipo=LCP&numero=214&ano=2025` e `.../legislacao/{id}` | Dados da norma e o mapa de alterações (quais artigos foram alterados e por qual norma posterior). **Não traz o texto corrido.** |
| Senado, portal Normas.leg.br | `normas.leg.br/api/public/normas?urn={urn}&&tipo_documento=maior-detalhe` e `normas.leg.br/api/public/binario/{id}/texto` | O **texto** das leis federais: a compilação vigente (feita pela Câmara, com as notas de alteração) ou a publicação original; para normas recentes, a árvore de dispositivos. A URN sai da API do Senado (`tipo`, `número`, data da assinatura). |
| Receita Federal, portal de normas | `POST normas.receita.fazenda.gov.br/api/indexacao/ato/pesquisar` (acha o `idAto`) e `normasinternet2.receita.fazenda.gov.br/api/consulta-externa/ato/{idAto}/visao/multivigente` | Resoluções do CGSN, INs da RFB e outros atos, com o texto em vigor. Os anexos em PDF vêm à parte (`.../anexo/{idArquivo}`). |

Limites: o Planalto não responde a acesso automático; o texto das leis vem do Normas.leg.br (a compilação pode estar um pouco atrás das leis mais novas; confira as notas "Vide" e a lista de alterações do
Senado). Os serviços do Senado devolvem 503 de vez em quando: o script espera e tenta de novo, com pausa entre as chamadas. Se uma fonte pedir verificação
de robô, não se contorna: avise o responsável.

Projetos citados com frequência: PLP 68/2024 virou a LC 214/2025; PLP 108/2024 virou a LC 227/2026; PLP 186/2026 virou a LC 238/2026
(limite do MEI). O PLP 108/2021 (MEI de R$ 130 mil) e o PLP 116/2021 (suspensão de prazos de 20/12 a 20/01) ainda tramitam.
