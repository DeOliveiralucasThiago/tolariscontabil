// Sociedade de profissionais (ISS fixo) e serviços hospitalares no planejamento completo.
// Sem rede externa. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const corpo = async () => (await page.innerText("body")).replace(/\u00a0/g, " ");   // o site usa espaço sem quebra depois de R$
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1200 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Profissionais");
await page.fill("#nome", "Paula Contadora");
await page.fill("#email", `paula-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-profissionais-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cid = (await api("POST", "/clientes", { data: { razao_social: "Advocacia Exemplo & Associados", atividade: "servico_anexo_iv", regime_atual: "simples" } })).id;

const abrir = async () => {
  await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
  await page.getByTestId("bloco-profissionais").waitFor();
};
const preencherBase = async () => {
  await page.fill("#receita", "60000000");        // máscara: dígitos são centavos
  await page.fill("#prolabore_anual", "3600000");
  await page.fill("#outras", "6000000");
};
// 1. Sem a opção: ISS de 5% da receita no Presumido
await abrir();
await preencherBase();
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const textoNormal = await corpo();
if (!textoNormal.includes("R$ 30.000,00")) throw new Error("ISS de 5% (R$ 30.000,00) não apareceu no cálculo normal");
passo("sem a opção, o ISS é 5% da receita");

// 2. Com ISS fixo de 3 profissionais x R$ 1.800
await abrir();
await preencherBase();
const bloco = page.getByTestId("bloco-profissionais");
await bloco.locator("summary").click();
await page.check("#sociedade_profissionais");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Informe a quantidade de profissionais e o ISS fixo anual de cada um.").waitFor();
passo("sem profissionais e valor, a tela avisa");
await page.fill("#profissionais", "3");
await page.fill("#iss_fixo_profissional", "180000");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(500);
const texto = await corpo();
for (const trecho of ["R$ 5.400,00", "ISS fixo", "Confirme o enquadramento"]) {
  if (!texto.includes(trecho)) throw new Error(`resultado com ISS fixo sem “${trecho}”`);
}
if (texto.includes("R$ 30.000,00")) throw new Error("o ISS de 5% não deveria aparecer com o ISS fixo");
await page.screenshot({ path: `${OUT}/profissionais_1_iss_fixo.png`, fullPage: true });
passo("ISS fixo de R$ 5.400,00 (3 x R$ 1.800,00) no Presumido e no Real, com o aviso de enquadramento");

// 3. Serviços hospitalares
await abrir();
await page.selectOption("select[name=atividade_completa]", "servico_fator_r");
await page.fill("#receita", "120000000");
await page.fill("#folha_anual", "30000000");
await page.fill("#prolabore_anual", "6000000");
await bloco.locator("summary").click();
await page.check("#servicos_hospitalares");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(500);
const hosp = await corpo();
for (const trecho of ["R$ 14.400,00", "Serviços hospitalares", "Anvisa"]) {
  if (!hosp.includes(trecho)) throw new Error(`resultado hospitalar sem “${trecho}”`);
}
await page.screenshot({ path: `${OUT}/profissionais_2_hospitalar.png`, fullPage: true });
passo("serviços hospitalares: IRPJ de R$ 14.400,00 no Presumido, com o aviso da Anvisa");

// 3b. Escritório de serviços contábeis: ISS fixo também no Simples (a opção só aparece no Anexo III)
await abrir();
await page.selectOption("select[name=atividade_completa]", "servico_anexo_iii");
await preencherBase();
await bloco.locator("summary").click();
await page.check("#sociedade_profissionais");
await page.fill("#profissionais", "2");
await page.fill("#iss_fixo_profissional", "150000");
await page.check("#iss_fixo_no_simples");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const contabil = await corpo();
for (const trecho of ["R$ 42.768,00", "ISS fixo (recolhido ao Município, fora do DAS)", "R$ 45.768,00", "Res. CGSN 140/2018, art. 34"]) {
  if (!contabil.includes(trecho)) throw new Error(`escritório contábil sem “${trecho}”`);
}
await page.screenshot({ path: `${OUT}/profissionais_3_contabil.png`, fullPage: true });
passo("escritório contábil: DAS de R$ 42.768,00 (sem o ISS) e ISS fixo de R$ 3.000,00 ao Município");
await abrir();
await page.selectOption("select[name=atividade_completa]", "servico_anexo_iv");
await bloco.locator("summary").click();
await page.check("#sociedade_profissionais");
if ((await page.locator("#iss_fixo_no_simples").count()) !== 0) throw new Error("a opção do contábil não deveria aparecer fora do Anexo III");
passo("a opção do ISS fixo no Simples só aparece no Anexo III");

// 4. Atividade de mercadoria não oferece o bloco
await abrir();
await page.selectOption("select[name=atividade_completa]", "comercio");
if ((await page.getByTestId("bloco-profissionais").count()) !== 0) throw new Error("comércio não deveria mostrar o bloco de profissionais");
passo("comércio não mostra o bloco");

if (erros.length) { console.log("Erros no console:", erros.slice(0, 3)); process.exit(1); }
console.log("Sem erros no console");
await browser.close();
