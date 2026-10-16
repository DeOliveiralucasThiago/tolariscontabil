# Premissas, fontes e pontos em aberto do motor (Fase 0)

Este documento lista o que o motor assume e o que ainda precisa ser conferido
pelo contador. Atualize-o junto com as tabelas em `src/tolaris_motor/tabelas/`.

## Tabelas legais usadas

| Tabela | Valores | Fonte |
|---|---|---|
| Simples Nacional | Anexos I–V, 6 faixas, limite R$ 4,8 mi, sublimite R$ 3,6 mi, fator R 28% | LC 123/2006 (redação LC 155/2016) |
| INSS 2026 | Salário mínimo R$ 1.621,00; teto R$ 8.475,55; faixas 7,5% / 9% / 12% / 14% (até 1.621,00 / 2.902,84 / 4.354,27 / 8.475,55) | Portaria Interministerial MPS/MF nº 13/2026 |
| INSS 2025 | Salário mínimo R$ 1.518,00; teto R$ 8.157,41 | Portaria Interministerial MPS/MF nº 6/2025 |
| IRPF mensal | Isento até R$ 2.428,80 … 27,5% com dedução de R$ 908,73; desconto simplificado R$ 607,20; dependente R$ 189,59 | Lei 15.191/2025 (desde 05/2025) |
| Redução IRPF 2026 | Até R$ 5.000: redução até R$ 312,89 (imposto zero). De R$ 5.000,01 a R$ 7.350: R$ 978,62 − 0,133145 × rendimento | Lei 15.270/2025 |
| Dividendos 2026 | Retenção de 10% sobre o total pago no mês por uma mesma PJ quando passar de R$ 50 mil; IRPFM de 0% (R$ 600 mil) a 10% (R$ 1,2 mi) | Lei 15.270/2025 |
| Lucro Presumido | Presunções 8%/12% (comércio/indústria), 32%/32% (serviços); IRPJ 15% + 10% acima de R$ 60 mil/tri; CSLL 9%; PIS 0,65%; Cofins 3% | Lei 9.249/1995; Lei 9.430/1996 |
| LC 224/2025 | Presunção +10% (relativo) sobre a receita acima de R$ 5 mi/ano (R$ 1,25 mi/tri). IRPJ desde 01/2026; CSLL desde 04/2026 (noventena) | LC 224/2025 |
| Reforma | 2026 ano-teste (CBS 0,9% e IBS 0,1% dispensados); 2027–28 CBS cheia − 0,1 p.p., IBS 0,1%, fim do PIS/Cofins e do IPI; 2029–32 ICMS/ISS a 90/80/70/60% e IBS a 10/20/30/40%; 2033 só IBS/CBS | EC 132/2023; LC 214/2025 |
| Alíquotas de referência | CBS 8,8% e IBS 17,7% (≈ 26,5%) — **estimativas** | Ministério da Fazenda; TCU/Senado ainda vão fixar a de 2027 |

## Premissas de cálculo

1. **Receita constante no ano.** No Simples, RBT12 = receita anual; no Presumido, cada trimestre recebe 1/4 da receita.
2. **Encargos sobre a folha (Presumido/Real):** CPP 20% + RAT 2% + terceiros 5,8% sobre salários; CPP 20% sobre o pró-labore. RAT e terceiros são parâmetros do `PerfilEmpresa`.
3. **FGTS** não entra no total de tributos (é igual em todos os regimes), mas é despesa no Lucro Real e compõe a folha do fator R.
4. **ICMS** é não cumulativo no Presumido e no Real (débito − crédito sobre compras), com alíquota de 18% nas vendas e nas compras, salvo parâmetro.
5. **Lucro Real** é uma estimativa gerencial: compras = custo das vendas (sem variação de estoque); créditos de PIS/Cofins sobre compras e "despesas creditáveis"; adições e exclusões do LALUR só se informadas.
6. **Simples acima do sublimite:** o motor usa a alíquota cheia do DAS e emite alerta (ICMS/ISS por fora ainda não são separados).
7. **Simulação expressa:** para o Lucro Real, supõe margem de 20% antes dos tributos sobre vendas.
8. **Pró-labore × dividendos:** no Lucro Real, pró-labore e CPP reduzem o IRPJ/CSLL a 34%; o IRPFM é só sinalizado, não calculado.
9. **Reforma:** o valor das vendas sem tributos fica constante; as compras são desembutidas (ICMS de crédito + 9,25%) para formar a base de crédito; Imposto Seletivo fora; redução setorial aplicada só na venda.

## Premissas da Fase 2

