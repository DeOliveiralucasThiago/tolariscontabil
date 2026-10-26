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
      PIS + Cofins + ICMS + ISS em 2033). Conferido com os Anexos da Res. CGSN 190/2026 (item 72): a aproximação vale, exceto o IPI da indústria, que permanece em 2033.
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

48. **Realizado:** receita e compras de cada mês vêm da planilha contábil quando ela traz o mês e, senão, das notas
    (vendas e compras). Folha, pró-labore e despesas só vêm da planilha. O comparativo usa os últimos 12 meses com
    receita informada e anualiza pela média (mínimo de 3 meses para comparar e 6 para refazer o comparativo de
    regimes). Campo que a planilha não traz aparece como "—" e, na reavaliação, fica como estava no planejamento.
    Com a folha real, o fator R do planejamento é descartado e recalculado.
49. **Projeção da receita:** reta de mínimos quadrados sobre os últimos 12 meses (mínimo de 6 meses informados; meses
    sem dado dentro da janela são desconhecidos, não zero, e fecham o RBT12 pela média). Não considera sazonalidade,
    contratos novos nem perdas. Confiança "alta" com 12 meses e r² de 0,5 ou mais, "média" com 9 meses ou r² de 0,3 ou
    mais, e "baixa" nos demais casos; projeção de confiança baixa não gera aviso próprio, só é mostrada na aba.
50. **Limites projetados:** MEI R$ 81 mil, sublimite (R$ 3,6 mi) e limite (R$ 4,8 mi) do Simples e limite do Presumido
    (R$ 78 mi), conforme o regime atual do cliente. Só aparece o cruzamento de limite ainda não ultrapassado. O aviso
    é "atenção" até 6 meses e "informativo" de 7 a 12; se o aviso de limite atual já existe, ganha a data prevista
    no texto. O limite do MEI usa o RBT12, como os avisos atuais; o limite legal é por ano-calendário (proporcional no
    primeiro ano), o que precisa de conferência.
51. **Aviso de realizado fora do planejado:** com 6 meses ou mais de dados, receita anualizada 20% ou mais acima ou
    abaixo do planejado (informativo) ou recomendação de regime diferente com os números reais (atenção).

52. **Verificação em duas etapas:** TOTP da RFC 6238 (SHA-1, 6 dígitos, 30 s, aceita o intervalo anterior e o seguinte),
    implementado só com a biblioteca padrão e testado com os vetores da própria RFC. O segredo fica cifrado (a mesma
    chave dos segredos do sistema); cada código vale uma vez (guarda o último intervalo aceito). Senha certa sem código
    não abre sessão: o login devolve um token de 5 minutos que só serve para a etapa do código e nunca como sessão.
    Errar o código conta no mesmo limite de tentativas do login (5 por e-mail e 30 por IP em 15 minutos) e a senha certa
    não zera esse limite. Ativar, desativar ou trocar os códigos de recuperação pede senha (e código, nos dois últimos);
    ativar derruba as outras sessões. Redefinir a senha pelo e-mail não dispensa o código.
53. **Códigos de recuperação:** 8 códigos de uso único (10 caracteres, sem letras ambíguas), mostrados uma só vez; no banco
    ficam só os hashes. Perdeu o celular e os códigos: um administrador remove a verificação do usuário (derruba as
    sessões dele e fica no registro). Não há política de exigir a verificação de todos os usuários do escritório.
54. **Registro de atividades:** guarda entrada no sistema (e recusas de quem tem conta), trocas e redefinições de senha,
    ações da verificação em duas etapas, equipe, cadastro/exclusão/exportação de cliente, importações, links do portal e
    de envio de notas (inclusive o envio feito pelo cliente), relatórios enviados, aceite de proposta, caixa de e-mail e
    dados do escritório. Cada registro tem usuário (nome e e-mail na hora), IP, data e um detalhe curto. Não guarda senha,
    token, conteúdo de nota nem o nome do titular do aceite. Fica 24 meses e só administradores veem. O IP só é confiável
    se `TOLARIS_PROXY_SALTOS` bate com o número de proxies na frente da API; a API não deve ficar acessível direto da internet.
55. **Exportação e exclusão (LGPD):** administradores baixam um JSON com tudo do cliente (cadastro, simulações, envios de
    relatório, notas e itens, dados contábeis, portal, link de envio e registro de atividades dele), sem tokens nem
    chaves internas. A exclusão é definitiva e em cascata (testada tabela por tabela); no registro de atividades sobra só
    o fato da exclusão e o nome do cliente é retirado dos registros anteriores. O sistema não decide base legal, prazo de
    guarda nem resposta ao titular: isso é do escritório (controlador) ou do cliente. Excluir cliente passou a ser só de
    administrador.
