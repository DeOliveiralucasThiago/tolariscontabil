// Lucro Presumido e Lucro Real a partir de 2027: CBS e IBS no lugar de PIS e Cofins, no planejamento completo e na prospecção.
// Sem rede externa. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const corpo = async () => (await page.innerText("body")).replace(/ /g, " ");
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1300 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Reforma 2027");
await page.fill("#nome", "Rita Contadora");
await page.fill("#email", `rita-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-regimes-2027-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cid = (await api("POST", "/clientes", { data: { razao_social: "Consultoria Reforma Ltda", atividade: "servico_fator_r", regime_atual: "simples" } })).id;

const abrir = async () => {
  await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
  await page.getByTestId("bloco-ano").waitFor();
  await page.fill("#receita", "90000000");        // máscara: dígitos são centavos
  await page.fill("#folha_anual", "20000000");
  await page.fill("#prolabore_anual", "6000000");
};

// 1. 2026 (padrão): PIS e Cofins no Presumido, sem CBS
await abrir();
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
let texto = await corpo();
if (!texto.includes("Cofins")) throw new Error("2026 deveria mostrar a Cofins");
passo("2026: Presumido e Real seguem com PIS e Cofins");

// 2. 2027: CBS e IBS no lugar de PIS e Cofins
await abrir();
await page.getByTestId("bloco-ano").locator("summary").click();
await page.selectOption("#ano_apuracao", "2027");
await page.getByText("a CBS e o IBS entram no lugar de PIS e Cofins").waitFor();
await page.waitForSelector("#reducao_ibs_cbs");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
texto = await corpo();
if (!/CBS/.test(texto) || !/IBS/.test(texto)) throw new Error("2027 deveria mostrar CBS e IBS");
if (/Cofins\s+R\$/.test(texto)) throw new Error("2027 não deveria mostrar a Cofins como tributo");
if (!texto.includes("regime normal paga CBS e IBS")) throw new Error("o alerta de premissas de 2027 não apareceu");
await page.screenshot({ path: `${OUT}/regimes_2027.png`, fullPage: true });
passo("2027: Presumido e Real mostram CBS e IBS e o alerta das premissas");

// 3. Redução de 30%: a CBS do Presumido cai
const cbs = async () => {
  const t = await corpo();
  const m = t.match(/^CBS\s+—\s+R\$\s*([\d.]+,\d{2})/m);   // linha da tabela: Simples (—), Presumido, Real
  if (!m) throw new Error("CBS do Presumido não encontrada");
  return Number(m[1].replace(/\./g, "").replace(",", "."));
};
const cheia = await cbs();
await abrir();
await page.getByTestId("bloco-ano").locator("summary").click();
await page.selectOption("#ano_apuracao", "2027");
await page.selectOption("#reducao_ibs_cbs", "0.3");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const reduzida = await cbs();
if (Math.abs(reduzida - cheia * 0.7) > 1) throw new Error(`CBS com 30% de redução esperada ${cheia * 0.7}, veio ${reduzida}`);
passo("redução de 30%: a CBS cai de " + cheia + " para " + reduzida);

// 4. Prospecção (simulação expressa) com ano 2029
await page.goto(`${BASE}/prospeccao`);
await page.selectOption("#atividade", "servico_fator_r");
await page.fill("#faturamento", "5000000");
await page.fill("#folha", "1000000");
await page.selectOption("#ano_previa", "2029");
await page.getByRole("button", { name: "Calcular previsão" }).click();
await page.getByText("Regime recomendado").waitFor();
texto = await corpo();
if (!/IBS/.test(texto) || /Cofins\s+R\$/.test(texto)) throw new Error("A previsão de 2029 deveria trazer IBS e não Cofins");
await page.screenshot({ path: `${OUT}/prospeccao_2029.png`, fullPage: true });
passo("prospecção com ano 2029 mostra IBS");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo dos regimes de 2027 em diante concluído.");