10. **Simples na Reforma (IBS/CBS no DAS ou por fora):**
    - Fatia do DAS substituída por IBS/CBS = partilha atual da LC 123/2006 (PIS + Cofins em 2027;
      PIS + Cofins + ICMS + ISS + IPI em 2033). A LC 214/2025 vai redefinir a partilha; até lá é aproximação.
    - Comparação por real vendido com preços ajustados para o cliente pagar o mesmo custo líquido:
      cliente empresa (B2B) se credita do IBS/CBS; consumidor final (B2C) paga o mesmo preço final.
    - Recolhendo por fora, a empresa se credita do IBS/CBS das compras de fornecedores do regime regular.
    - Conclusão do modelo: para vendas B2B a escolha é quase neutra; o que decide são os créditos nas compras
      (a favor de recolher por fora) e a fatia de vendas ao consumidor final (contra).
11. **Autônomo × CNPJ (valores mensais):**
    - Autônomo: INSS de 20% até o teto; carnê-leão com livro-caixa ou desconto simplificado (o maior) e a
      redução de 2026; ISS fixo municipal informado à parte.
    - MEI: R$ 81.000/ano; DAS 2026 = 5% do salário mínimo (R$ 81,05) + R$ 5 (ISS) ou R$ 1 (ICMS).
    - Simples: compara pró-labore de um salário mínimo com o pró-labore que leva o fator R a 28% e escolhe
      o melhor; sócio paga INSS de 11% e IRPF sobre o pró-labore; lucro distribuído isento.
    - Presumido: pró-labore de um salário mínimo; CPP de 20% sobre ele.
    - Honorários contábeis entram como custo das opções com CNPJ.
12. **Salário líquido:** INSS progressivo de 2026 e IRRF com a redução da Lei 15.270/2025.

| Tabela | Valores | Fonte |
|---|---|---|
| Partilha do DAS | Percentuais por tributo de cada faixa dos Anexos I a V; ISS limitado a 5% efetivo | LC 123/2006, Anexos I a V |
| MEI | Limite R$ 81.000/ano; INSS 5% do salário mínimo; ISS R$ 5; ICMS R$ 1 | LC 123/2006, art. 18-A |

## Premissas da Fase 3 (importação fiscal)

13. **Classificação:** nota emitida pelo CNPJ do cliente com tipo "saída" = venda; nota em que o cliente
    é destinatário = compra. Notas sem o CNPJ do cliente são ignoradas.
14. **Situação:** só notas autorizadas (status 100/150) ou sem protocolo no XML; no SPED, documentos
    cancelados, denegados e inutilizados ficam de fora.
15. **Valores:** valor total da nota (vNF / VL_DOC). Devoluções, notas de ajuste e CFOPs que não são
    venda (remessas, transferências) ainda entram como vendas ou compras: o contador deve conferir.
16. **Anualização:** com menos de 12 meses importados, o planejamento usa a média mensal × 12.
17. **NFS-e:** ainda não importada (formatos municipais e padrão nacional em transição).

## Premissas da recuperação de tributos (monofásico e ST no Simples Nacional)

18. **O que é:** quem revende produto com PIS/Cofins monofásico ou ICMS por substituição tributária (ST) deve
    declarar a receita dele separada no PGDAS-D; o programa então deixa de cobrar, sobre ela, a parcela de
    PIS/Cofins ou de ICMS da repartição da faixa. Sem a segregação, o cliente paga em duplicidade.
    Base: LC 123/2006, art. 18, §4º-A, I e art. 13, §1º, XIII, a; Res. CGSN 140/2018, art. 25.
19. **Indício, não certeza:** o sistema não sabe o que foi declarado no PGDAS-D. O valor é "pode ter sido pago a
    mais"; o contador confere mês a mês antes de retificar ou pedir restituição.
20. **Sinais lidos na própria nota (certeza maior):** PIS com CST 04 (monofásica, revenda a alíquota zero);
    ICMS com CSOSN 500/201/202/203 ou CST 10/30/60/70; CFOP de ST (5401, 5403, 5405, 6401, 6403, 6404).
21. **Sinais por NCM (certeza média):** tabela inicial em `tabelas/monofasico.json`, com o grupo, a base legal e a
    observação de cada item. Grupos com "lista parcial" (autopeças, lubrificantes, sabonetes, preparos de
    bebidas) não entram no valor provável: aparecem em "a conferir". ST só por CEST também fica em "a conferir",
    porque a lista de ST varia por UF.
22. **Apenas revenda:** só entram saídas com CFOP de revenda (5102, 5104, 5106, 5403, 5405, 5656, 5667 e os
    interestaduais 6xxx); venda de produção própria, remessas, bonificações e devoluções ficam de fora.