56. **Backup:** o Tolaris cria e confere o arquivo (SQLite: integridade, tabelas e contagem; PostgreSQL: restauração real
    em banco temporário se pedida), mas **não criptografa nem envia para fora do servidor**: isso fica com quem hospeda.
    O pacote portátil faz uma cópia por dia ao abrir (14 últimas) e tem "Backup Tolaris.bat".
57. **Cabeçalhos:** site e API com `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`; site com `X-Frame-Options:
    DENY`, `frame-ancestors 'none'` e política de permissões; API com `Cache-Control: no-store`. Não há CSP de scripts (o
    Next usa scripts embutidos) nem HSTS: o HSTS vai no proxy HTTPS de quem hospeda.

58. **Funil comercial:** conta uma proposta de honorários por cliente, a mais recente, para refazer a simulação não inflar
    os números. "Criada" é a data em que a proposta foi definida; "enviada", o primeiro entre publicar no portal e um
    e-mail que saiu com sucesso (e-mail que falhou não conta); "vista", a primeira abertura do relatório no portal;
    "aceita", o aceite eletrônico. Cada etapa conta quem chegou até ela, mesmo se a proposta venceu depois. Vencida é a
    proposta cuja validade passou sem aceite; um aceite posterior ao vencimento continua aceito. O período filtra pela data
    em que a proposta foi criada. A taxa de aceite é aceitas sobre enviadas. Os alertas de "O que fazer" usam os mesmos
    prazos da central de avisos (3 dias sem abrir, 7 dias sem responder) e avisam 3 dias antes do vencimento. A economia
    mostrada é a diferença entre o melhor e o pior regime da simulação aceita, não a economia sobre o que o cliente paga hoje.
    O funil não sabe de propostas fechadas fora do sistema (contrato assinado sem passar pelo aceite no portal).

59. **Tour e ajuda:** o tour geral abre sozinho uma vez por usuário **e por navegador** (a marca fica no armazenamento
    local, com versão: mudar `VERSAO` em `AjudaDoSistema.tsx` faz o tour abrir de novo para todos). Navegadores
    automatizados (testes) não o abrem sozinhos, para não cobrir a tela dos fluxos de teste. Os textos descrevem o sistema
    como ele é hoje: ao mudar uma tela ou criar uma funcionalidade, atualize `lib/tour.ts`. A ajuda não mostra nada que o
    usuário não possa ver (o passo some para o centro se o elemento não existe, por exemplo para quem não é administrador).

## Premissas da receita do exterior (exportação) e da variação cambial

60. **O que conta como exportação de serviços:** prestação a pessoa física ou jurídica residente ou domiciliada no
    exterior, com pagamento que represente ingresso de divisas, exceto o serviço desenvolvido no Brasil cujo resultado
    aqui se verifique (Res. CGSN 140/2018, art. 25, §§ 4º e 4º-A; SC Cosit 78/2019 e 185/2025). O Tolaris **não verifica**
    nada disso: o contador informa a parte da receita que é exportação e o sistema avisa dos requisitos em cada regime.
    Para ISS, o critério é o local do resultado (LC 116/2003, art. 2º, I e parágrafo único), que pode divergir do de PIS/Cofins.
61. **Simples Nacional:** a receita exportada paga o DAS menos a fatia de PIS, Cofins e ISS da partilha da faixa (serviços), ou
    de PIS, Cofins, ICMS e IPI (mercadorias); IRPJ, CSLL e CPP continuam (LC 123/2006, art. 18, § 14; Res. CGSN 140/2018, art.
    25, § 3º). Conferido no texto consolidado da Resolução, em 26/10/2026. A exclusão do ISS na exportação de serviços segue a
    LC 116/2003 e a desconsideração dos percentuais do art. 25; a SC Cosit 78/2019 só cita PIS/Cofins. A Res. CGSN 190/2026
    revoga os §§ 4º e 4º-A do art. 25 e muda o cálculo a partir de 01/01/2027: o Tolaris calcula 2025 e 2026 e avisa.
62. **Limites e alíquota do Simples com exportação:** mercado interno e exportação têm, cada um, o limite de R$ 4,8 mi (LC
    123/2006, art. 3º, § 14; Res. CGSN 140/2018, art. 2º, § 1º). **Cada mercado usa o RBT12 do próprio mercado** para achar a
    faixa e a alíquota efetiva (LC 123/2006, art. 3º, § 15, redação da LC 147/2014; Res. CGSN 140/2018, art. 23). A primeira
    versão do Tolaris usava o RBT12 total e superestimava o DAS de quem tem os dois mercados (quem só exporta, ou só vende no país,
    não muda). O fator R continua sobre a receita total. O sublimite estadual de ICMS/ISS (R$ 3,6 mi) conta só o mercado interno.
