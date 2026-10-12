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

## Pontos para o contador validar

- [ ] Composição da folha do fator R (salários + pró-labore + FGTS; incluir 13º, férias?).
- [ ] RAT/terceiros padrão (2% e 5,8%) para os clientes típicos do escritório.
- [ ] Tratamento da LC 224/2025 diante das liminares e ADIs 7920/7936.
- [ ] Premissa de margem de 20% na simulação expressa do Lucro Real.
- [ ] Desembutir tributos das compras na reforma (fator padrão 27,25% para mercadorias).
- [ ] Percentuais de partilha do DAS (tabela em `simples_nacional.json`, campo `partilha`).
- [ ] Modelo da decisão do Simples na Reforma (preços ajustados para o mesmo custo líquido do cliente).
- [ ] Carnê-leão: livro-caixa × desconto simplificado (o motor usa o maior dos dois).
- [ ] Casos da planilha `validacao/casos_validacao.xlsx` (64 casos, incluindo SR* e AU*).

## Fora do escopo da Fase 0 (próximos passos do motor)

- Repartição do DAS por tributo e ICMS/ISS fora do DAS acima do sublimite.
- IRPF anual (declaração) e cálculo completo do IRPFM com redutor.
- Imposto Seletivo, ZFM, regimes específicos (combustíveis, financeiro, imobiliário).
- Substituição tributária de ICMS, DIFAL e benefícios fiscais estaduais.