23. **Valor do item:** valor do produto menos desconto (frete e outras despesas acessórias não entram).
24. **Cálculo:** economia do mês = base segregável x alíquota efetiva do mês x (% de PIS + % de Cofins da
    repartição da faixa) para o monofásico, e x % de ICMS para a ST. O RBT12 de cada mês é a soma das notas de
    venda dos 12 meses anteriores; com menos histórico importado, usa a média x 12 (marcado com `*`).
    Na 6ª faixa (RBT12 acima de R$ 3,6 milhões) o ICMS já é recolhido fora do DAS: não há economia de ICMS.
25. **Receita do mês:** valor total das notas de venda (vNF), como no movimento fiscal; devoluções e remessas ainda
    entram (premissa 15) e podem deslocar um pouco a alíquota efetiva.
26. **Escopo:** Anexos I (comércio) e II (indústria). Clientes fora do Simples recebem aviso: lá a revenda de
    produto monofásico tem PIS/Cofins com alíquota zero, mas o cálculo é outro. Não cobre veículos, máquinas,
    etanol nem cigarros. A lista de NCM é aplicada ao período todo, sem separar vigências.
27. **Prazo:** pedidos de restituição ou compensação prescrevem em 5 anos (CTN, art. 168); o cálculo cobre só o
    período importado. Com a Reforma, o PIS/Cofins deixa de existir em 2027 (substituído pela CBS).

## Premissas dos avisos e do recálculo (central de avisos)

28. **Quando são calculados:** na hora em que a página abre, a partir do último planejamento (expressa ou completa)
    e das notas importadas de cada cliente. Clientes inativos ficam de fora.
29. **Fator R:** só para clientes cadastrados no Simples com atividade "serviços sujeitos ao fator R".
    Fator R = (salários + pró-labore + FGTS 8%) / receita do último planejamento. Abaixo de 28%, compara o DAS no
    Anexo V com o do Anexo III e desconta o INSS do sócio (11% até o teto) sobre o pró-labore que falta,
    supondo um sócio e sem considerar IRPF; só vira "oportunidade" se o ganho líquido for positivo. Até 3 pontos
    percentuais acima do mínimo, gera aviso de atenção (risco de cair no Anexo V).
30. **Limites de receita:** a receita de 12 meses vem das notas importadas (média x 12 se há menos de 12 meses) ou,
    sem notas, do último planejamento. Atenção a partir de 80% do limite, crítico a partir de 95% ou acima.
    MEI: R$ 81 mil, com tolerância de 20% (R$ 97,2 mil); Simples: sublimite de R$ 3,6 milhões e limite de
    R$ 4,8 milhões (tolerância de 20%, R$ 5,76 milhões); Presumido: R$ 5 milhões (LC 224/2025) e R$ 78 milhões.
31. **Simulação desatualizada:** o sistema refaz, com as regras atuais, a simulação mais recente de cada tipo por
    cliente e compara os números (textos explicativos e campos novos são ignorados). Se mudou, avisa e oferece
    "Recalcular", que cria uma nova versão e mantém a anterior no histórico.
32. **Mudanças na legislação:** o texto da lista fica em `tabelas/mudancas.json` e é atualizado junto com as
    tabelas de cálculo; ele resume o que já está no motor e não substitui a leitura da lei.

## Premissas dos honorários, da leitura e do aceite

33. **Tabela de honorários:** valores mensais por regime recomendado (MEI, Simples, Presumido, Real), adicional por
    funcionário CLT, adesão única, serviços incluídos e validade da proposta (1 a 90 dias). Só administradores
    alteram. A sugestão é "base do regime recomendado + funcionários x adicional"; o contador sempre pode alterar
    o valor antes de salvar a proposta na simulação.
34. **Retorno exibido ao cliente:** economia estimada do relatório dividida pelo total do primeiro ano
    (12 x honorário mensal + adesão). Só aparece com economia positiva e a razão só é citada quando é de 1 vez ou
    mais. É a estimativa do diagnóstico, não promessa de resultado, e o PDF diz isso.
35. **Confirmação de leitura:** conta quando o cliente abre o relatório na tela do portal ou baixa o PDF por ele.
    Aberturas em menos de 10 minutos contam uma só. Prova que o link foi usado, não quem leu. Não há pixel de
    rastreio nos e-mails.
