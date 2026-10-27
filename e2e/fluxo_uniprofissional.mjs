// Reforma Tributária para sociedades uniprofissionais: ISS fixo na transição e redução de 30% do art. 127 da LC 214/2025,
// na calculadora da Reforma e no planejamento completo. Sem rede externa. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const corpo = async () => (await page.innerText("body")).replace(/ /g, " ");
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1500 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Uniprofissional");
await page.fill("#nome", "Lia Contadora");
await page.fill("#email", `lia-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-uniprofissional-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// 1. Calculadora da Reforma: sociedade com ISS fixo, advogados (30%)
await page.goto(`${BASE}/reforma`);
await page.fill("#receita_ref", "60000000");
await page.getByTestId("bloco-uniprofissional").waitFor();
await page.check("#uni_ativa");
await page.fill("#uni_profissionais", "3");
await page.fill("#uni_iss_fixo", "100000");        // R$ 1.000,00 por profissional (centavos)
await page.selectOption("#uni_profissao", "Advogados");
await page.getByTestId("requisitos-art-127").waitFor();
if (!(await page.inputValue("#reducao_ref")).startsWith("0.3")) throw new Error("a profissão deveria marcar a redução de 30%");
passo("profissão do art. 127 marca a redução de 30% e mostra os requisitos");
await page.getByRole("button", { name: "Simular transição" }).click();
await page.getByText("Carga sobre o consumo em 2033").first().waitFor();
const texto = await corpo();
if (!texto.includes("não traz regra própria")) throw new Error("o alerta do ISS fixo na transição não apareceu");
await page.screenshot({ path: `${OUT}/uniprofissional_reforma.png`, fullPage: true });
passo("a Reforma mostra o alerta do ISS fixo na transição");

// 2. Sem informar profissionais e valor, a tela avisa
await page.goto(`${BASE}/reforma`);
await page.fill("#receita_ref", "60000000");
await page.check("#uni_ativa");
await page.getByRole("button", { name: "Simular transição" }).click();
await page.getByText("Informe a quantidade de profissionais e o ISS fixo anual de cada um.").waitFor();
passo("sem profissionais e valor, a tela avisa");

// 3. Comércio não mostra o bloco
await page.selectOption("#vende", "m");
if (await page.getByTestId("bloco-uniprofissional").count()) throw new Error("o bloco de uniprofissional não deveria aparecer para mercadorias");
passo("o bloco não aparece para mercadorias");

// 4. Planejamento completo: a profissão preenche a redução de 2027
const cid = (await (await page.request.post(BASE + "/api/clientes", { data: { razao_social: "Advocacia Reforma", atividade: "servico_anexo_iv", regime_atual: "simples" } })).json()).id;
await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
await page.getByTestId("bloco-profissionais").waitFor();
await page.fill("#receita", "60000000");
await page.fill("#prolabore_anual", "3600000");
await page.fill("#outras", "6000000");
await page.getByTestId("bloco-profissionais").locator("summary").click();
await page.check("#sociedade_profissionais");
await page.fill("#profissionais", "3");
await page.fill("#iss_fixo_profissional", "180000");
await page.selectOption("#profissao", "Advogados");
await page.getByTestId("bloco-ano").locator("summary").click();
await page.selectOption("#ano_apuracao", "2027");
if (!(await page.inputValue("#reducao_ibs_cbs")).startsWith("0.3")) throw new Error("a redução de 30% deveria vir da profissão");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const t2 = await corpo();
if (!t2.includes("Redução de 30%")) throw new Error("o alerta da redução de 30% não apareceu");
if (!t2.includes("não traz regra própria")) throw new Error("o alerta do ISS fixo não apareceu");
await page.screenshot({ path: `${OUT}/uniprofissional_completa.png`, fullPage: true });
passo("planejamento de 2027 com ISS fixo e redução de 30% vinda da profissão");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo das sociedades uniprofissionais concluído.");
