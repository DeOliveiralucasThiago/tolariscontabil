// Conferência dos impedimentos do Simples (LC 123, art. 3º, § 4º, e art. 17): respostas no cadastro, simulação, cabeçalho e Central de Avisos.
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
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1600 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Impedimentos");
await page.fill("#nome", "Ivo Contador");
await page.fill("#email", `ivo-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-impedimentos-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const cid = (await (await page.request.post(BASE + "/api/clientes", { data: { razao_social: "Serviços Gerais Ltda", atividade: "servico_anexo_iii", regime_atual: "simples", status: "ativo", natureza_juridica: "Sociedade Empresária Limitada" } })).json()).id;

// 1. A conferência começa vazia
await page.goto(`${BASE}/clientes/${cid}?aba=dados`);
const conf = page.getByTestId("conferencia-impedimentos");
await conf.waitFor();
if (!(await page.getByTestId("veredito-impedimentos").innerText()).includes("23 por responder")) throw new Error("a conferência deveria começar com 23 perguntas por responder");
passo("a conferência lista as 23 perguntas, todas por responder");

// 2. Cessão de mão de obra: impedimento do art. 17, XII
await page.selectOption("#imp_cessao_mao_de_obra", "sim");
await page.getByRole("button", { name: "Salvar conferência" }).click();
await page.getByText("Conferência salva.").waitFor();
const achados = await page.getByTestId("impedimentos-achados").innerText();
if (!achados.includes("Cessão ou locação de mão de obra") || !achados.includes("art. 17, XII")) throw new Error("achado errado: " + achados);
if (!(await page.getByTestId("veredito-impedimentos").innerText()).includes("Há impedimento ao Simples")) throw new Error("faltou o veredito");
await page.screenshot({ path: `${OUT}/impedimentos_conferencia.png`, fullPage: true });
await page.waitForFunction(() => document.querySelector('[data-testid="impedimento-do-cliente"]'));
passo("sim em cessão de mão de obra: impedimento (art. 17, XII) e etiqueta no cabeçalho do cliente");

// 3. Impedimento que depende da receita global
await page.selectOption("#imp_cessao_mao_de_obra", "nao");
await page.selectOption("#imp_socio_administrador_de_outra", "sim");
await page.getByRole("button", { name: "Salvar conferência" }).click();
await page.getByText("Depende da receita").waitFor();
await page.check("#tem_outras");
await page.fill("#receita_outras", "100000000");   // R$ 1.000.000,00 das outras empresas
await page.fill("#receita_desta", "60000000");     // R$ 600.000,00 desta: global de R$ 1,6 mi, abaixo de R$ 4,8 mi
await page.getByRole("button", { name: "Salvar conferência" }).click();
await page.waitForFunction(() => !document.querySelector('[data-testid="impedimentos-achados"]'));
passo("sócio administrador de outra empresa só impede se a receita global passar de R$ 4,8 milhões");

// 4. Simulação: com o impedimento confirmado, o Simples não se aplica
await page.selectOption("#imp_cessao_mao_de_obra", "sim");
await page.getByRole("button", { name: "Salvar conferência" }).click();
await page.getByText("Conferência salva.").waitFor();
await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
await page.fill("#receita", "60000000");
await page.fill("#folha_anual", "10000000");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
const t = await corpo();
if (/Regime recomendado\s*Simples Nacional/.test(t)) throw new Error("o Simples não deveria ser o recomendado com impedimento");
if (!/Impedimento ao Simples Nacional confirmado no cadastro/.test(t)) throw new Error("o alerta do impedimento não apareceu no planejamento");
passo("planejamento: o Simples não se aplica e o alerta cita o impedimento");

// 5. Central de Avisos
await page.goto(`${BASE}/avisos`);
await page.getByText("Impedimento ao Simples Nacional confirmado no cadastro (1)").first().waitFor();
await page.screenshot({ path: `${OUT}/impedimentos_avisos.png`, fullPage: true });
passo("a Central de Avisos marca o cliente do Simples como crítico");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo dos impedimentos do Simples concluído.");