36. **Aceite eletrônico simples:** nome digitado, confirmação marcada, data, hora e IP. Não é assinatura digital
    (ICP-Brasil) e quem tem o link pode aceitar. Depois do aceite a proposta não pode ser alterada nem removida
    (para mudar, cria-se nova proposta em outro relatório). O escritório recebe e-mail com o registro e deve
    formalizar o contrato de prestação de serviços.
37. **Acompanhamento nos avisos:** relatório publicado e não aberto há 3 dias ou mais (até 60 dias, só com portal
    ativo); proposta vista e sem aceite há 7 dias ou mais; proposta aceita por cliente ainda "prospect" (o aviso some
    quando o cliente passa a ativo).
38. **WhatsApp:** o sistema só monta o link `wa.me` com a mensagem; quem envia é o contador, pelo próprio WhatsApp.
    O número vem do telefone do cadastro (DDD + número, com 55 acrescentado); sem telefone válido, o WhatsApp pede
    para escolher o contato. O link do portal só aparece na hora em que é gerado.
39. **Dados pessoais do aceite:** nome e IP ficam guardados como comprovante do aceite (finalidade: prova da
    contratação) e o portal avisa o cliente disso antes do aceite.
40. **Link de envio de notas:** o token tem 256 bits, só o hash (SHA-256) fica no banco e o link aparece uma única
    vez; gerar outro desativa o anterior. Quem abre o link só consegue enviar arquivos (não lê nada do escritório nem
    das notas já importadas). Limite de 30 envios por hora por link (contado em memória: vale por processo) e o mesmo
    limite de tamanho da importação. Notas de outro CNPJ enviadas pelo link são ignoradas.
41. **Planilha de dados contábeis:** `.csv` (separador `;`, `,` ou tab; UTF-8 ou Windows-1252) ou `.xlsx` (primeira
    aba), até 5 MB, 5.000 linhas e 40 colunas. Valores em formato brasileiro ou americano; negativos e valores acima
    de R$ 100 bilhões por campo são recusados (provável coluna errada). Competência em `AAAA-MM`, `MM/AAAA`, `mar/26`
    ou data. Meses repetidos na mesma planilha são somados (com aviso). Reenviar um mês troca só os campos que a
    planilha trouxe. No planejamento entram os últimos 12 meses; com menos de 12, a média dos meses informados
    vezes 12, com o aviso na tela. Campo que a planilha não traz entra como zero no planejamento.
42. **Caixa de e-mail (IMAP):** a senha é cifrada (Fernet, chave derivada de `TOLARIS_SECRET_KEY`; trocar a chave
    exige digitar a senha de novo) e nunca volta para o navegador; mudar servidor, porta ou usuário exige digitá-la
    outra vez, para a senha guardada não seguir para outro destino. Só conexão TLS na porta 993. O servidor é
    validado contra SSRF (nomes que resolvem para IP interno, loopback, link-local ou reservado são recusados, e a
    conexão usa o IP validado, conferindo o certificado pelo nome). A caixa é aberta em modo leitura: o progresso é o
    UID da última mensagem (com UIDVALIDITY), então nada é marcado como lido. Primeira leitura: últimos 30 dias;
    até 50 mensagens por rodada. Anexos `.xml`, `.zip` e `.txt` (SPED); o cliente é achado pelo CNPJ do emitente ou do
    destinatário da NF-e (a nota entra nos dois se ambos forem clientes) ou pelo registro 0000 do SPED. Arquivos de
    quem não é cliente aparecem na tela como "sem cliente". Contas Microsoft 365/Outlook costumam exigir OAuth e não
    funcionam com senha em IMAP. A leitura automática roda em uma thread do processo da API: com vários workers, cada
    um leria a caixa (sem duplicar notas, mas com leituras repetidas); use um só worker ou desligue a leitura
    automática em todos menos um.
43. **LGPD:** XML de notas têm CNPJ e, às vezes, CPF de pessoas físicas. Ficam só os campos necessários ao cálculo
    (valores, datas, itens e CNPJ do participante). Os arquivos originais e o corpo dos e-mails não são guardados.
44. **Download direto da SEFAZ (DistDFe) não implementado, de propósito:** exige certificado digital A1 do contribuinte
    (ou do escritório, com o CNPJ do escritório informado em `autXML` pelo emissor) guardado no servidor. Isso só deve
    ser feito com HTTPS, gestor de segredos e teste em homologação, o que este ambiente não permite validar.
    Enquanto isso, o link de envio e a caixa de e-mail cobrem a chegada dos XML. Também falta importar a NFS-e.
45. **Aviso de notas paradas:** cliente com status "ativo" cuja última competência importada tem mais de 2 meses de
    atraso em relação ao mês atual (em outubro, a última competência é julho ou antes). Gravidade "informativa".

