// Enquadramento: CNAEs secundários vêm da Receita ao cadastrar o cliente, aparecem classificados na tela de
// enquadramento, e a análise compara os caminhos para o Anexo III (pró-labore e atividade do Anexo III).
// Precisa do mock_brasilapi.py (CNPJ 11.222.333/0001-81 com dois CNAEs secundários). E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1100 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Enquadramento");
await page.fill("#nome", "Iara Contadora");
await page.fill("#email", `iara-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-enquadra-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};

// 1. Cadastro pela busca de CNPJ guarda os CNAEs secundários
await page.goto(`${BASE}/clientes/novo`);
await page.fill("#cnpj", "11222333000181");
await page.getByRole("button", { name: "Buscar" }).click();
await page.getByText("2 CNAE(s) secundário(s)").waitFor();
await page.getByRole("button", { name: /Cadastrar|Salvar/ }).first().click();
await page.waitForURL(/\/clientes\/\d+$/);
const clienteId = Number(page.url().split("/").pop());
const guardado = await api("GET", `/clientes/${clienteId}`);
if (guardado.cnaes_secundarios?.length !== 2) throw new Error(`secundários não guardados: ${JSON.stringify(guardado.cnaes_secundarios)}`);
passo("CNPJ trouxe e guardou os 2 CNAEs secundários");

// 2. Tela de enquadramento do cliente: CNAEs classificados e candidato ao Anexo III
await page.goto(`${BASE}/enquadramento?cliente=${clienteId}`);
await page.getByRole("heading", { name: "Enquadramento" }).waitFor();
const cartao = page.getByTestId("cnaes-do-cliente");
await cartao.waitFor();
const textoCnaes = await cartao.innerText();
for (const trecho of ["6201-5/01", "principal", "8599-6/04", "Anexo III ou V (fator R)", "Treinamento em desenvolvimento"]) {
  if (!textoCnaes.includes(trecho)) throw new Error(`cartão de CNAEs sem “${trecho}”: ${textoCnaes}`);
}
const cand = await page.getByTestId("candidatos-anexo-iii").innerText();
if (!cand.includes("Treinamento")) throw new Error(`candidato ao Anexo III ausente: ${cand}`);
if (!/não sugere CNAEs que a empresa ainda não tem/.test(textoCnaes)) throw new Error("faltou o aviso de que o Tolaris não sugere CNAEs novos");
await page.screenshot({ path: `${OUT}/enquadramento_1_cnaes.png`, fullPage: true });
passo("CNAEs do cliente classificados, com candidato ao Anexo III e aviso");

// 3. Análise dos caminhos (fator R de 6%: Anexo V hoje)
await page.fill("#receita", "60000000");       // máscara: dígitos são centavos
await page.fill("#prolabore_anual", "3600000");
await page.fill("#outras", "6000000");
await page.fill("#percentual_iii", "30");
await page.getByRole("button", { name: "Analisar enquadramento" }).click();
const res = page.getByTestId("resultado-enquadramento");
await res.waitFor();
const t = await res.innerText();
for (const trecho of ["Como está hoje", "Pró-labore +", "25% da receita", "30% da receita", "50% da receita", "100% da receita", "Fator R hoje: 6,00%", "exercida de fato"]) {
  if (!t.includes(trecho)) throw new Error(`resultado sem “${trecho}”: ${t}`);
}
if (!(await page.getByText("Economia por ano").first().isVisible())) throw new Error("sem destaque de economia");
await page.screenshot({ path: `${OUT}/enquadramento_2_resultado.png`, fullPage: true });
passo("análise mostra hoje, pró-labore e 25/30/50/100% no Anexo III, com o aviso de risco");

// 4. Salvar no cliente e abrir o PDF
await page.getByRole("button", { name: /Salvar/ }).first().click();
await page.getByRole("link", { name: /PDF|relatório|proposta/i }).first().waitFor();
const sims = await api("GET", `/clientes/${clienteId}/simulacoes`);
const sim = sims.find((s) => s.tipo === "enquadramento");
if (!sim) throw new Error("simulação de enquadramento não ficou no histórico");
const pdf = await page.request.get(`${BASE}/api/simulacoes/${sim.id}/proposta.pdf`);
if (!pdf.ok() || !(await pdf.body()).subarray(0, 4).equals(Buffer.from("%PDF"))) throw new Error("PDF do enquadramento inválido");
passo("simulação salva no histórico e PDF gerado");

// 5. Menu e celular
await page.setViewportSize({ width: 390, height: 800 });
await page.goto(`${BASE}/enquadramento`);
await page.getByRole("heading", { name: "Enquadramento" }).waitFor();
const larg = await page.evaluate(() => document.documentElement.scrollWidth);
if (larg > 392) throw new Error(`rolagem horizontal no celular: ${larg}px`);
passo("sem rolagem horizontal no celular");

await browser.close();
if (erros.length) {
  console.error("Erros no console:", erros);
  process.exit(1);
}
console.log("OK");
