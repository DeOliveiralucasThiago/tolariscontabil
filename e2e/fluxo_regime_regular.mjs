// Aviso do prazo da opção pelo regime regular de IBS/CBS (até 30/10/2026): aparece na central de avisos para clientes do Simples
// e leva ao Simples na Reforma já com a receita e a atividade do cliente. O aviso some depois do prazo, então o fluxo só roda até lá.
import fs from "fs";
import { chromium } from "playwright";

if (new Date() > new Date("2026-10-31T00:00:00-03:00")) {
  console.log("O prazo de 30/10/2026 já passou: o aviso não existe mais. Nada a testar.");
  process.exit(0);
}
const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const page = await (await browser.newContext({ viewport: { width: 1360, height: 1100 } })).newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Prazo");
await page.fill("#nome", "Rita Contadora");
await page.fill("#email", `rita-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-prazo-12345678");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cid = (await api("POST", "/clientes", { data: { razao_social: "Comércio do Prazo Ltda", atividade: "comercio", regime_atual: "simples" } })).id;
await api("POST", `/clientes/${cid}/simulacoes/completa`, { data: { atividade: "comercio", receita_bruta_anual: 2000000, compras_anual: 1200000 } });

await page.goto(`${BASE}/avisos`);
const aviso = page.locator("li").filter({ hasText: "Regime regular de IBS/CBS em 2027" }).first();
await aviso.waitFor();
const texto = (await aviso.innerText()).replace(/ /g, " ");
for (const trecho of ["até 30/10/2026", "Comércio do Prazo Ltda", "compensa a partir de", "03/11 a 20/12/2026"]) {
  if (!texto.includes(trecho)) throw new Error(`aviso sem “${trecho}”: ${texto}`);
}
await page.screenshot({ path: `${OUT}/regime_regular_1_aviso.png`, fullPage: true });
passo("a central de avisos mostra o prazo do regime regular, com o ponto de equilíbrio do cliente");

await aviso.getByRole("link", { name: "Simular o Simples na Reforma" }).click();
await page.waitForURL(/\/reforma\?aba=simples&cliente=\d+&receita=2000000&atividade=comercio/);
await page.locator("#receita_sr").waitFor();
const receita = await page.inputValue("#receita_sr");
if (!/2\.000\.000,00/.test(receita)) throw new Error(`a receita do cliente não veio preenchida: ${receita}`);
const atividade = await page.locator("select[name=atividade_sr]").inputValue();
if (atividade !== "comercio") throw new Error(`atividade do cliente não veio preenchida: ${atividade}`);
passo("o botão abre o Simples na Reforma com a receita e a atividade do cliente");

if (erros.length) { console.log("Erros no console:", erros.slice(0, 3)); process.exit(1); }
console.log("Sem erros no console");
await browser.close();
