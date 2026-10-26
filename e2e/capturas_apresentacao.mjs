// Capturas de tela para a apresentação do Tolaris: semeia um escritório fictício (Contabilidade Horizonte) e fotografa as telas.
// Tudo é inventado (o kit de teste vem de kit-de-teste/). Precisa da API com TOLARIS_PTAX_URL e TOLARIS_BRASILAPI_URL apontando
// para o mock_brasilapi.py, e do site SEM a variável TOLARIS_AMBIENTE_TESTE (para a barra de testes não aparecer nas imagens).
//   node capturas_apresentacao.mjs <pasta de saída>
import fs from "fs";
import path from "path";
import { execFileSync } from "child_process";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida/apresentacao";
const KIT = path.resolve(process.env.KIT ?? "../kit-de-teste");
fs.mkdirSync(OUT, { recursive: true });

const falhas = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, locale: "pt-BR" });
const page = await ctx.newPage();
const erros = [];
page.on("pageerror", (e) => erros.push(String(e)));

const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const ESCONDE_AJUDA = "div.fixed.bottom-4.right-4 { display: none !important; }";
const quieto = () => page.waitForLoadState("networkidle").catch(() => undefined);
async function foto(nome, alvo = null, { pausa = 400 } = {}) {
  await page.waitForTimeout(pausa);
  const arq = path.join(OUT, `${nome}.png`);
  await page.addStyleTag({ content: ESCONDE_AJUDA }).catch(() => undefined);
  if (alvo) await alvo.screenshot({ path: arq });
  else await page.screenshot({ path: arq });
  console.log("📷", nome);
}
async function tenta(nome, fn) {
  try { await fn(); } catch (e) { falhas.push(nome); console.log("✗", nome, String(e).split("\n")[0]); }
}
const cnpjs = { estrela: "12345678000195", maple: "11444777000161", padaria: "45997418000153", clinica: "04252011000110", oficina: "11222333000181", beto: "00000000000191" };

// --- 0. Tela de entrada (antes de cadastrar)
await page.goto(`${BASE}/login`);
await page.getByRole("img", { name: /Tolaris/ }).waitFor();
await quieto();
await foto("01-login");

// --- 1. Escritório fictício
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Horizonte");
await page.fill("#nome", "Lia Contadora");
await page.fill("#email", "lia@horizonte.example");
await page.fill("#senha", "senha-horizonte-2026");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
await api("PATCH", "/escritorio", { data: {
  nome: "Contabilidade Horizonte", cnpj: "11222333000181", crc: "SP-123456/O-7", email: "contato@horizonte.example", telefone: "(11) 3000-1234",
  honorarios: { base: { mei: 180, simples: 650, presumido: 1200, real: 2400 }, por_funcionario: 60, adesao: 300, servicos: "Escrituração contábil e fiscal, obrigações acessórias, planejamento tributário.", validade_dias: 15 },
} });
await api("PUT", "/escritorio/logo", { multipart: { arquivo: { name: "logo.png", mimeType: "image/png", buffer: fs.readFileSync(path.resolve("../web/public/icone-tolaris.png")) } } });

// --- 2. Clientes e dados
const cli = async (razao, cnpj, atividade, regime, extra = {}) =>
  (await api("POST", "/clientes", { data: { razao_social: razao, cnpj, atividade, regime_atual: regime, status: "ativo", email: `contato@${cnpj}.example`, municipio: "SÃO PAULO", uf: "SP", ...extra } })).id;
const completa = (cid, dados) => api("POST", `/clientes/${cid}/simulacoes/completa`, { data: dados });
const honorarios = (sid, valor, adesao = 0) => api("PUT", `/simulacoes/${sid}/honorarios`, { data: { valor_mensal: valor, adesao } });
const publicar = (sid) => api("PATCH", `/simulacoes/${sid}/publicacao`, { data: { publicada: true } });

