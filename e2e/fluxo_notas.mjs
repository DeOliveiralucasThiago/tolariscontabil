// Item 4: notas sem atrito. Link de envio para o cliente (sem login), dados contábeis por planilha com mapeamento de
// colunas e caixa de e-mail (IMAP) nas Configurações. E-mail novo a cada execução; não precisa de e-mail real.
// A verificação da caixa de e-mail tenta conectar de verdade: aqui só conferimos que a falha aparece de forma legível
// (o servidor IMAP de mentira fica nos testes automáticos da API).
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
const CNPJ = "11222333000181";

const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
const vigiar = (p) => {
  p.on("console", (m) => m.type() === "error" && !/401|429|Failed to load resource/.test(m.text()) && erros.push(m.text()));
  p.on("pageerror", (e) => erros.push(String(e)));
};
vigiar(page);

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Notas Fáceis");
await page.fill("#nome", "Paula Contadora");
await page.fill("#email", `paula-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-notas-fceis-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

const api = async (metodo, caminho, corpo) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, data: corpo });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cliente = await api("POST", "/clientes", {
  razao_social: "Mercadinho Boa Compra Ltda", cnpj: CNPJ, atividade: "comercio", regime_atual: "simples",
  contato_nome: "Marcos Souza", telefone: "(11) 98765-4321", status: "ativo",
});

function nfe(n, data) {
  const chave = `3526031122233300018155001${String(n).padStart(9, "0")}1${String(n).padStart(8, "0")}`.slice(0, 43).padEnd(43, "0") + "1";
  return `<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe${chave}"><ide><mod>55</mod><dhEmi>${data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>${CNPJ}</CNPJ></emit><dest><CNPJ>45997418000153</CNPJ></dest><total><ICMSTot><vICMS>0.00</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vNF>1500.00</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>${chave}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>`;
}
const pasta = fs.mkdtempSync(path.join(os.tmpdir(), "notas-"));
const xml1 = path.join(pasta, "nota-1.xml");
const xml2 = path.join(pasta, "nota-2.xml");
fs.writeFileSync(xml1, nfe(1, "2025-03-10"));
fs.writeFileSync(xml2, nfe(2, "2025-04-10"));

// 1. Link de envio: o escritório gera, o cliente envia sem login
await page.goto(`${BASE}/clientes/${cliente.id}?aba=movimento`);
await page.getByRole("heading", { name: "Receber notas do cliente" }).waitFor();
await page.getByRole("button", { name: "Gerar link de envio" }).click();
const campoLink = page.getByLabel("Link de envio de notas");
await campoLink.waitFor();
const link = (await campoLink.inputValue()).replace(/^https?:\/\/[^/]+/, BASE);
const zap = await page.getByLabel("Mensagem para o WhatsApp").inputValue();
if (!zap.includes("Marcos") || !zap.includes("Contabilidade Notas Fáceis")) throw new Error(`mensagem inesperada: ${zap}`);
await page.screenshot({ path: `${OUT}/notas-1-link.png`, fullPage: true });
passo("escritório gera o link de envio e a mensagem de WhatsApp vem pronta");

const cli = await browser.newContext({ viewport: { width: 390, height: 800 } }); // celular do cliente, sem sessão
const anonimo = await cli.newPage();
vigiar(anonimo);
await anonimo.goto(link);
await anonimo.getByRole("heading", { name: "Mercadinho Boa Compra Ltda" }).waitFor();
await anonimo.setInputFiles('input[aria-label="Arquivos de notas"]', [xml1, xml2]);
await anonimo.getByText("2 recebidas · 0 já existiam · 0 ignoradas").waitFor();
await anonimo.screenshot({ path: `${OUT}/notas-2-cliente-celular.png`, fullPage: true });
if ((await anonimo.evaluate(() => document.documentElement.scrollWidth)) > 390) throw new Error("rolagem horizontal na página do cliente");
await anonimo.setInputFiles('input[aria-label="Arquivos de notas"]', [xml1]);
await anonimo.getByText("0 recebidas · 1 já existiam · 0 ignoradas").waitFor();
passo("cliente envia 2 XML sem login (celular) e a repetição é ignorada");

await page.reload();
await page.getByText("Recebeu 2 notas em 2 envios").waitFor();
await page.getByText("Vendas (últimos 2 meses)").waitFor();
passo("as notas aparecem no movimento fiscal do cliente");

page.once("dialog", (d) => d.accept());
await page.getByRole("button", { name: "Desativar" }).click();
await page.getByRole("button", { name: "Gerar link de envio" }).waitFor();
await anonimo.reload();
await anonimo.getByText(/não está mais ativo|não encontrado|inválido/i).first().waitFor();
passo("link desativado deixa de funcionar");

