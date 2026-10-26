// Capturas extras da apresentação: Simples na Reforma (sete anos), Pessoa física e Mudanças na legislação.
// Cria o próprio escritório fictício (Contabilidade Horizonte), então rode com um banco novo e o site SEM TOLARIS_AMBIENTE_TESTE.
//   node capturas_apresentacao_extra.mjs <pasta de saída>
import fs from "fs";
import { chromium } from "playwright";
const BASE = "http://127.0.0.1:3000";
const OUT = process.argv[2];
fs.mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: "pt-BR" });
const page = await ctx.newPage();
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Horizonte");
await page.fill("#nome", "Lia Contadora");
await page.fill("#email", "lia@horizonte.example");
await page.fill("#senha", "senha-horizonte-2026");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const moeda = (sel, centavos) => page.fill(sel, String(centavos));
const ESC = "div.fixed.bottom-4.right-4 { display: none !important; }";
const quieto = () => page.waitForLoadState("networkidle").catch(() => undefined);

// 1. Simples na Reforma, sete anos
await page.goto(`${BASE}/reforma?aba=simples`);
await page.getByRole("tab", { name: "Simples: IBS/CBS no DAS ou por fora" }).click();
await moeda("#receita_sr", 200000000);
await page.locator("#b2b").fill("80");
await moeda("#compras_sr", 120000000);
await page.getByRole("button", { name: "Comparar opções" }).click();
await page.getByText("Recomendação para 2033").waitFor();
await quieto(); await page.waitForTimeout(800);
await page.addStyleTag({ content: ESC });
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: `${OUT}/17-simples-reforma.png` });
console.log("17");

// 2. Pessoa física
await page.goto(`${BASE}/pessoa-fisica`);
await page.getByRole("heading", { name: "Pessoa física" }).first().waitFor();
await moeda("#receita_pf", 1500000);
await moeda("#despesas_pf", 100000);
await moeda("#contab_pf", 40000);
await page.getByRole("button", { name: "Comparar" }).click();
await page.getByText(/Opção mais vantajosa/).waitFor();
await quieto(); await page.waitForTimeout(800);
await page.addStyleTag({ content: ESC });
await page.evaluate(() => window.scrollTo(0, 0));
await page.screenshot({ path: `${OUT}/18-pessoa-fisica.png` });
console.log("18");

// 3. Mudanças na legislação
await page.goto(`${BASE}/avisos`);
await quieto();
const cartao = page.locator("section").filter({ has: page.getByRole("heading", { name: "Mudanças na legislação" }) }).first();
await cartao.waitFor();
await cartao.scrollIntoViewIfNeeded();
await page.addStyleTag({ content: ESC });
await page.waitForTimeout(500);
await cartao.screenshot({ path: `${OUT}/19-mudancas.png` });
console.log("19");
await b.close();