// Mercadinho Estrela: kit (12 meses de notas, SPED e planilha contábil)
const estrela = await cli("Mercadinho Estrela Ltda", cnpjs.estrela, "comercio", "simples", { nome_fantasia: "Mercadinho Estrela" });
const arq = (nome) => ({ name: nome, mimeType: "application/octet-stream", buffer: fs.readFileSync(path.join(KIT, nome)) });
await api("POST", `/clientes/${estrela}/importacoes`, { multipart: { arquivos: arq("3-notas-xml.zip") } });
await api("POST", `/clientes/${estrela}/importacoes`, { multipart: { arquivos: arq("4-sped-fiscal-2026-09.txt") } });
const previa = await api("POST", `/clientes/${estrela}/financeiro/previa`, { multipart: { arquivos: arq("2-dados-contabeis-12-meses.xlsx") } });
await api("POST", `/clientes/${estrela}/financeiro/importar`, { multipart: { arquivos: arq("2-dados-contabeis-12-meses.xlsx"), mapeamento: JSON.stringify(previa.sugestao) } });
const planoEstrela = await completa(estrela, { atividade: "comercio", receita_bruta_anual: 820000, folha_clt_anual: 174000, pro_labore_anual: 54000, compras_anual: 475000, despesas_creditaveis_anual: 28000, outras_despesas_anual: 70000 });
await honorarios(planoEstrela.id, 900, 300);
await api("POST", `/clientes/${estrela}/recuperacao`, { data: {} }).catch(() => undefined);

// Consultoria Maple: serviços exportados (CAD)
const maple = await cli("Consultoria Maple Ltda", cnpjs.maple, "servico_fator_r", "presumido");
// Propostas em etapas diferentes (para o funil)
const padaria = await cli("Padaria Pão Bom Ltda", cnpjs.padaria, "comercio", "simples");
const clinica = await cli("Clínica Sorriso Ltda", cnpjs.clinica, "servico_fator_r", "simples");
const oficina = await cli("Oficina Boa Roda Ltda", cnpjs.oficina, "servico_anexo_iii", "simples");
const base = { atividade: "comercio", receita_bruta_anual: 1200000, folha_clt_anual: 120000, pro_labore_anual: 36000, compras_anual: 720000, despesas_creditaveis_anual: 60000 };
const sPad = await completa(padaria, base); await honorarios(sPad.id, 750);
const sCli = await completa(clinica, { atividade: "servico_fator_r", receita_bruta_anual: 900000, folha_clt_anual: 150000, pro_labore_anual: 60000 }); await honorarios(sCli.id, 1100, 300); await publicar(sCli.id);
const sOfi = await completa(oficina, { atividade: "servico_anexo_iii", receita_bruta_anual: 480000, folha_clt_anual: 72000, pro_labore_anual: 36000 }); await honorarios(sOfi.id, 800); await publicar(sOfi.id);
const tokenOfi = (await api("POST", `/clientes/${oficina}/portal`, { data: {} })).link.split("/").pop();
await page.request.post(`${BASE}/api/portal/${tokenOfi}/simulacoes/${sOfi.id}/visto`);
await publicar(planoEstrela.id);
const tokenEstrela = (await api("POST", `/clientes/${estrela}/portal`, { data: {} })).link.split("/").pop();
await page.request.post(`${BASE}/api/portal/${tokenEstrela}/simulacoes/${planoEstrela.id}/visto`);
await page.request.post(`${BASE}/api/portal/${tokenEstrela}/simulacoes/${planoEstrela.id}/aceite`, { data: { nome: "Dona Estrela", confirmo: true } });
// Avisos: MEI perto do limite e fator R baixo
const beto = await cli("Beto Instalações MEI", cnpjs.beto, "servico_anexo_iii", "mei");
await completa(beto, { atividade: "servico_anexo_iii", receita_bruta_anual: 79500 });
const alfa = await cli("Alfa Tecnologia Ltda", "45997418000153".replace("45997418000153", "34028316000103"), "servico_fator_r", "simples");
await completa(alfa, { atividade: "servico_fator_r", receita_bruta_anual: 600000, folha_clt_anual: 72000, pro_labore_anual: 60000 });

