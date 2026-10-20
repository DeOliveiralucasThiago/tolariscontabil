// Receita do exterior: explicação dos Anexos no seletor, bloco opcional do planejamento, conversor de moeda (PTAX),
// resultado sem ISS/PIS/Cofins na parte exportada, variação cambial e prospecção com exterior. E-mail novo a cada execução.
// Precisa da API com TOLARIS_PTAX_URL=http://127.0.0.1:8099/ptax (o mock_brasilapi.py responde as duas coisas).
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1000 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Exterior");
await page.fill("#nome", "Lia Contadora");
await page.fill("#email", `lia-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-exterior-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const brl = (t) => Number(t.replace(/[^\d,-]/g, "").replace(",", "."));

// 1. Seletor de atividade: o Anexo aparece em cada opção e há explicação com exemplos
await page.goto(`${BASE}/prospeccao`);
await page.getByRole("heading", { name: "Prospecção rápida" }).waitFor();
const opcoes = await page.locator("#atividade option").allTextContents();
for (const trecho of ["Comércio — Anexo I", "Indústria — Anexo II", "(fator R) — Anexo III ou V", "Anexo III (fixo)", "Anexo IV (CPP por fora)"]) {
  if (!opcoes.some((o) => o.includes(trecho))) throw new Error(`opção sem “${trecho}”: ${opcoes.join(" | ")}`);
}
await page.selectOption("#atividade", "servico_fator_r");
const explica = page.getByTestId("explica-atividade");
await explica.locator("summary").click();
const texto = await explica.innerText();
for (const trecho of ["Consultoria, TI e software", "28%", "Anexo V não é uma opção à parte"]) {
  if (!texto.includes(trecho)) throw new Error(`explicação sem “${trecho}”: ${texto}`);
}
await page.screenshot({ path: `${OUT}/exterior_1_atividade.png` });
passo("seletor de atividade mostra o Anexo e explica exemplos e fator R");

// 2. Prospecção com parte do faturamento vinda do exterior
await page.fill("#faturamento", "5000000"); // máscara: os dígitos são centavos
await page.fill("#prolabore", "2000000");
await page.click("text=Calcular previsão");
await page.getByText("Regime recomendado").waitFor();
const semExterior = await page.locator("tr", { has: page.getByText("Total", { exact: true }) }).first().innerText();
await page.fill("#exterior_mensal", "5000000");
await page.click("text=Calcular previsão");
await page.getByTestId("nota-exterior").waitFor();
const comExterior = await page.locator("tr", { has: page.getByText("Total", { exact: true }) }).first().innerText();
const nums = (t) => t.match(/R\$\s?[\d.]+,\d{2}/g).map(brl);
const a = nums(semExterior), b = nums(comExterior);
if (!(b.every((v, i) => v < a[i]))) throw new Error(`com exterior não ficou menor em todos os regimes: ${a} -> ${b}`);
if (!(await page.getByText("ingresso de divisas").first().isVisible())) throw new Error("faltou o aviso de requisitos da exportação");
await page.screenshot({ path: `${OUT}/exterior_2_prospeccao.png`, fullPage: true });
passo(`prospecção: tributos caem com receita do exterior (${a} -> ${b})`);

// 3. Planejamento completo do cliente: bloco opcional, conversor com PTAX, variação cambial
const cliente = await api("POST", "/clientes", { data: { razao_social: "Consultoria Maple Ltda", cnpj: "11222333000181", atividade: "servico_fator_r", regime_atual: "presumido", status: "ativo" } });
await page.goto(`${BASE}/clientes/${cliente.id}`);
await page.getByRole("tab", { name: "Novo planejamento" }).click();
await page.fill("#receita", "60000000");
await page.fill("#prolabore_anual", "24000000");
await page.fill("#outras", "6000000");
const bloco = page.getByTestId("bloco-exterior");
await bloco.locator("summary").click();
await page.selectOption("#moeda_origem", "CAD");
await page.fill("#valor_moeda", "100000");   // máscara: 1.000,00 CAD
await page.fill("#data_cambio", "2026-10-15");
await page.click("text=Buscar PTAX");
await page.getByText(/PTAX de compra de 15\/10\/2026/).waitFor();
const taxa = await page.inputValue("#taxa_cambio");
if (taxa !== "4,0000") throw new Error(`taxa esperada 4,0000, veio ${taxa}`);
const convertido = await page.getByTestId("reais-convertidos").innerText();
if (brl(convertido) !== 4000) throw new Error(`1.000 CAD x 4,00 = R$ 4.000,00; veio ${convertido}`);
// taxa editável: o contrato de câmbio manda
await page.fill("#taxa_cambio", "4,5");
if (brl(await page.getByTestId("reais-convertidos").innerText()) !== 4500) throw new Error("troca manual da taxa não refez a conta");
await page.click("text=Usar como receita do exterior");
if (brl(await page.inputValue("#receita_exterior")) !== 4500) throw new Error("receita do exterior não foi preenchida pelo conversor");
// o valor do exterior vira o do ano todo: 600.000
await page.fill("#receita_exterior", "60000000");
await page.selectOption("#tipo_cambial", "ganho");
await page.fill("#variacao_cambial", "4000000");
await page.screenshot({ path: `${OUT}/exterior_3_planejamento.png`, fullPage: true });
await page.click("text=Calcular e salvar planejamento");
await page.getByTestId("nota-exterior").waitFor();
const nota = await page.getByTestId("nota-exterior").innerText();
if (!/600\.000,00/.test(nota) || !/ganho/.test(nota) || !/40\.000,00/.test(nota)) throw new Error("resumo do exterior errado: " + nota);
if (!(await page.getByText(/Variação cambial ativa somada à base de IRPJ e CSLL/).first().isVisible())) throw new Error("faltou o aviso da variação cambial no Presumido");
await page.screenshot({ path: `${OUT}/exterior_4_resultado.png`, fullPage: true });
passo("planejamento com conversor PTAX (taxa editável), exterior e variação cambial");

// 4. Erro: exterior maior que a receita
await page.getByRole("tab", { name: "Novo planejamento" }).click();
await page.fill("#receita", "10000000");
if (!(await page.locator("#receita_exterior").isVisible())) await page.getByTestId("bloco-exterior").locator("summary").click();
await page.fill("#receita_exterior", "20000000");
await page.click("text=Calcular e salvar planejamento");
await page.getByRole("alert").filter({ hasText: "não pode passar da receita bruta" }).waitFor();
passo("exterior acima da receita é barrado com mensagem clara");

// 5. Planilha com colunas do exterior, inclusive variação cambial negativa
await api("POST", `/clientes/${cliente.id}/financeiro/importar`, {
  multipart: { arquivos: { name: "d.csv", mimeType: "text/csv", buffer: Buffer.from("﻿Mês;Receita;Receita do exterior;Variação cambial\n" + Array.from({ length: 12 }, (_, i) => `2025-${String(i + 1).padStart(2, "0")};50000,00;40000,00;-250,00`).join("\n")) },
    mapeamento: JSON.stringify({ competencia: 0, receita: 1, receita_exterior: 2, variacao_cambial: 3 }) },
});
const fin = await api("GET", `/clientes/${cliente.id}/financeiro`);
if (fin.planejamento.receita_exterior_anual !== 480000 || fin.planejamento.variacao_cambial_anual !== -3000) throw new Error("planejamento da planilha errado: " + JSON.stringify(fin.planejamento));
await page.goto(`${BASE}/clientes/${cliente.id}`);
await page.getByRole("tab", { name: "Movimento fiscal" }).click();
await page.getByText("Usar no planejamento").click();
await page.getByTestId("bloco-exterior").waitFor();
if (brl(await page.inputValue("#receita_exterior")) !== 480000) throw new Error("“Usar no planejamento” não trouxe a receita do exterior");
if ((await page.inputValue("#tipo_cambial")) !== "perda") throw new Error("variação negativa devia aparecer como perda");
passo("planilha com receita do exterior e perda cambial alimenta o planejamento");

// 6. Celular: bloco e conversor cabem na tela
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: `${OUT}/exterior_5_celular.png`, fullPage: true });
const largura = await page.evaluate(() => document.documentElement.scrollWidth);
if (largura > 392) throw new Error(`rolagem horizontal no celular: ${largura}px`);
passo("celular sem rolagem horizontal");

if (erros.length) throw new Error("erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo do exterior concluído.");
