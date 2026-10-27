// Segregações do art. 25 da Res. CGSN 140/2018: locação de bens móveis, transporte intermunicipal e comunicação no planejamento completo.
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
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1400 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Segregações");
await page.fill("#nome", "Sara Contadora");
await page.fill("#email", `sara-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-segregacoes-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const cid = (await (await page.request.post(BASE + "/api/clientes", { data: { razao_social: "Locadora e Transportes Ltda", atividade: "locacao_bens_moveis", regime_atual: "simples" } })).json()).id;

const abrir = async () => {
  await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
  await page.getByTestId("bloco-atividades-mistas").waitFor();
  await page.waitForTimeout(600);
  await page.fill("#receita", "60000000");        // R$ 600.000,00 (máscara: centavos)
  await page.fill("#folha_anual", "10000000");
};
const resultado = async () => {
  await page.click("text=Calcular e salvar planejamento");
  await page.getByText("Regime recomendado").first().waitFor();
  await page.waitForTimeout(800);
};
const das = async () => {
  const m = (await corpo()).match(/^DAS\s+R\$\s*([\d.]+,\d{2})/m);
  if (!m) throw new Error("linha do DAS não encontrada");
  return Number(m[1].replace(/\./g, "").replace(",", "."));
};

// 1. Locação de bens móveis (atividade do cadastro): Anexo III sem ISS = R$ 42.768,00
await abrir();
const ativ = await page.inputValue("#atividade_completa").catch(() => "");
await resultado();
if ((await das()) !== 42768) throw new Error("DAS da locação deveria ser 42.768,00");
if (!/partilha ajustada/.test(await corpo())) throw new Error("faltou o aviso da partilha ajustada");
await page.screenshot({ path: `${OUT}/segregacoes_locacao.png`, fullPage: true });
passo("locação de bens móveis: DAS de R$ 42.768,00 (Anexo III sem a parcela do ISS) e aviso da partilha ajustada");

// 2. Mais R$ 300 mil de comunicação como outra atividade: duas partes no DAS, cada uma com a sua partilha
await abrir();
await page.getByTestId("bloco-atividades-mistas").locator("summary").click();
await page.fill("#outra_comunicacao_icms", "30000000");
await resultado();
const texto = await corpo();
if (!/Anexo III sem a parcela do ISS e com a do ICMS do Anexo I/.test(texto)) throw new Error("faltou a parte da comunicação com ICMS");
await page.screenshot({ path: `${OUT}/segregacoes_mista.png`, fullPage: true });
passo("locação + comunicação: o aviso lista as duas partes, cada uma com o seu ajuste");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo das segregações do art. 25 concluído.", ativ ? `(atividade do formulário: ${ativ})` : "");