// --- 3. Capturas
await tenta("02-painel", async () => { await page.goto(`${BASE}/painel`); await quieto(); await foto("02-painel"); });

await tenta("03-prospeccao", async () => {
  await page.goto(`${BASE}/prospeccao`);
  await page.fill("#cnpj", "11.222.333/0001-81");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByText(/TECH SOLUCOES/).first().waitFor();
  await page.fill("#faturamento", "4500000");
  await page.fill("#folha", "800000");
  await page.fill("#prolabore", "600000");
  await page.click("text=Calcular previsão");
  await page.getByText("Regime recomendado").waitFor();
  await quieto();
  await page.evaluate(() => window.scrollTo(0, 0));
  await foto("03-prospeccao");
  await page.evaluate(() => window.scrollTo(0, 620));
  await foto("03b-comparativo");
  await page.getByText("Memória de cálculo").first().scrollIntoViewIfNeeded().catch(() => undefined);
});

await tenta("04-exterior", async () => {
  await page.goto(`${BASE}/clientes/${maple}?aba=planejamento`);
  await page.fill("#receita", "60000000");
  await page.fill("#prolabore_anual", "24000000");
  await page.fill("#outras", "6000000");
  const bloco = page.getByTestId("bloco-exterior");
  await bloco.locator("summary").click();
  await page.selectOption("#moeda_origem", "CAD");
  await page.fill("#valor_moeda", "15000000");
  await page.fill("#data_cambio", "2026-10-15");
  await page.click("text=Buscar PTAX");
  await page.getByText(/PTAX de compra/).waitFor();
  await page.click("text=Usar como receita do exterior");
  await page.fill("#receita_exterior", "60000000");
  await page.fill("#variacao_cambial", "4000000");
  await bloco.scrollIntoViewIfNeeded();
  await foto("04-exterior-form", bloco);
  await page.click("text=Calcular e salvar planejamento");
  await page.getByTestId("nota-exterior").waitFor();
  await quieto();
  await page.getByText("Regime recomendado").first().scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollBy(0, -60));
  await foto("04b-exterior-resultado");
});

await tenta("05-simulacoes", async () => { await page.goto(`${BASE}/clientes/${estrela}?aba=simulacoes`); await quieto(); await foto("05-simulacoes-do-cliente"); });

await tenta("06-proposta-pdf", async () => {
  const r = await page.request.get(`${BASE}/api/simulacoes/${planoEstrela.id}/proposta.pdf`);
  const pdf = path.join(OUT, "proposta.pdf");
  fs.writeFileSync(pdf, await r.body());
  execFileSync("pdftoppm", ["-r", "110", "-png", pdf, path.join(OUT, "06-proposta")]);
  console.log("📷 06-proposta (páginas do PDF)");
});

await tenta("07-portal", async () => { await page.goto(`${BASE}/portal/${tokenEstrela}`); await quieto(); await page.waitForTimeout(800); await foto("07-portal-do-cliente"); });

// Foto de uma faixa da página a partir de um elemento (rola a página inteira, sem depender da posição da rolagem)
async function faixa(nome, localizador, { altura = 860, acima = 24 } = {}) {
  const caixa = await localizador.first().boundingBox();
  const topo = await page.evaluate(() => window.scrollY);
  const y = Math.max(0, caixa.y + topo - acima);
  await page.addStyleTag({ content: ESCONDE_AJUDA }).catch(() => undefined);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(OUT, `${nome}.png`), fullPage: true, clip: { x: 0, y, width: 1440, height: altura } });
  console.log("📷", nome);
}

