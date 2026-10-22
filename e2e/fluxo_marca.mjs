// Marca e ambiente de testes: logo no lado esquerdo do login (no lugar do texto), ícone da aba e barra "Ambiente de testes".
// Precisa do site iniciado com TOLARIS_AMBIENTE_TESTE=true. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 860 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

// 1. Login: logo à esquerda, sem o texto antigo, e barra no topo
await page.goto(`${BASE}/login`);
const logo = page.getByRole("img", { name: "Tolaris — Tecnologia Integrada" });
await logo.waitFor();
const caixa = await logo.boundingBox();
if (!caixa || caixa.x > 80 || caixa.y > 120 || caixa.width < 80) throw new Error("logo fora do canto esquerdo: " + JSON.stringify(caixa));
if (await page.getByText("Tolaris Contábil", { exact: true }).count()) throw new Error("o texto “Tolaris Contábil” ainda aparece no login");
const ok = await logo.evaluate((img) => img.complete && img.naturalWidth > 0);
if (!ok) throw new Error("a imagem da logo não carregou");
const faixa = page.getByRole("note").filter({ hasText: "Ambiente de testes" });
await faixa.waitFor();
const f = await faixa.boundingBox();
if (!f || f.y !== 0 || f.width < 1300) throw new Error("a barra não está no topo, de ponta a ponta: " + JSON.stringify(f));
const cor = await faixa.evaluate((e) => getComputedStyle(e).backgroundColor);
if (cor !== "rgb(31, 58, 95)") throw new Error("a barra devia ser o azul do Tolaris, veio " + cor);
if (!(await faixa.innerText()).includes("dados fictícios")) throw new Error("texto da barra incompleto");
const altura = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
if (altura > 1) throw new Error(`o login ganhou rolagem vertical de ${altura}px por causa da barra`);
await page.screenshot({ path: `${OUT}/marca_1_login.png` });
passo("login: logo no canto esquerdo no lugar do texto, barra azul de ambiente de testes e sem rolagem extra");

// 2. Ícone da aba
const icones = await page.locator('link[rel~="icon"]').evaluateAll((els) => els.map((e) => e.getAttribute("href")));
if (!icones.length) throw new Error("sem ícone na aba");
for (const href of icones) {
  const r = await page.request.get(new URL(href, BASE).toString());
  if (!r.ok() || !/image/.test(r.headers()["content-type"] ?? "")) throw new Error(`ícone ${href} não carregou (${r.status()})`);
}
passo(`ícone da aba servido (${icones.join(", ")})`);

// 3. Dentro do sistema: a barra aparece, o menu lateral continua inteiro (inclusive o "Sair")
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Marca");
await page.fill("#nome", "Rui Contador");
await page.fill("#email", `rui-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-marca-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
await faixa.waitFor();
const sair = page.getByRole("button", { name: "Sair" }).first();
await sair.waitFor();
const s = await sair.boundingBox();
if (!s || s.y + s.height > 860) throw new Error("o botão Sair ficou fora da tela com a barra: " + JSON.stringify(s));
const rolagem = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight);
await page.screenshot({ path: `${OUT}/marca_2_sistema.png` });
passo(`sistema: barra no topo e menu lateral inteiro (sobra de rolagem: ${rolagem}px)`);

// 4. Celular: barra curta, cabe na largura, sem rolagem horizontal
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${BASE}/login`);
await faixa.waitFor();
const h = await faixa.boundingBox();
if (!h || h.height > 40) throw new Error("a barra ficou alta no celular: " + JSON.stringify(h));
const larg = await page.evaluate(() => document.documentElement.scrollWidth);
if (larg > 392) throw new Error(`rolagem horizontal no celular: ${larg}px`);
await page.screenshot({ path: `${OUT}/marca_3_celular.png` });
passo("celular: barra curta e sem rolagem horizontal");

if (erros.length) throw new Error("erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo da marca concluído.");