63. **Lucro Presumido:** a receita de exportação fica fora de PIS/Cofins (Leis 10.637/2002, art. 5º, e 10.833/2003, art. 6º,
    com a condição do ingresso de divisas) e de ISS/ICMS, mas **entra** na base presumida de IRPJ e CSLL. O crédito de ICMS
    das compras é mantido (CF, art. 155, § 2º, X, a).
64. **Lucro Real:** os débitos de PIS/Cofins consideram só o mercado interno e os créditos continuam; o saldo credor não
    entra no total (como já era). ISS/ICMS só sobre o mercado interno.
65. **Variação cambial:** informada pelo contador como valor líquido do ano (ganho ou perda), em reais. No Presumido, o
    ganho soma 100% na base de IRPJ e CSLL (sem presunção) e a perda **não** abate; fora de PIS/Cofins (receita financeira
    no regime cumulativo). No Real, entra no lucro (ganho soma, perda deduz). **No Simples não é calculada** (aviso).
    Regime de reconhecimento (caixa ou competência, IN RFB 1.700/2017, arts. 152 e 153) é do contador: o Tolaris recebe o
    valor já apurado. A Receita entende que a regra de caixa do art. 30 da MP 2.158-35/2001 vale só para o Real; há quem
    defenda o contrário.
66. **Câmbio:** a conversão para reais usa a PTAX de compra do Banco Central (fechamento do último dia útil até a data
    informada), por padrão, e o contador pode trocar a taxa pela do contrato de câmbio. A consulta usa o serviço público
    Olinda do Banco Central. A lista de moedas vem do próprio serviço (`Moedas`, guardada por um dia); se ele não
    responder, a tela oferece as dez mais comuns (AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK, USD) e a taxa manual segue
    valendo. **Não foi testada contra o serviço real** (o ambiente de desenvolvimento não alcança o Banco Central): o
    formato das respostas segue a documentação.
67. **Reforma tributária, planejado × realizado e notas:** as calculadoras da Reforma (IBS/CBS, Simples na Reforma) **não**
    separam exportação (que não tem IBS/CBS na LC 214/2025). O acompanhamento mantém a proporção de exterior do
    planejamento ao reavaliar com a receita real. NF-e de exportação (CFOP 7xxx) e a nota fiscal de serviços ainda não
    alimentam a receita do exterior: ela vem do planejamento ou da planilha.
68. **Seleção de atividade:** as opções mostram o Anexo e exemplos. O Anexo V não é opção: é o resultado do fator R. Os
    exemplos de serviços por Anexo são orientativos (LC 123/2006, art. 18, §§ 5º-B a 5º-M); o enquadramento é pelo CNAE.

69. **Enquadramento (Anexo V → III):** para atividade do fator R, o Tolaris compara a situação de hoje com (a) pró-labore elevado
    até o fator R chegar a 28%, somando o INSS de 11% do sócio sobre o acréscimo (o IRRF do sócio não entra) e (b) uma parte da
    receita em atividade que tributa direto no Anexo III, em 25%, 50%, 100% e um percentual do contador. No Simples, cada parte
    da receita usa a alíquota efetiva do seu Anexo (calculada sobre o RBT12 do mercado), e a receita do exterior é repartida
    proporcionalmente entre as partes. O fator R continua medido sobre a receita total. Presumido e Real não mudam com a
    separação por Anexo. **Só vale se a atividade for exercida de fato**, com o CNAE no cadastro e nota fiscal do serviço: a Receita
    enquadra pela atividade real, e um CNAE incluído sem a atividade pode ser desconsiderado, com cobrança e multa. A tela e o
    PDF repetem esse aviso.
70. **CNAEs e Anexos:** o catálogo traz as 1.334 subclasses da CNAE 2.3 (IBGE/Concla), as vedações oficiais (Res. CGSN 140/2018,
    Anexo VI: 101 CNAEs impeditivos; Anexo VII: 22 ambíguos) e o Anexo de 389 CNAEs vindo da tabela da Contabilizei (fonte
    **comercial**, coletada em 26/10/2026). Atenção: os Anexos VI e VII da Resolução são listas de **vedação**, não de Anexo; a
    Resolução define o Anexo III, IV ou V pela **descrição da atividade** (art. 25, § 1º), e não existe tabela oficial por
    CNAE. A tabela comercial é, portanto, uma interpretação e cada resposta traz a confiança: `oficial` (vedação), `tabela`
    (Contabilizei) ou `divisao` (regra aproximada, para os CNAEs que a tabela não cobre; ela errava 112 dos 389 códigos da
    tabela, por isso só vale como último recurso). Os CNAEs secundários do cliente vêm da consulta de CNPJ (cadastro, prospecção rápida, importação em lote e a própria tela Enquadramento, que também aceita o CNPJ ou um cliente da lista). A tela Enquadramento
    lista os CNAEs de Anexo III direto, sem fator R, que o contador pode avaliar, sempre com o aviso de que só vale para atividade
    exercida de fato. Para atualizar, baixe as fontes de novo e rode `scripts/gerar_tabela_cnae.py`.

