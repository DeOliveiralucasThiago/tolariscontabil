// Funil comercial: quatro propostas em etapas diferentes (criada, enviada, vista, aceita), o funil, os valores e as ações.
// Cria tudo pela API; o aceite usa o portal do cliente, como no uso real. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Funil");
await page.fill("#nome", "Teo Contador");
await page.fill("#email", `teo-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-funil-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const CNPJS = ["11222333000181", "11444777000161", "45997418000153", "04252011000110"];
async function proposta(i, nome, mensal, adesao = 0) {
  const c = await api("POST", "/clientes", { data: { razao_social: nome, cnpj: CNPJS[i], atividade: "comercio", email: `c${i}@exemplo.com.br` } });
  const s = await api("POST", `/clientes/${c.id}/simulacoes/completa`, {
    data: { atividade: "comercio", receita_bruta_anual: 1200000, folha_clt_anual: 120000, pro_labore_anual: 36000, compras_anual: 720000, despesas_creditaveis_anual: 60000 },
  });
  await api("PUT", `/simulacoes/${s.id}/honorarios`, { data: { valor_mensal: mensal, adesao } });
  return { cid: c.id, sid: s.id };
}
const a = await proposta(0, "Padaria Criada Ltda", 500);
const b = await proposta(1, "Oficina Enviada Ltda", 800);
await api("PATCH", `/simulacoes/${b.sid}/publicacao`, { data: { publicada: true } });
const c = await proposta(2, "Mercado Visto Ltda", 1000);
await api("PATCH", `/simulacoes/${c.sid}/publicacao`, { data: { publicada: true } });
const tokenC = (await api("POST", `/clientes/${c.cid}/portal`, { data: {} })).link.split("/").pop();
await page.request.post(`${BASE}/api/portal/${tokenC}/simulacoes/${c.sid}/visto`);
const d = await proposta(3, "Clínica Aceita Ltda", 1500, 300);
await api("PATCH", `/simulacoes/${d.sid}/publicacao`, { data: { publicada: true } });
const tokenD = (await api("POST", `/clientes/${d.cid}/portal`, { data: {} })).link.split("/").pop();
await page.request.post(`${BASE}/api/portal/${tokenD}/simulacoes/${d.sid}/visto`);
const aceite = await page.request.post(`${BASE}/api/portal/${tokenD}/simulacoes/${d.sid}/aceite`, { data: { nome: "Dra. Helena", confirmo: true } });
if (!aceite.ok()) throw new Error("aceite falhou");

// 1. O funil
await page.goto(`${BASE}/funil`);
await page.getByRole("heading", { name: "Funil comercial" }).waitFor();
const funil = page.getByRole("list", { name: "Funil de propostas" });
await funil.waitFor();
const quantidades = await funil.getByRole("img").evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
const esperado = ["Propostas criadas: 4", "Enviadas ao cliente: 3", "Abertas pelo cliente: 2", "Aceitas: 1"];
if (JSON.stringify(quantidades) !== JSON.stringify(esperado)) throw new Error(`funil inesperado: ${quantidades}`);
await page.getByText("75% da etapa anterior").waitFor();
await page.getByText("50% da etapa anterior").waitFor();
await page.screenshot({ path: `${OUT}/funil-1.png`, fullPage: true });
passo("funil com 4 criadas, 3 enviadas, 2 abertas e 1 aceita, com a conversão de cada etapa");

// 2. Valores
await page.getByText(/R\$\s1\.500,00/).first().waitFor();
await page.getByText(/R\$\s18\.300,00 no primeiro ano, com adesão/).waitFor();
await page.getByText(/R\$\s2\.300,00/).first().waitFor();
await page.getByText("33%").first().waitFor();
passo("aceitos R$ 1.500/mês (R$ 18.300 no 1º ano com adesão), em aberto R$ 2.300/mês e taxa de aceite de 33%");

// 3. Lista, filtros e ações
const linhas = page.locator("tbody tr");
if ((await linhas.count()) !== 4) throw new Error("esperava 4 propostas na lista");
const ordem = await linhas.locator("td:first-child a").allInnerTexts();
if (ordem[0] !== "Mercado Visto Ltda" || ordem[3] !== "Clínica Aceita Ltda") throw new Error(`ordem inesperada: ${ordem}`);
await page.getByRole("tab", { name: /Precisam de ação/ }).click();
await page.getByText(/Publique no portal ou envie por e-mail/).waitFor();
await page.getByRole("tab", { name: "Aceitas" }).click();
await page.getByText(/Aceita em .*Formalize o contrato/).waitFor();
if ((await page.locator("tbody tr").count()) !== 1) throw new Error("filtro Aceitas deveria ter 1 proposta");
await page.screenshot({ path: `${OUT}/funil-2-aceitas.png`, fullPage: true });
await page.getByRole("link", { name: "Clínica Aceita Ltda" }).click();
await page.waitForURL(/\/clientes\/\d+/);
passo("lista ordenada por urgência, filtros por situação, ação sugerida e link para o cliente");

// 4. Período e celular
await page.goto(`${BASE}/funil`);
await page.getByLabel("Período").selectOption("30");
await page.getByRole("list", { name: "Funil de propostas" }).waitFor();
const cel = await browser.newContext({ viewport: { width: 390, height: 800 } });
const pc = await cel.newPage();
await pc.context().addCookies(await ctx.cookies());
await pc.goto(`${BASE}/funil`);
await pc.getByRole("list", { name: "Funil de propostas" }).waitFor();
await pc.screenshot({ path: `${OUT}/funil-3-celular.png`, fullPage: true });
if ((await pc.evaluate(() => document.documentElement.scrollWidth)) > 390) throw new Error("rolagem horizontal no celular");
passo("filtro de período e página no celular sem rolagem horizontal");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
