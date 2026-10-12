// Fase 2 no navegador: Reforma (transição e Simples), Pessoa física (autônomo, pró-labore, salário),
// salvar no cliente, relatórios em PDF e histórico do cliente com todos os tipos.
// Uso: veja e2e/README.md (rode depois de fluxo_principal.mjs ou com banco novo).
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));
const passo = (t) => console.log("✓", t);
const moeda = (sel, centavos) => page.fill(sel, String(centavos));

async function baixarPdf(nome) {
  const link = page.getByRole("link", { name: "Abrir relatório em PDF" });
  await link.waitFor();
  const resp = await page.request.get(BASE + (await link.getAttribute("href")));
  if (resp.headers()["content-type"] !== "application/pdf") throw new Error(`PDF ${nome} não veio`);
  fs.writeFileSync(`${OUT}/${nome}.pdf`, await resp.body());
}

async function salvarNoCliente(nome) {
  await page.getByLabel("Cliente", { exact: true }).selectOption({ label: "Mercado Bom Preço Ltda" });
  await page.getByRole("button", { name: "Salvar e gerar PDF" }).click();
  await baixarPdf(nome);
}

// Cadastro e um cliente
const email = `fase2-${Date.now()}@teste.com.br`;
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Escritório Fase 2");
await page.fill("#nome", "Ana Contadora");
await page.fill("#email", email);
await page.fill("#senha", "senha-forte-123");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
await page.goto(`${BASE}/clientes/novo`);
await page.fill("#razao_social", "Mercado Bom Preço Ltda");
await page.selectOption("#atividade", "comercio");
await page.getByRole("button", { name: "Cadastrar cliente" }).click();
await page.waitForURL(/\/clientes\/\d+$/);
const clienteUrl = page.url();
passo("cadastro e cliente");

// Reforma: transição
await page.click("aside >> text=Reforma Tributária");
await page.waitForURL("**/reforma");
await moeda("#receita_ref", 200000000);
await page.selectOption("#vende", "m");
await moeda("#compras_ref", 120000000);
await moeda("#desp_ref", 10000000);
await page.getByRole("button", { name: "Simular transição" }).click();
await page.getByText("Carga sobre o consumo em 2033").waitFor();
await page.screenshot({ path: `${OUT}/f2-1-reforma.png`, fullPage: true });
await salvarNoCliente("reforma");
passo("reforma: transição calculada, salva e PDF");

// Reforma: Simples no DAS ou por fora
await page.getByRole("tab", { name: "Simples: IBS/CBS no DAS ou por fora" }).click();
await moeda("#receita_sr", 200000000);
await page.locator("#b2b").fill("80");
await moeda("#compras_sr", 120000000);
await page.getByRole("button", { name: "Comparar opções" }).click();
await page.getByText("Recomendação para 2033").waitFor();
await page.getByRole("button", { name: "2027", exact: true }).click();
await page.screenshot({ path: `${OUT}/f2-2-simples-reforma.png`, fullPage: true });
await salvarNoCliente("simples-reforma");
passo("reforma: Simples B2B calculado, curva por ano, salvo e PDF");

// Pessoa física: autônomo × CNPJ
await page.click("aside >> text=Pessoa física");
await page.waitForURL("**/pessoa-fisica");
await moeda("#receita_pf", 1500000);
await moeda("#despesas_pf", 100000);
await moeda("#contab_pf", 40000);
await page.getByRole("button", { name: "Comparar" }).click();
await page.getByText("Opção mais vantajosa").waitFor();
const melhor = await page.locator("section.border-2 .text-2xl").innerText();
await page.screenshot({ path: `${OUT}/f2-3-autonomo.png`, fullPage: true });
await salvarNoCliente("autonomo");
passo(`autônomo × CNPJ: melhor = ${melhor}; salvo e PDF`);

// Pró-labore × dividendos
await page.getByRole("tab", { name: "Pró-labore × dividendos" }).click();
await moeda("#retirada", 2000000);
await page.getByRole("button", { name: "Comparar" }).click();
await page.getByText("Estratégia recomendada").waitFor();
await salvarNoCliente("pro-labore");
passo("pró-labore × dividendos: salvo e PDF");

// Salário líquido
await page.getByRole("tab", { name: "Salário líquido" }).click();
await moeda("#bruto", 590000);
await page.getByRole("button", { name: "Calcular" }).click();
await page.getByText("R$ 4.924,35").first().waitFor();
passo("salário líquido de R$ 5.900,00 = R$ 4.924,35");

// Histórico do cliente com todos os tipos
await page.goto(clienteUrl);
await page.getByText("Simulações (4)").waitFor();
for (const titulo of ["Reforma Tributária 2025–2033", "Simples na Reforma", "Autônomo × CNPJ", "Pró-labore × dividendos"]) {
  await page.locator("li", { hasText: titulo }).getByRole("button", { name: "Ver" }).click();
  await page.getByRole("link", { name: "Abrir relatório em PDF" }).waitFor();
  await page.locator("li", { hasText: titulo }).getByRole("button", { name: "Fechar" }).click();
}
passo("histórico do cliente abre os 4 tipos");

// Celular
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: await ctx.storageState() });
const mp = await mobile.newPage();
await mp.goto(`${BASE}/reforma`);
await mp.fill("#receita_ref", "100000000");
await mp.getByRole("button", { name: "Simular transição" }).click();
await mp.getByText("Carga sobre o consumo em 2033").waitFor();
const larg = await mp.evaluate(() => document.documentElement.scrollWidth);
await mp.screenshot({ path: `${OUT}/f2-4-celular.png`, fullPage: true });
if (larg > 390) throw new Error(`rolagem horizontal no celular: ${larg}px`);
passo(`celular sem rolagem horizontal (${larg}px)`);

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