71. **Conferência com o texto da LC 123/2006 (26/10/2026):** as tabelas dos Anexos I a V (alíquotas, parcelas a deduzir e partilha, na
    redação da LC 155/2016) foram comparadas com `simples_nacional.json`, sem divergência. **Fator R:** art. 18, §§ 5º-I, 5º-J e 5º-M
    (28%), § 5º-K (12 meses anteriores) e § 24 (folha = remunerações a pessoas físicas, inclusive pró-labore, mais a contribuição patronal
    efetivamente recolhida e o FGTS); o § 26 exclui aluguéis e distribuição de lucros. O Tolaris soma salários, pró-labore e FGTS de 8%,
    sem a CPP (que no Anexo III e no V já está dentro do DAS): ponto para o contador. Somar uma CPP estimada inflaria o fator R e poderia
    indicar o Anexo III sem que a empresa chegue a 28%, por isso não foi feito. O resultado avisa a composição legal da folha (13º
    incluído; aluguéis e distribuição de lucros fora) e o planejamento aceita a folha apurada no eSocial ou no PGDAS-D no campo
    "Folha do fator R informada", que substitui a calculada. **Vedações:** os incisos XI (atividade intelectual) e
    XIII (consultoria) do art. 17 foram revogados em 2014, então serviço intelectual pode optar pelo Simples; seguem vedados, entre outros,
    sócio domiciliado no exterior (art. 17, II), locação de imóveis próprios (XV, LC 214/2025), filial no exterior (art. 3º, § 4º, XII) e
    sócios com pessoalidade, subordinação e habitualidade com o contratante (art. 3º, § 4º, XI). **Exclusão:** art. 29, §§ 1º e 2º (3
    anos de impedimento; 10 se houver artifício ou fraude). **Anexo pela atividade:** § 5º-B (Anexo III, entre elas cursos "gerenciais e
    escolas livres", instalação, reparos e manutenção em geral, produções culturais), § 5º-C (IV), § 5º-D e § 5º-I (V pelo fator R);
    os §§ 5º-D, IV e VI exigem que o programa ou a página sejam desenvolvidos "em estabelecimento do optante". Escritórios contábeis
    recolhem ISS em valor fixo (§ 22-A), o que o cálculo não trata.

72. **Resoluções CGSN 190, 191, 194 e 195 (lidas no portal de normas da Receita, em 26/10/2026):**
    - **190/2026** (publicada em 10/08/2026, efeitos a partir de 01/01/2027): adapta o Simples ao IBS e à CBS. Novos Anexos I a V com a
      partilha por período (2027–28, 2029, 2030, 2031, 2032 e 2033 em diante): a CBS e o IBS ocupam, em cada faixa, a soma das
      fatias de PIS, Cofins, ICMS e ISS de hoje (conferido por Anexo e faixa); o IPI do Anexo II permanece (7,5%); a 6ª faixa tem
      alíquota nominal um pouco menor (Anexo I: 18,90%; Anexo III: 32,90%) e o teto do ISS efetivo cai a 4% em 2030. Cria a opção pelo
      regime regular de IBS/CBS (art. 40-C e 40-D) e o split payment. A RBT12 passa a ser a dos 12 meses anteriores ao mês anterior ao
      da apuração; interno e exportação continuam separados; os §§ 4º e 4º-A do art. 25 (exportação de serviços) são revogados e a
      qualificação segue cada tributo (§ 4º-B). A folha do fator R mantém a mesma composição. Novo Anexo XIII com os valores do MEI.
    - **191/2026** (efeitos a partir de 01/11/2026): o optante do Simples que presta serviços passa a emitir obrigatoriamente a NFS-e
      de padrão nacional (Emissor Nacional, web ou API), também o optante pendente ou impedido; vedada em operação só de ICMS.
    - **194/2026** (publicada em 28/09/2026): altera a Res. 186/2026. Opção pelo Simples para 2027: de 01/09 a 15/10/2026 (cancelável de
      03/11 a 20/12/2026; pendências regularizáveis até 30/10/2026). **Opção pelo regime regular de IBS/CBS para jan-jun/2027: de
      01/09 a 30/10/2026, cancelável de 03/11 a 20/12/2026.** Empresas abertas depois de 16/10 (Simples) ou de 31/10 (regime regular)
      ficam fora desses prazos.
    - **195/2026** (efeitos a partir de 01/01/2027): a DASN-Simei pode servir de documento fiscal do MEI para consumidor final pessoa
      física. Sem efeito no cálculo.
    O Tolaris continua calculando o Simples de 2025 e 2026 com as tabelas atuais; os Anexos de 2027 em diante ainda não foram
    carregados como vigências. A Res. 186/2026 (origem dos prazos) não foi lida, só a parte que a 194 reescreve.

## Pontos para o contador validar

- [ ] Composição da folha do fator R (salários + pró-labore + FGTS; incluir 13º, férias? A lei, art. 18, § 24, soma também a CPP efetivamente recolhida).
- [ ] RAT/terceiros padrão (2% e 5,8%) para os clientes típicos do escritório.
- [ ] **Prazo:** decisão sobre o regime regular de IBS/CBS (jan-jun/2027) até 30/10/2026; cancelamento irretratável de 03/11 a 20/12/2026 (Res. CGSN 194/2026). Rodar o "Simples na Reforma" dos clientes B2B antes.
- [ ] NFS-e nacional obrigatória a partir de 01/11/2026 para os optantes que prestam serviços (Res. CGSN 191/2026): conferir os clientes ainda em emissor municipal.
- [ ] Enquadramento: conferir o Anexo de cada CNAE do cliente na descrição da atividade (Res. CGSN 140/2018, art. 25, § 1º), já que a tabela por CNAE é comercial, e se há atividade real que justifique segregar receita no Anexo III.
- [ ] Pró-labore elevado para o fator R: custo do INSS (11% do sócio) e do IRRF, e se a retirada total já comporta o valor.
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
- [ ] Acompanhamento: o desvio de 20% e a projeção linear fazem sentido para a carteira? Há clientes sazonais
      (comércio de fim de ano, safra) para os quais a projeção precisa de outro método?
- [ ] Limite do MEI: avisar pelo RBT12 ou pela receita do ano-calendário (com a regra proporcional no primeiro ano)?
- [ ] Segurança: o escritório quer exigir a verificação em duas etapas de todos os usuários? Quanto tempo guardar o
      registro de atividades (hoje 24 meses) e os backups?
- [ ] LGPD: quem responde ao titular, qual o prazo de guarda das notas de clientes que saem do escritório e o que consta
      do contrato de prestação de serviços (o texto do aceite da proposta e o aviso de privacidade ainda são genéricos).
- [ ] Funil: o escritório marca como fechado o que foi acertado por telefone ou WhatsApp? Falta um "Marcar como fechado" (e
      "perdido, com o motivo") para o funil não depender do aceite no portal.
- [ ] Caixa de e-mail: o escritório tem uma caixa própria que aceite IMAP com senha de aplicativo?
- [ ] Casos REC1 a REC3 da planilha (alíquota efetiva x % da repartição) e o tratamento do RBT12 estimado.

- [ ] Receita do exterior: o ISS sai do DAS na exportação de serviços (premissa 61)? O texto vigente do art. 25 da Res. CGSN 140
      depois da Res. CGSN 190/2026? Quais municípios exigem comprovação (contrato, câmbio) e qual a alíquota na exportação?
- [ ] Variação cambial: caixa ou competência no Presumido? Entra na receita bruta do Simples? Ganho em conta no exterior?
- [ ] Taxa de conversão: PTAX de compra ou venda, do dia do câmbio ou da emissão da nota? Cada cliente tem a sua política.
- [ ] Os exemplos de serviços por Anexo (seletor de atividade) batem com o que o escritório usa?

## Fora do escopo da Fase 0 (próximos passos do motor)

- Repartição do DAS por tributo e ICMS/ISS fora do DAS acima do sublimite.
- IRPF anual (declaração) e cálculo completo do IRPFM com redutor.
- Imposto Seletivo, ZFM, regimes específicos (combustíveis, financeiro, imobiliário).
- Envio automático pela API oficial do WhatsApp Business, rastreio de abertura de e-mail e assinatura com certificado.
- Aviso por e-mail ou WhatsApp (resumo semanal da carteira) e avisos por projeção de crescimento da receita.
- DIFAL e benefícios fiscais estaduais (a segregação de ST do Simples está na recuperação de tributos).