// 2. Dados contábeis por planilha (CSV com colunas fora de ordem, para provar o mapeamento)
const linhas = ["Mês;Observação;Folha de pagamento;Faturamento;Compras;Pró-labore"];
for (let m = 1; m <= 12; m++) linhas.push(`2025-${String(m).padStart(2, "0")};ok;${m === 12 ? "R$ 1.500,00" : "1500,00"};10000,00;6000,00;500,00`);
linhas.push("xx;lixo;1;1;1;1");
const csv = path.join(pasta, "contabil.csv");
fs.writeFileSync(csv, "﻿" + linhas.join("\n"));
const dados = page.getByRole("heading", { name: "Dados contábeis (planilha)" });
await dados.waitFor();
await page.setInputFiles('input[aria-label="Planilha de dados contábeis"]', csv);
const mapeamento = page.getByLabel("Mapeamento de colunas");
await mapeamento.waitFor();
if ((await mapeamento.getByLabel("Receita (faturamento)").inputValue()) !== "3") throw new Error("a coluna Faturamento não foi sugerida para a receita");
if ((await mapeamento.getByLabel("Folha de salários").inputValue()) !== "2") throw new Error("a coluna Folha de pagamento não foi sugerida");
await page.screenshot({ path: `${OUT}/notas-3-mapeamento.png`, fullPage: true });
await mapeamento.getByRole("button", { name: "Importar dados" }).click();
await page.getByText("12 meses novos · 0 atualizados · 1 linhas ignoradas").waitFor();
await page.getByText("Base do planejamento: jan/25 a dez/25 — receita anual R$ 120.000,00").waitFor();
await page.screenshot({ path: `${OUT}/notas-4-planilha.png`, fullPage: true });
passo("planilha com colunas fora de ordem: sugestão pelo cabeçalho, importação e linha inválida explicada");

await page.getByRole("button", { name: "Usar no planejamento" }).first().click();
await page.getByText("Valores da planilha de jan/25 a dez/25").waitFor();
if ((await page.locator("#receita").inputValue()) !== "120.000,00") throw new Error("receita anual não preenchida");
if ((await page.locator("#folha_anual").inputValue()) !== "18.000,00") throw new Error("folha anual não preenchida");
if ((await page.locator("#prolabore_anual").inputValue()) !== "6.000,00") throw new Error("pró-labore anual não preenchido");
await page.screenshot({ path: `${OUT}/notas-5-planejamento.png`, fullPage: true });
passo("planejamento preenchido com receita, compras, folha e pró-labore da planilha");

// 3. Caixa de e-mail nas Configurações
await page.goto(`${BASE}/configuracoes`);
await page.getByRole("heading", { name: "Caixa de entrada de notas (e-mail)" }).waitFor();
await page.fill("#imap_host", "localhost");
await page.fill("#imap_usuario", "notas@escritorio.com.br");
await page.fill("#imap_senha", "senha-da-caixa");
await page.getByRole("button", { name: "Salvar", exact: true }).last().click();
await page.getByText("Esse endereço aponta para uma rede interna e não é aceito.").waitFor();
passo("servidor IMAP em rede interna é recusado (proteção contra SSRF)");

await page.fill("#imap_host", "93.184.216.34");
await page.getByRole("button", { name: "Salvar", exact: true }).last().click();
await page.getByText("Caixa de e-mail salva.").waitFor();
await page.reload();
await page.waitForFunction(() => document.querySelector("#imap_usuario")?.value === "notas@escritorio.com.br", null, { timeout: 10000 })
  .catch(() => { throw new Error("caixa não gravada"); });
if ((await page.getByLabel("Senha", { exact: true }).last().inputValue()) !== "") throw new Error("a senha não pode voltar do servidor");
await page.getByRole("button", { name: "Verificar agora" }).click();
await page.getByLabel("Última verificação").waitFor({ timeout: 60000 });
await page.screenshot({ path: `${OUT}/notas-6-caixa-email.png`, fullPage: true });
passo("caixa de e-mail salva sem devolver a senha; a verificação mostra o resultado (ou o erro) sem quebrar");

// 4. Aviso de notas paradas (última competência é mar/25 → abr/25 foi a última importada: bem antes de hoje)
await page.goto(`${BASE}/avisos`);
await page.getByText("Notas paradas desde abr/25").waitFor();
passo("central de avisos aponta cliente ativo com notas paradas");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
