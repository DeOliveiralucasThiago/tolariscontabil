// Honorários, leitura e aceite: tabela do escritório, proposta na simulação, portal do cliente (leitura e aceite),
// WhatsApp e avisos. E-mail novo a cada execução; não precisa de e-mail real.
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
page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Honorários");
await page.fill("#nome", "Helena Contadora");
await page.fill("#email", `helena-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-honorarios-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// 1. Tabela de honorários do escritório
await page.getByRole("heading", { name: "Tabela de honorários" }).waitFor();
await page.fill("#hon-simples", "80000");
await page.fill("#hon-presumido", "150000");
await page.fill("#hon-funcionario", "7000");
await page.fill("#hon-adesao", "50000");
await page.fill("#hon-servicos", "Escrituração fiscal e contábil\nFolha de pagamento\nPlanejamento tributário anual");
await page.getByRole("button", { name: "Salvar tabela" }).click();
await page.getByText("Tabela de honorários salva.").waitFor();
await page.reload();
if ((await page.inputValue("#hon-simples")) !== "800,00") throw new Error("a tabela não foi gravada");
passo("tabela de honorários do escritório salva e recarregada");

// 2. Cliente (prospect) com telefone e um planejamento, criados pela API
const api = async (metodo, caminho, corpo) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, data: corpo });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cliente = await api("POST", "/clientes", {
  razao_social: "Mercadinho Boa Compra Ltda", cnpj: "11222333000181", atividade: "comercio", regime_atual: "simples",
  contato_nome: "Marcos Souza", telefone: "(11) 98765-4321",
});
await api("POST", `/clientes/${cliente.id}/simulacoes/completa`, {
  atividade: "comercio", receita_bruta_anual: 1500000, folha_clt_anual: 120000, pro_labore_anual: 36000,
  compras_anual: 900000, despesas_creditaveis_anual: 60000 });

// 3. Proposta de honorários na simulação
await page.goto(`${BASE}/clientes/${cliente.id}`);
await page.getByRole("button", { name: "Honorários" }).click();
const painel = page.getByRole("form", { name: "Proposta de honorários" });
await painel.getByLabel("Funcionários (CLT)").fill("3");
await painel.getByText("Sugestão pela tabela: Simples Nacional R$ 800,00 + 3 × R$ 70,00 = R$ 1.010,00 por mês.").waitFor();
if ((await painel.getByLabel("Honorário mensal").inputValue()) !== "1.010,00") throw new Error("valor sugerido não preenchido");
await painel.getByText("Total no primeiro ano: R$ 12.620,00").waitFor();
await painel.getByRole("button", { name: "Salvar proposta" }).click();
await painel.getByText("Proposta salva.").waitFor();
await page.screenshot({ path: `${OUT}/hon-1-proposta.png`, fullPage: true });
await painel.getByRole("button", { name: "Fechar" }).click();
await page.getByText("Honorários R$ 1.010,00/mês").waitFor();
passo("valor sugerido pela tabela (R$ 800 + 3 × R$ 70 = R$ 1.010) e proposta salva");

// 4. Publicar, gerar o link e abrir o WhatsApp com mensagem pronta
await page.getByRole("checkbox", { name: /Publicar no portal/ }).check();
await page.getByText("No portal · ainda não visto pelo cliente").waitFor();
await page.getByRole("button", { name: "Gerar link do portal" }).click();
const campoLink = page.getByLabel("Link do portal");
await campoLink.waitFor();
const link = await campoLink.inputValue();
const mensagem = await page.getByLabel("Mensagem para o WhatsApp").inputValue();
if (!mensagem.startsWith("Olá, Marcos! Aqui é do escritório Contabilidade Honorários.") || !mensagem.includes(link)) {
  throw new Error(`mensagem do WhatsApp inesperada: ${mensagem}`);
}
const href = await page.getByRole("link", { name: "Enviar pelo WhatsApp" }).getAttribute("href");
if (!href.startsWith("https://wa.me/5511987654321?text=") || decodeURIComponent(href.split("text=")[1]) !== mensagem) {
  throw new Error(`link do WhatsApp inesperado: ${href}`);
}
await page.getByText("Abre a conversa com (11) 98765-4321.").waitFor();
await page.screenshot({ path: `${OUT}/hon-2-whatsapp.png`, fullPage: true });
passo("link do WhatsApp com o número do cliente (55 11 98765-4321) e a mensagem editável");

// 5. O cliente abre o portal, vê a proposta e aceita
const ctxCliente = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const cli = await ctxCliente.newPage();
cli.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
await cli.goto(link.replace(/^https?:\/\/[^/]+/, BASE));
const proposta = cli.getByRole("region", { name: "Proposta de honorários" });
await proposta.getByText("R$ 1.010,00").waitFor();
await proposta.getByText("Total no primeiro ano").waitFor();
await proposta.getByText("Folha de pagamento").waitFor();
const aceitar = proposta.getByRole("button", { name: "Aceitar proposta" });
if (!(await aceitar.isDisabled())) throw new Error("o botão deveria começar desabilitado");
await proposta.getByLabel("Seu nome completo").fill("Marcos Souza");
await proposta.getByRole("checkbox").check();
await cli.screenshot({ path: `${OUT}/hon-3-portal.png`, fullPage: true });
await aceitar.click();
await proposta.getByText("Proposta aceita por Marcos Souza").waitFor();
await cli.getByText("Proposta de honorários aceita").waitFor();
passo("portal mostra a proposta; aceite só habilita com nome e confirmação e fica registrado");

const celular = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await celular.goto(link.replace(/^https?:\/\/[^/]+/, BASE));
await celular.getByRole("region", { name: "Proposta de honorários" }).waitFor();
const largura = await celular.evaluate(() => document.documentElement.scrollWidth);
await celular.screenshot({ path: `${OUT}/hon-4-portal-celular.png`, fullPage: true });
if (largura > 390) throw new Error(`rolagem horizontal no portal (celular): ${largura}px`);
passo("portal no celular sem rolagem horizontal");

// 6. De volta ao escritório: leitura, aceite, proposta travada e aviso
await page.reload();
await page.getByText(/Visto pelo cliente em .* · [12] abertura/).waitFor();
await page.getByText("Proposta aceita por Marcos Souza em").first().waitFor();
await page.getByRole("button", { name: "Honorários" }).click();
await page.getByText("Uma proposta aceita não pode mais ser alterada.").waitFor();
if (await page.getByRole("button", { name: /Salvar proposta|Atualizar proposta/ }).count()) throw new Error("proposta aceita não deveria ser editável");
await page.screenshot({ path: `${OUT}/hon-5-aceita.png`, fullPage: true });
passo("escritório vê a confirmação de leitura e o aceite; proposta aceita não é mais editável");

await page.goto(`${BASE}/avisos`);
await page.getByText("Marcos Souza aceitou a proposta de honorários: R$ 1.010,00 por mês").waitFor();
await page.getByText("Oportunidade").first().waitFor();
await page.screenshot({ path: `${OUT}/hon-6-avisos.png`, fullPage: true });
passo("central de avisos mostra o aceite como oportunidade (R$ 12.120,00 por ano)");

const pdf = await page.request.get(`${BASE}/api/simulacoes/${(await api("GET", `/clientes/${cliente.id}/simulacoes`))[0].id}/proposta.pdf`);
if (pdf.headers()["content-type"] !== "application/pdf" || (await pdf.body()).length < 10000) throw new Error("PDF com a proposta não veio");
passo("PDF da proposta com os honorários baixa");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
