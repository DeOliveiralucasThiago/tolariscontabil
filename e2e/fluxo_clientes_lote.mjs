// Importação de clientes em lote: planilha com CNPJ, conferência, importação e complemento pela consulta de CNPJ.
// Precisa da BrasilAPI falsa (e2e/mock_brasilapi.py): só o CNPJ 11.222.333/0001-81 existe nela. E-mail novo a cada execução.
import fs from "fs";
import os from "os";
import path from "path";
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
await page.fill("#escritorio_nome", "Contabilidade Carteira Grande");
await page.fill("#nome", "Rita Contadora");
await page.fill("#email", `rita-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-carteira-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// O Excel guarda o CNPJ como número e perde o zero à esquerda; um dos CNPJ é assim.
const linhas = [
  "CNPJ;Nome da empresa;Atividade;Regime tributário;E-mail",
  "11.222.333/0001-81;;;;",
  "4252011000110;Empresa do Zero Ltda;Comércio;Simples Nacional;contato@zero.com.br",
  "45997418000153;;;;",
  "11222333000199;Com dígito errado;;;",
  "11.222.333/0001-81;Repetido;;;",
];
const pasta = fs.mkdtempSync(path.join(os.tmpdir(), "lote-"));
const csv = path.join(pasta, "carteira.csv");
fs.writeFileSync(csv, "﻿" + linhas.join("\n"));

await page.goto(`${BASE}/clientes`);
await page.getByRole("link", { name: "Importar planilha" }).click();
await page.getByRole("heading", { name: "Importar clientes" }).waitFor();
await page.setInputFiles('input[aria-label="Planilha de clientes"]', csv);
const mapeamento = page.getByLabel("Mapeamento de colunas");
await mapeamento.waitFor();
if ((await mapeamento.getByLabel("CNPJ *").inputValue()) !== "0") throw new Error("coluna do CNPJ não sugerida");
if ((await mapeamento.getByLabel("Razão social").inputValue()) !== "1") throw new Error("coluna 'Nome da empresa' não sugerida para a razão social");
if ((await mapeamento.getByLabel("Regime atual").inputValue()) !== "3") throw new Error("coluna do regime não sugerida");
passo("planilha lida e colunas sugeridas pelo cabeçalho");

await mapeamento.getByRole("button", { name: "Conferir" }).click();
const conf = page.getByLabel("Conferência da planilha");
await conf.getByText("3 clientes novos · 0 já cadastrados · 1 repetidos · 1 com CNPJ inválido").waitFor();
await conf.getByText("Linha 5").waitFor();
await page.screenshot({ path: `${OUT}/lote-1-conferencia.png`, fullPage: true });
passo("conferência: 3 novos, 1 repetido e 1 CNPJ inválido, com a linha de cada problema");

await page.getByRole("button", { name: "Importar 3 clientes" }).click();
await page.getByText("3 clientes criados · 2 para completar o cadastro").waitFor();
await page.getByText("2 clientes com cadastro por completar").waitFor();
await page.screenshot({ path: `${OUT}/lote-2-importado.png`, fullPage: true });
passo("3 clientes criados (o CNPJ sem zero à esquerda foi reconhecido); 2 aguardam o cadastro");

await page.getByRole("button", { name: "Completar pelo CNPJ" }).click();
await page.getByText("Não encontrados na Receita").waitFor({ timeout: 60000 });
await page.getByText("45.997.418/0001-53").first().waitFor();
await page.screenshot({ path: `${OUT}/lote-3-completado.png`, fullPage: true });
passo("cadastro completado pela consulta: um achado, outro listado como não encontrado");

await page.goto(`${BASE}/clientes`);
await page.getByRole("link", { name: "TECH SOLUCOES EM SOFTWARE LTDA" }).waitFor();
await page.getByText("Empresa do Zero Ltda").waitFor();
await page.getByText("Cadastro por completar").waitFor({ state: "detached" }).catch(() => {});
const total = await page.locator("tbody tr").count();
if (total !== 3) throw new Error(`esperava 3 clientes na lista, vieram ${total}`);
await page.screenshot({ path: `${OUT}/lote-4-lista.png`, fullPage: true });
passo("lista de clientes com os 3 importados (razão social vinda da Receita para o que veio só com CNPJ)");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
