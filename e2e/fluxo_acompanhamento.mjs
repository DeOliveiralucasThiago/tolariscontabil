// Planejado × realizado e projeção de limites: o cliente é planejado para R$ 3 mi, a receita real cresce e o Simples
// será ultrapassado. Cria a carteira pela API (e-mail novo a cada execução; não precisa de e-mail nem da BrasilAPI).
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Acompanha");
await page.fill("#nome", "Sofia Contadora");
await page.fill("#email", `sofia-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-acompanha-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cliente = await api("POST", "/clientes", {
  data: { razao_social: "Distribuidora Crescer Ltda", cnpj: "11222333000181", atividade: "comercio", regime_atual: "simples", status: "ativo" },
});
await api("POST", `/clientes/${cliente.id}/simulacoes/completa`, {
  data: { atividade: "comercio", receita_bruta_anual: 3000000, folha_clt_anual: 240000, pro_labore_anual: 60000, compras_anual: 1800000, despesas_creditaveis_anual: 90000 },
});
const linhas = ["Mês;Receita;Compras;Folha;Pró-labore"];
for (let m = 1; m <= 12; m++) linhas.push(`2025-${String(m).padStart(2, "0")};${250000 + 10000 * (m - 1)},00;${150000 + 6000 * (m - 1)},00;20000,00;5000,00`);
await api("POST", `/clientes/${cliente.id}/financeiro/importar`, {
  multipart: {
    arquivos: { name: "contabil.csv", mimeType: "text/csv", buffer: Buffer.from("﻿" + linhas.join("\n")) },
    mapeamento: JSON.stringify({ competencia: 0, receita: 1, compras: 2, folha: 3, pro_labore: 4 }),
  },
});

// 1. A aba mostra o comparativo, a recomendação e a projeção
await page.goto(`${BASE}/clientes/${cliente.id}?aba=acompanhamento`);
await page.getByRole("heading", { name: "Planejado × realizado" }).waitFor();
await page.getByText(/Receita dos últimos 12 meses, anualizada: R\$ 3\.660\.000,00, 22% acima do planejado/).waitFor();
await page.getByRole("heading", { name: "A recomendação ainda vale?" }).waitFor();
await page.getByRole("heading", { name: "Números do período" }).waitFor();
await page.getByRole("heading", { name: "Projeção dos limites" }).waitFor();
await page.screenshot({ path: `${OUT}/acomp-1-cliente.png`, fullPage: true });
passo("planejado × realizado: receita 22% acima do planejado, recomendação reavaliada e números do período");

// 2. Projeção: o limite do Simples será passado, com a data
await page.getByText(/passa do limite do Simples/).first().waitFor();
const texto = await page.getByText(/passa do limite do Simples/).first().innerText();
if (!/\(R\$\s4\.800\.000,00\) em [a-z]{3}\/\d{2}/.test(texto)) throw new Error(`texto da projeção inesperado: ${texto}`);
const grafico = page.getByRole("img", { name: /RBT12\) realizada e projetada/ });
await grafico.waitFor();
const caixa = await grafico.boundingBox();
if (!caixa || caixa.height < 200) throw new Error("gráfico não desenhou");
await page.screenshot({ path: `${OUT}/acomp-2-projecao.png`, fullPage: true });
passo("projeção avisa a data em que o limite de R$ 4,8 mi é ultrapassado, com gráfico");

// 3. Avisos: projeção e desvio do planejamento
await page.goto(`${BASE}/avisos`);
await page.getByText(/No ritmo atual, passa do limite do Simples em/).first().waitFor();
await page.getByText(/Receita real 22% acima do planejado|a melhor opção passou de/).first().waitFor();
await page.screenshot({ path: `${OUT}/acomp-3-avisos.png`, fullPage: true });
await page.getByRole("link", { name: "Ver acompanhamento" }).first().click();
await page.waitForURL(/aba=acompanhamento/);
await page.getByRole("heading", { name: "Planejado × realizado" }).waitFor();
passo("central de avisos aponta a projeção e o desvio, e leva direto à aba Acompanhamento");

// 4. Novo planejamento com os números reais
await page.getByRole("button", { name: "Novo planejamento com os números reais" }).click();
await page.getByText(/Valores realizados de jan\/25 a dez\/25/).waitFor();
if ((await page.locator("#receita").inputValue()) !== "3.660.000,00") throw new Error("receita real não foi para o formulário");
passo("botão leva os números reais para um novo planejamento");

// 5. Celular
const cel = await browser.newContext({ viewport: { width: 390, height: 800 } });
const pc = await cel.newPage();
await pc.context().addCookies(await ctx.cookies());
await pc.goto(`${BASE}/clientes/${cliente.id}?aba=acompanhamento`);
await pc.getByRole("heading", { name: "Projeção dos limites" }).waitFor();
await pc.screenshot({ path: `${OUT}/acomp-4-celular.png`, fullPage: true });
if ((await pc.evaluate(() => document.documentElement.scrollWidth)) > 390) throw new Error("rolagem horizontal no celular");
passo("aba no celular sem rolagem horizontal");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
