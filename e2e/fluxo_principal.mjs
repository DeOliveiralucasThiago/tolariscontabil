// Fluxo principal no navegador: cadastro → marca → prospecção com CNPJ → PDF → planejamento → painel.
// Uso: veja e2e/README.md
import fs from "fs";
import path from "path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
const LOGO = process.argv[3] ?? path.join(path.dirname(new URL(import.meta.url).pathname), "logo.png");
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));
const passo = (t) => console.log("✓", t);

// 1. Rota protegida redireciona para login
await page.goto(`${BASE}/painel`);
await page.waitForURL("**/login");
passo("sem sessão → login");

// 2. Cadastro
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Silva & Associados Contabilidade");
await page.fill("#nome", "Marcos Silva");
await page.fill("#email", "marcos@silva.com.br");
await page.fill("#senha", "senha-forte-123");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
passo("cadastro → configurações");

// 3. Configurações: cor, CRC e logo
await page.fill("#crc", "SP-123456/O-7");
await page.fill("#telefone", "(19) 3222-1111");
await page.locator("#cor").evaluate((el) => {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
  set.call(el, "#0f5e4a"); el.dispatchEvent(new Event("input", { bubbles: true }));
});
await page.getByRole("button", { name: "Salvar", exact: true }).click();
await page.getByText("Dados salvos.").waitFor();
await page.setInputFiles("input[type=file]", LOGO);
await page.getByAltText("Logo do escritório").waitFor();
await page.screenshot({ path: `${OUT}/1-configuracoes.png` });
passo("marca do escritório salva");

// 4. Prospecção com consulta de CNPJ
await page.click("text=Prospecção");
await page.waitForURL("**/prospeccao");
await page.fill("#cnpj", "11222333000181");
await page.getByRole("button", { name: "Buscar" }).click();
await page.getByText("TECH SOLUCOES EM SOFTWARE LTDA · ATIVA").waitFor();
const atividade = await page.inputValue("#atividade");
if (atividade !== "servico_fator_r") throw new Error("atividade sugerida errada: " + atividade);
passo("CNPJ preenchido e atividade sugerida (fator R)");
await page.fill("#faturamento", "5000000");   // R$ 50.000,00
await page.fill("#folha", "800000");          // R$ 8.000,00
await page.fill("#prolabore", "500000");      // R$ 5.000,00
await page.getByRole("button", { name: "Calcular previsão" }).click();
await page.getByText("Regime recomendado").waitFor();
const economia = await page.locator("text=Economia estimada").locator("..").innerText();
await page.screenshot({ path: `${OUT}/2-prospeccao.png`, fullPage: true });
passo("comparativo calculado: " + economia.replace(/\s+/g, " "));
await page.getByRole("button", { name: "Salvar prospect e gerar proposta" }).click();
const linkPdf = page.getByRole("link", { name: "Abrir proposta em PDF" });
await linkPdf.waitFor();
const href = await linkPdf.getAttribute("href");
const pdf = await page.request.get(BASE + href);
if (pdf.headers()["content-type"] !== "application/pdf") throw new Error("PDF não veio");
fs.writeFileSync(`${OUT}/proposta.pdf`, await pdf.body());
passo("prospect salvo e PDF baixado (" + (await pdf.body()).length + " bytes)");

// 5. Cliente: planejamento completo
await page.getByRole("link", { name: "Ver cliente" }).click();
await page.waitForURL(/\/clientes\/\d+$/);
await page.getByRole("tab", { name: "Novo planejamento" }).click();
await page.fill("#receita", "120000000");            // R$ 1.200.000,00
await page.fill("#folha_anual", "18000000");
await page.fill("#prolabore_anual", "6000000");
await page.fill("#outras", "30000000");
await page.getByRole("button", { name: "Calcular e salvar planejamento" }).click();
await page.getByText("Planejamento tributário 2026").first().waitFor();
await page.getByText("Regime recomendado").waitFor();
await page.locator("summary", { hasText: "Simples Nacional" }).click();
await page.screenshot({ path: `${OUT}/3-cliente.png`, fullPage: true });
passo("planejamento completo salvo no cliente");

// 6. Lista de clientes e painel
await page.click("text=Clientes");
await page.getByText("TECH SOLUCOES EM SOFTWARE LTDA").waitFor();
await page.click("text=Painel");
await page.getByText("Últimas simulações").waitFor();
await page.screenshot({ path: `${OUT}/4-painel.png`, fullPage: true });
passo("painel com simulações");

// 7. Celular
const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, storageState: await ctx.storageState() });
const mp = await mobile.newPage();
await mp.goto(`${BASE}/prospeccao`);
await mp.getByText("Prospecção rápida").waitFor();
const larg = await mp.evaluate(() => document.documentElement.scrollWidth);
await mp.screenshot({ path: `${OUT}/5-celular.png`, fullPage: true });
passo("celular: largura de rolagem " + larg + "px (viewport 390)");

// 8. Sair
await page.click("text=Sair");
await page.waitForURL("**/login");
passo("logout");
await browser.close();
// O 401 do passo 1 (acesso sem sessão) é esperado
const inesperados = erros.filter((e) => !e.includes("401"));
console.log(inesperados.length ? "ERROS NO CONSOLE:\n" + inesperados.join("\n") : "Sem erros inesperados no console");
process.exit(inesperados.length ? 1 : 0);