await tenta("08-recuperacao", async () => {
  await page.goto(`${BASE}/clientes/${estrela}?aba=movimento`);
  await page.getByText("Imposto pago a mais no Simples Nacional").first().waitFor();
  await quieto();
  await faixa("08-recuperacao", page.getByRole("heading", { name: "Imposto pago a mais no Simples Nacional" }));
  await faixa("08b-recuperacao-por-mes", page.getByRole("heading", { name: "Pago a mais por mês (R$)" }), { acima: 10 });
});

await tenta("09-notas", async () => {
  await page.goto(`${BASE}/clientes/${estrela}?aba=movimento`);
  await quieto();
  await foto("09-movimento-fiscal");
});

await tenta("10-acompanhamento", async () => { await page.goto(`${BASE}/clientes/${estrela}?aba=acompanhamento`); await quieto(); await page.waitForTimeout(800); await foto("10-acompanhamento"); });
await tenta("11-avisos", async () => { await page.goto(`${BASE}/avisos`); await quieto(); await foto("11-avisos"); });
await tenta("12-funil", async () => { await page.goto(`${BASE}/funil`); await quieto(); await page.waitForTimeout(600); await foto("12-funil"); });

await tenta("13-seguranca", async () => {
  await page.goto(`${BASE}/configuracoes`);
  await quieto();
  const cartao = page.locator("section").filter({ has: page.getByRole("heading", { name: "Registro de atividades" }) }).first();
  await cartao.scrollIntoViewIfNeeded();
  await foto("13-registro-de-atividades", cartao);
  const duas = page.locator("section").filter({ has: page.getByRole("heading", { name: "Verificação em duas etapas" }) }).first();
  await duas.scrollIntoViewIfNeeded();
  await foto("13b-duas-etapas", duas);
});

await tenta("14-reforma", async () => {
  await page.goto(`${BASE}/reforma`);
  await quieto();
  await page.fill("#receita_ref", "300000000");
  await page.getByRole("button", { name: "Simular transição" }).click();
  await page.getByText(/2033/).first().waitFor();
  await quieto();
  await page.waitForTimeout(800);
  await foto("14-reforma");
  await page.evaluate(() => window.scrollTo(0, 560));
  await foto("14b-reforma-resultado");
});

await tenta("16-enquadramento", async () => {
  // Empresa de serviços no Anexo V (fator R de 6%): CNPJ traz os CNAEs e a análise compara os caminhos até o Anexo III
  await page.goto(`${BASE}/enquadramento`);
  await page.getByRole("heading", { name: "Enquadramento" }).waitFor();
  await page.fill("#enq_cnpj", "11222333000181");
  await page.getByRole("button", { name: "Buscar" }).click();
  await page.getByTestId("cnaes-do-cliente").waitFor();
  await page.fill("#receita", "60000000");
  await page.fill("#prolabore_anual", "3600000");
  await page.fill("#outras", "6000000");
  await page.fill("#percentual_iii", "30");
  await page.getByRole("button", { name: "Analisar enquadramento" }).click();
  const res = page.getByTestId("resultado-enquadramento");
  await res.waitFor();
  await quieto();
  await page.waitForTimeout(600);
  await faixa("16-enquadramento", res, { altura: 835, acima: 12 });
});

await tenta("15-tour", async () => {
  const p2 = await ctx.newPage();
  await p2.addInitScript(() => localStorage.setItem("tolaris:tour:forcar", "1"));
  await p2.goto(`${BASE}/painel`);
  await p2.getByRole("dialog").first().waitFor({ timeout: 15000 }).catch(() => undefined);
  await p2.waitForTimeout(1200);
  await p2.screenshot({ path: path.join(OUT, "15-tour.png") });
  console.log("📷 15-tour");
  await p2.close();
});

fs.writeFileSync(path.join(OUT, "ids.json"), JSON.stringify({ estrela, maple, planoEstrela: planoEstrela.id, tokenEstrela }, null, 2));
if (erros.length) console.log("erros de página:", erros.slice(0, 3));
console.log(falhas.length ? `Falharam: ${falhas.join(", ")}` : "Capturas concluídas.");
await browser.close();
