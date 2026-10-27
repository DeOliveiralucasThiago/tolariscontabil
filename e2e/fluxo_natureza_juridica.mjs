// Natureza jurídica: vem da consulta de CNPJ, mostra o que permite no Simples, vai para as simulações e para a Central de Avisos.
// Pede a BrasilAPI falsa (e2e/mock_brasilapi.py, CNPJ 11.222.333/0001-81) e a API apontando para ela. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const corpo = async () => (await page.innerText("body")).replace(/ /g, " ");
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1400 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Natureza");
await page.fill("#nome", "Nina Contadora");
await page.fill("#email", `nina-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-natureza-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// 1. A consulta de CNPJ preenche a natureza jurídica e mostra o que ela permite
await page.goto(`${BASE}/clientes/novo`);
await page.fill("#cnpj", "11222333000181");
await page.getByRole("button", { name: "Buscar" }).click();
await page.getByText("TECH SOLUCOES EM SOFTWARE LTDA · ATIVA").waitFor();
await page.waitForFunction(() => document.querySelector("#natureza_juridica")?.value === "Sociedade Empresária Limitada");
const info = await page.getByTestId("natureza-info").innerText();
if (!info.includes("Pode optar pelo Simples") || !info.includes("art. 3º")) throw new Error("natureza sem a explicação do Simples: " + info);
passo("CNPJ traz a natureza jurídica e a tela diz que pode optar pelo Simples");

// 2. Trocar para sociedade anônima: o Simples fica vedado
await page.selectOption("#natureza_juridica", "Sociedade Anônima Fechada");
await page.waitForFunction(() => /Simples vedado/.test(document.querySelector('[data-testid="natureza-info"]')?.innerText ?? ""));
const vedado = await page.getByTestId("natureza-info").innerText();
if (!vedado.includes("§ 4º, X")) throw new Error("faltou a base legal: " + vedado);
await page.selectOption("#regime_atual", "simples");
await page.getByRole("button", { name: /Cadastrar|Salvar/ }).first().click();
await page.waitForURL(/\/clientes\/\d+$/);
const cid = Number(page.url().split("/").pop());
await page.getByTestId("natureza-do-cliente").waitFor();
if (!(await page.getByTestId("natureza-do-cliente").innerText()).includes("Simples não permitido")) throw new Error("o cabeçalho do cliente deveria avisar");
passo("sociedade por ações: Simples vedado, com a base legal, e o aviso no cabeçalho do cliente");

// 3. O planejamento usa a natureza do cadastro: o Simples não se aplica
await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
await page.fill("#receita", "60000000");
await page.fill("#folha_anual", "12000000");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const t = await corpo();
if (/Regime recomendado\s*Simples Nacional/.test(t)) throw new Error("o Simples não deveria ser o recomendado para uma S.A.");
if (!/Natureza jurídica .*Sociedade por ações/i.test(t)) throw new Error("o alerta da natureza jurídica não apareceu no planejamento");
await page.screenshot({ path: `${OUT}/natureza_planejamento.png`, fullPage: true });
passo("planejamento: Simples não se aplica à sociedade por ações");

// 4. Central de Avisos: cliente no Simples com natureza que não permite
await page.goto(`${BASE}/avisos`);
await page.getByText("não permite o Simples Nacional").first().waitFor();
await page.screenshot({ path: `${OUT}/natureza_avisos.png`, fullPage: true });
passo("a Central de Avisos marca como crítico o cliente no Simples com natureza que não permite");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo da natureza jurídica concluído.");
