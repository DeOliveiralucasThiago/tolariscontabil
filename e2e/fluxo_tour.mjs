// Tour de primeiro acesso e ajuda por tela: abre sozinho uma vez, guia os menus, cada tela tem "? Ajuda" e tudo funciona no celular.
// Os navegadores automatizados não abrem o tour sozinhos; aqui ele é forçado. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const forcar = () => localStorage.setItem("tolaris:tour:forcar", "1");
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
await ctx.addInitScript(forcar);
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));
const dialogo = page.getByRole("dialog");

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Guiada");
await page.fill("#nome", "Vera Contadora");
await page.fill("#email", `vera-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-tour-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// 1. O tour de primeiro acesso abre sozinho
await dialogo.getByRole("heading", { name: "Bem-vindo ao Tolaris Contábil" }).waitFor();
await dialogo.getByText("1 de 11").waitFor();
await page.screenshot({ path: `${OUT}/tour-1-boas-vindas.png` });
await page.keyboard.press("ArrowRight");
await dialogo.getByRole("heading", { name: "Painel", exact: true }).waitFor();
const menuPainel = await page.locator('[data-tour="menu-/painel"]').first().boundingBox();
const caixa = await dialogo.boundingBox();
if (!menuPainel || !caixa || caixa.x < menuPainel.x + menuPainel.width) throw new Error(`balão fora de lugar: ${JSON.stringify({ menuPainel, caixa })}`);
await page.screenshot({ path: `${OUT}/tour-2-menu.png` });
await page.keyboard.press("ArrowLeft");
await dialogo.getByRole("heading", { name: "Bem-vindo ao Tolaris Contábil" }).waitFor();
passo("tour abre sozinho no primeiro acesso, o balão fica ao lado do menu e as setas do teclado navegam");

const titulos = [];
for (let i = 0; i < 10; i++) {
  await dialogo.getByRole("button", { name: "Próximo" }).click();
  titulos.push(await dialogo.getByRole("heading").first().innerText());
}
if (titulos.join("|") !== "Painel|Prospecção|Clientes|Funil comercial|Avisos|Reforma Tributária|Pessoa física|Equipe|Configurações|Pronto para começar") throw new Error(`passos inesperados: ${titulos}`);
await page.screenshot({ path: `${OUT}/tour-3-fim.png` });
await dialogo.getByRole("button", { name: "Concluir" }).click();
await dialogo.waitFor({ state: "detached" });
await page.reload();
await page.getByRole("heading", { name: "Configurações do escritório" }).waitFor();
await page.waitForTimeout(1500);
if (await dialogo.count()) throw new Error("o tour não deveria reabrir depois de concluído");
passo("11 passos (um por menu) e, concluído, não volta a abrir");

// 2. Ajuda de cada tela
await page.getByRole("button", { name: "Ajuda" }).click();
await page.getByRole("menuitem", { name: /Ajuda desta tela/ }).click();
await dialogo.getByRole("heading", { name: "Identificação" }).waitFor();
await dialogo.getByText("1 de 6").waitFor();
await page.keyboard.press("Escape");
await dialogo.waitFor({ state: "detached" });
passo("Ajuda desta tela em Configurações (6 passos) e Esc fecha");

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cliente = await api("POST", "/clientes", { data: { razao_social: "Padaria Guiada Ltda", cnpj: "11222333000181", atividade: "comercio", regime_atual: "simples" } });

for (const [rota, primeiro, total] of [
  ["/painel", "Painel", 4], ["/prospeccao", "Dados da empresa", 3], ["/clientes", "Importar planilha", 5], ["/clientes/importar", "Planilha da carteira", 3],
  [`/clientes/${cliente.id}`, "Simulações", 5], ["/funil", "Período", 3], ["/avisos", "Avisos", 3], ["/reforma", "Duas simulações", 2],
  ["/pessoa-fisica", "Calculadoras", 1], ["/equipe", "Convidar", 2],
]) {
  await page.goto(`${BASE}${rota}`);
  await page.getByRole("button", { name: "Ajuda" }).click();
  await page.getByRole("menuitem", { name: /Ajuda desta tela/ }).click();
  await dialogo.getByRole("heading", { name: primeiro, exact: true }).waitFor();
  await dialogo.getByText(`1 de ${total}`).waitFor();
  await page.keyboard.press("Escape");
}
passo("todas as telas têm ajuda guiada, com o número certo de passos");

// 3. O balão aponta para o elemento certo (aba Movimento fiscal do cliente)
await page.goto(`${BASE}/clientes/${cliente.id}`);
await page.getByRole("button", { name: "Ajuda" }).click();
await page.getByRole("menuitem", { name: /Ajuda desta tela/ }).click();
await dialogo.getByRole("button", { name: "Próximo" }).click();
await dialogo.getByRole("button", { name: "Próximo" }).click();
await dialogo.getByRole("heading", { name: "Movimento fiscal" }).waitFor();
await page.waitForTimeout(300);
const aba = await page.getByRole("tab", { name: "Movimento fiscal" }).boundingBox();
const bal = await dialogo.boundingBox();
const centroAba = aba ? aba.y + aba.height / 2 : 0;
const aoLado = aba && bal && bal.x >= aba.x + aba.width && bal.x - (aba.x + aba.width) < 40 && bal.y <= centroAba && bal.y + bal.height >= centroAba;
const abaixo = aba && bal && bal.y >= aba.y + aba.height && bal.y - (aba.y + aba.height) < 40;
if (!aoLado && !abaixo) throw new Error(`balão longe da aba: ${JSON.stringify({ aba, bal })}`);
await page.screenshot({ path: `${OUT}/tour-4-aba.png` });
await page.keyboard.press("Escape");
passo("o balão do passo 'Movimento fiscal' fica junto da aba correspondente");

// 4. Celular: o tour abre o menu para mostrar os itens e cabe na tela
const cel = await browser.newContext({ viewport: { width: 390, height: 800 } });
await cel.addInitScript(forcar);
await cel.addCookies(await ctx.cookies());
const pc = await cel.newPage();
await pc.goto(`${BASE}/painel`);
const d = pc.getByRole("dialog");
await d.getByRole("heading", { name: "Bem-vindo ao Tolaris Contábil" }).waitFor();
await d.getByRole("button", { name: "Próximo" }).click();
await d.getByRole("heading", { name: "Painel", exact: true }).waitFor();
await pc.waitForTimeout(500);
if ((await pc.getByRole("button", { name: "Abrir menu" }).getAttribute("aria-expanded")) !== "true") throw new Error("o tour deveria abrir o menu no celular");
const b = await d.boundingBox();
if (!b || b.x < 0 || b.x + b.width > 390 || b.y < 0 || b.y + b.height > 800) throw new Error(`balão fora da tela: ${JSON.stringify(b)}`);
await pc.screenshot({ path: `${OUT}/tour-5-celular.png` });
if ((await pc.evaluate(() => document.documentElement.scrollWidth)) > 390) throw new Error("rolagem horizontal no celular");
await pc.keyboard.press("Escape");
await d.waitFor({ state: "detached" });
if ((await pc.getByRole("button", { name: "Abrir menu" }).getAttribute("aria-expanded")) !== "false") throw new Error("o menu deveria fechar ao pular o tour");
passo("no celular o tour abre o menu, o balão cabe na tela, sem rolagem horizontal, e pular fecha o menu");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