46. **Importação de clientes em lote:** até 2.000 clientes por planilha (.csv ou .xlsx, 5 MB). O CNPJ aceita pontuação
    e, como o Excel descarta o zero à esquerda de números, CNPJ com 8 a 13 dígitos são completados com zeros e só valem
    se o dígito verificador fechar. Quem já tem o CNPJ cadastrado no escritório é ignorado (a planilha não atualiza
    clientes existentes). Valores de atividade, regime e situação que o sistema não reconhece ficam em branco, com aviso.
    Sem a coluna de situação, o cliente entra como "ativo" (a carteira existente), podendo escolher prospect ou inativo.
47. **Completar cadastro pelo CNPJ:** cliente criado sem razão social ou sem atividade fica "por completar". A consulta
    roda em lotes de 15 (a API pública tem limite de taxa), só preenche campos vazios e o nome provisório
    ("CNPJ 00.000.000/0000-00"); nada que o escritório digitou é trocado. A atividade e o regime vêm da sugestão por
    CNAE e pela opção de Simples/MEI, que precisam de conferência do contador. CNPJ não encontrado deixa de ser tentado
    e aparece listado; falha da consulta mantém o cliente na fila.

## Pontos para o contador validar

- [ ] Composição da folha do fator R (salários + pró-labore + FGTS; incluir 13º, férias?).
- [ ] RAT/terceiros padrão (2% e 5,8%) para os clientes típicos do escritório.
- [ ] Tratamento da LC 224/2025 diante das liminares e ADIs 7920/7936.
- [ ] Premissa de margem de 20% na simulação expressa do Lucro Real.
- [ ] Desembutir tributos das compras na reforma (fator padrão 27,25% para mercadorias).
- [ ] Percentuais de partilha do DAS (tabela em `simples_nacional.json`, campo `partilha`).
- [ ] Modelo da decisão do Simples na Reforma (preços ajustados para o mesmo custo líquido do cliente).
- [ ] Carnê-leão: livro-caixa × desconto simplificado (o motor usa o maior dos dois).
- [ ] Casos da planilha `validacao/casos_validacao.xlsx` (69 casos, incluindo SR*, AU*, REC* e AV*).
- [ ] Importação: quais CFOPs excluir da receita (remessas, devoluções, transferências).
- [ ] **Tabela de NCM monofásicos** (`src/tolaris_motor/tabelas/monofasico.json`): conferir cada prefixo e as
      exceções por subitem na tabela oficial da Receita; hoje é uma lista inicial montada sem acesso à fonte oficial.
- [ ] Sinais de ST na nota (CSOSN/CST/CFOP): confirmar quais permitem segregar o ICMS, inclusive para o substituto.
- [ ] Avisos de fator R (casos AV1 e AV2): margem de 3 pontos, INSS do acréscimo de pró-labore (um sócio) e
      tolerância de 20% do MEI e do Simples; limiares de 80% e 95% para atenção e crítico.
- [ ] Honorários: o modelo (base por regime + adicional por funcionário + adesão) cobre como o escritório cobra?
      Faltam faixas de faturamento, número de notas ou de lançamentos?
- [ ] Aceite eletrônico simples: basta para o escritório ou ele quer assinatura com certificado (ICP-Brasil/Gov.br)?
- [ ] Planilha de dados contábeis: quais colunas o sistema contábil do escritório exporta? (Faltam, por exemplo,
      receita por anexo, retenções e saldo de balancete.)
- [ ] Importação de clientes: quais colunas a lista de clientes do sistema atual do escritório exporta? (Faltam, por
      exemplo, código interno, data de entrada e responsável.)
- [ ] Caixa de e-mail: o escritório tem uma caixa própria que aceite IMAP com senha de aplicativo?
- [ ] Casos REC1 a REC3 da planilha (alíquota efetiva x % da repartição) e o tratamento do RBT12 estimado.

## Fora do escopo da Fase 0 (próximos passos do motor)

- Repartição do DAS por tributo e ICMS/ISS fora do DAS acima do sublimite.
- IRPF anual (declaração) e cálculo completo do IRPFM com redutor.
- Imposto Seletivo, ZFM, regimes específicos (combustíveis, financeiro, imobiliário).
- Envio automático pela API oficial do WhatsApp Business, rastreio de abertura de e-mail e assinatura com certificado.
- Aviso por e-mail ou WhatsApp (resumo semanal da carteira) e avisos por projeção de crescimento da receita.
- DIFAL e benefícios fiscais estaduais (a segregação de ST do Simples está na recuperação de tributos).
