// Avisos da carteira no navegador: fator R, limite do MEI, painel, filtros, mudanças na legislação e recálculo.
// Para o passo "simulação desatualizada" é preciso alterar o resultado salvo no banco: defina E2E_DB com o caminho do
// SQLite da API (ex.: E2E_DB=./e2e.db). Sem ele, esse passo é pulado.
import { execFileSync } from "child_process";
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
const DB = process.env.E2E_DB;
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);

const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Avisos");
await page.fill("#nome", "Alice Contadora");
await page.fill("#email", `alice-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-avisos-123");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// Carteira de exemplo criada pela API (a sessão do navegador vale para as chamadas)
const api = async (metodo, caminho, corpo) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, data: corpo });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.json();
};
const consultoria = await api("POST", "/clientes", { razao_social: "Consultoria Alfa Ltda", cnpj: "11222333000181", atividade: "servico_fator_r", regime_atual: "simples", status: "ativo" });
await api("POST", `/clientes/${consultoria.id}/simulacoes/completa`, { atividade: "servico_fator_r", receita_bruta_anual: 600000, folha_clt_anual: 96000, pro_labore_anual: 60000 });
const mei = await api("POST", "/clientes", { razao_social: "Beto Instalações MEI", cnpj: "45997418000153", atividade: "servico_anexo_iii", regime_atual: "mei", status: "ativo" });
await api("POST", `/clientes/${mei.id}/simulacoes/completa`, { atividade: "servico_anexo_iii", receita_bruta_anual: 85000 });
const comercio = await api("POST", "/clientes", { razao_social: "Mercadinho Bom Preço", cnpj: "11444777000161", atividade: "comercio", regime_atual: "simples", status: "ativo" });
const simComercio = await api("POST", `/clientes/${comercio.id}/simulacoes/completa`, {
  atividade: "comercio", receita_bruta_anual: 1500000, folha_clt_anual: 120000, pro_labore_anual: 36000, compras_anual: 900000, despesas_creditaveis_anual: 60000 });

// 1. Painel: cartão com o resumo e link para a central
await page.goto(`${BASE}/painel`);
await page.getByText("1 crítico · 0 em atenção · 1 oportunidade").waitFor();
await page.getByText("R$ 43.264,80 a ganhar").waitFor();
await page.getByRole("link", { name: "Ver todos" }).click();
await page.waitForURL("**/avisos");
passo("painel mostra o resumo e leva à central de avisos");

// 2. Central: avisos, ordem e valores
await page.getByRole("heading", { name: "Avisos" }).waitFor();
await page.getByText("3 clientes analisados").waitFor();
await page.getByText("Fator R de 27,28%: o cliente paga pelo Anexo V").waitFor();
await page.getByText("Receita de R$ 85.000,00 acima do limite do MEI (R$ 81.000,00)").waitFor();
await page.getByText("Ganho líquido estimado: R$ 43.264,80 por ano").waitFor();
const ordem = await page.locator("ul > li h3").allInnerTexts();
if (!ordem[0].includes("MEI")) throw new Error(`o crítico deveria vir primeiro: ${ordem.join(" | ")}`);
await page.screenshot({ path: `${OUT}/av-1-central.png`, fullPage: true });
passo("fator R (R$ 43.264,80 a ganhar) e MEI acima do limite, o crítico primeiro");

// 3. Filtros
await page.getByRole("tab", { name: /Críticos \(1\)/ }).click();
await page.getByText("Fator R de 27,28%").waitFor({ state: "detached" });
await page.getByRole("tab", { name: /Oportunidades \(1\)/ }).click();
await page.getByText("Fator R de 27,28%: o cliente paga pelo Anexo V").waitFor();
await page.getByRole("tab", { name: /Todos/ }).click();
passo("filtros por gravidade");

// 4. Mudanças na legislação
await page.getByText("Futura · 01/01/2027").first().waitFor();
await page.getByText("Reforma Tributária: CBS substitui PIS/Cofins e o IPI é zerado").click();
await page.getByText("Base legal: EC 132/2023; LC 214/2025").first().waitFor();
await page.getByText("Em vigor · 01/01/2026").first().waitFor();
passo("mudanças na legislação: futuras primeiro, com base legal");

// 5. Simulação desatualizada por mudança de regra
if (DB) {
  execFileSync("python3", ["-c", `
import json, sqlite3, sys
con = sqlite3.connect(sys.argv[1])
linha = con.execute("select id, resultado from simulacoes where id = ?", (int(sys.argv[2]),)).fetchone()
r = json.loads(linha[1])
r["regimes"][0]["total"] -= 5000   # como se o resultado tivesse sido calculado com uma regra antiga
con.execute("update simulacoes set resultado = ? where id = ?", (json.dumps(r), linha[0]))
con.commit()
`, DB, String(simComercio.id)]);
  await page.reload();
  await page.getByText("o resultado mudou com as regras atuais").waitFor();
  await page.getByText(/Mudaram os totais — Simples Nacional: de R\$ .* para R\$ .*A recomendação continua a mesma/).waitFor();
  await page.screenshot({ path: `${OUT}/av-2-desatualizada.png`, fullPage: true });
  await page.getByRole("button", { name: "Recalcular" }).click();
  await page.getByText("Simulação de Mercadinho Bom Preço recalculada com as regras atuais.").waitFor();
  await page.getByText("o resultado mudou com as regras atuais").waitFor({ state: "detached" });
  passo("simulação desatualizada é apontada, recalculada com um clique e o aviso some");

  await page.getByRole("link", { name: "Ver no cliente" }).click();
  await page.waitForURL(/\/clientes\/\d+$/);
  await page.getByText(/Simulações \(2\)/).waitFor();
  await page.getByRole("button", { name: "Ver" }).first().click();
  await page.getByText("Recalculada com as regras atuais em").waitFor();
  await page.screenshot({ path: `${OUT}/av-3-cliente.png`, fullPage: true });
  passo("a nova simulação mostra o antes e o depois e a anterior fica no histórico");
} else {
  console.log("- passo da simulação desatualizada pulado (defina E2E_DB)");
}

// 6. Atalho do aviso para a aba certa do cliente
await page.goto(`${BASE}/avisos`);
await page.getByRole("link", { name: "Abrir cliente" }).first().click();
await page.waitForURL(/\/clientes\/\d+\?aba=simulacoes$/);
passo("o botão do aviso abre o cliente na aba indicada");

// 7. Celular
const celular = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await celular.context().addCookies(await ctx.cookies());
await celular.goto(`${BASE}/avisos`);
await celular.getByText("Fator R de 27,28%: o cliente paga pelo Anexo V").waitFor();
const largura = await celular.evaluate(() => document.documentElement.scrollWidth);
await celular.screenshot({ path: `${OUT}/av-4-celular.png`, fullPage: true });
if (largura > 390) throw new Error(`rolagem horizontal no celular: ${largura}px`);
passo("celular sem rolagem horizontal");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
