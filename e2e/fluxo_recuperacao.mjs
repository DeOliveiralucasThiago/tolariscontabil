// Recuperação de tributos no navegador: importa NF-e com itens, vê o imposto pago a mais (monofásico e ST),
// gera o relatório, abre o PDF e confere o celular. Usa e-mail novo a cada execução.
import fs from "fs";
import os from "os";
import path from "path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const CNPJ = "11222333000181";

// NF-e de venda com itens: [ncm, cfop, icms (CSOSN/CST), cstPis, cest, valor, descrição]
function nfe(n, data, itens) {
  const chave = `3526031122233300018155001${String(n).padStart(9, "0")}1${String(n).padStart(8, "0")}`.slice(0, 43).padEnd(43, "0") + "1";
  const dets = itens.map(([ncm, cfop, icms, cstPis, cest, valor, nome], i) => {
    const grupoIcms = icms.length === 3 ? `<ICMSSN${icms}><orig>0</orig><CSOSN>${icms}</CSOSN></ICMSSN${icms}>` : `<ICMS${icms}><orig>0</orig><CST>${icms}</CST></ICMS${icms}>`;
    const grupoPis = cstPis === "04" ? `<PISNT><CST>04</CST></PISNT>` : `<PISOutr><CST>${cstPis}</CST></PISOutr>`;
    return `<det nItem="${i + 1}"><prod><cProd>${i + 1}</cProd><xProd>${nome}</xProd><NCM>${ncm}</NCM>${cest ? `<CEST>${cest}</CEST>` : ""}<CFOP>${cfop}</CFOP><vProd>${valor.toFixed(2)}</vProd><vDesc>0.00</vDesc></prod><imposto><ICMS>${grupoIcms}</ICMS><PIS>${grupoPis}</PIS></imposto></det>`;
  }).join("");
  const total = itens.reduce((s, i) => s + i[5], 0);
  return `<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe${chave}"><ide><mod>55</mod><dhEmi>${data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>${CNPJ}</CNPJ></emit><dest><CNPJ>45997418000153</CNPJ></dest>${dets}<total><ICMSTot><vICMS>0.00</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vNF>${total.toFixed(2)}</vNF></ICMSTot></total></infNFe></NFe><protNFe><infProt><chNFe>${chave}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>`;
}

const pasta = fs.mkdtempSync(path.join(os.tmpdir(), "rec-"));
const arquivos = [];
for (let i = 0; i < 13; i++) {
  const ano = 2025 + Math.floor(i / 12), mes = (i % 12) + 1;
  // 12 meses de R$ 100 mil sem itens especiais; no último, refrigerante (NCM da lista, ST na nota) e remédio (CST PIS 04)
  const itens = i < 12
    ? [["19059090", "5102", "102", "49", "", 100000, "BISCOITO RECHEADO"]]
    : [["22021000", "5405", "500", "49", "0300100", 10000, "REFRIGERANTE COLA 2L"], ["19059090", "5102", "102", "49", "", 90000, "BISCOITO RECHEADO"]];
  const arq = path.join(pasta, `venda-${i + 1}.xml`);
  fs.writeFileSync(arq, nfe(i + 1, `${ano}-${String(mes).padStart(2, "0")}-10`, itens));
  arquivos.push(arq);
}

const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Recuperação");
await page.fill("#nome", "Rita Contadora");
await page.fill("#email", `rita-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-recuperacao-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

await page.goto(`${BASE}/clientes/novo`);
await page.fill("#cnpj", CNPJ);
await page.fill("#razao_social", "Mercadinho Boa Compra Ltda");
await page.selectOption("#atividade", "comercio");
await page.getByRole("button", { name: "Cadastrar cliente" }).click();
await page.waitForURL(/\/clientes\/\d+$/);
passo("cliente do comércio cadastrado");

await page.getByRole("tab", { name: "Movimento fiscal" }).click();
await page.getByText("Importe os XML de NF-e de venda para descobrir").waitFor();
passo("antes de importar, a tela explica o que fazer");

await page.setInputFiles('input[aria-label="Arquivos fiscais"]', arquivos);
await page.getByText("13 importados · 0 já existiam").waitFor();
const secao = page.getByRole("region", { name: "Imposto pago a mais no Simples Nacional" });
await secao.waitFor();
await secao.getByText("R$ 432,43").first().waitFor(); // 136,79 de PIS/Cofins + 295,64 de ICMS
await secao.getByText("REFRIGERANTE COLA 2L").waitFor();
await secao.getByText("NCM da lista · ST indicado na nota").waitFor();
await secao.getByText("Indício, não certeza").waitFor();
await page.screenshot({ path: `${OUT}/rec-1-analise.png`, fullPage: true });
passo("importação lê os itens e mostra R$ 432,43 pagos a mais (PIS/Cofins R$ 136,79 + ICMS R$ 295,64)");

const [pdf] = await Promise.all([
  page.waitForResponse((r) => r.url().includes("/recuperacao") && r.request().method() === "POST"),
  secao.getByRole("button", { name: "Gerar relatório" }).click(),
]);
if (pdf.status() !== 201) throw new Error(`gerar relatório: ${pdf.status()}`);
await secao.getByText("Relatório salvo em Simulações.").waitFor();
const href = await secao.getByRole("link", { name: "Abrir PDF" }).getAttribute("href");
const resposta = await page.request.get(BASE + href);
if (resposta.headers()["content-type"] !== "application/pdf") throw new Error("PDF não veio");
passo("relatório gerado e PDF baixa");

await page.getByRole("tab", { name: /Simulações \(1\)/ }).click();
await page.getByText("Recuperação de tributos — R$ 432,43 pagos a mais no período").waitFor();
await page.getByRole("button", { name: "Ver" }).first().click();
await page.getByText("Economia por ano daqui para frente").first().waitFor();
await page.screenshot({ path: `${OUT}/rec-2-simulacao.png`, fullPage: true });
passo("relatório aparece nas simulações do cliente e abre com o mesmo conteúdo");

// Importar de novo não duplica
await page.getByRole("tab", { name: "Movimento fiscal" }).click();
await page.setInputFiles('input[aria-label="Arquivos fiscais"]', arquivos.slice(0, 2));
await page.getByText("0 importados · 2 já existiam").waitFor();
passo("reimportar não duplica nem completa o que já tem itens");

const celular = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await celular.context().addCookies(await ctx.cookies());
await celular.goto(page.url());
await celular.getByRole("tab", { name: "Movimento fiscal" }).click();
await celular.getByRole("region", { name: "Imposto pago a mais no Simples Nacional" }).getByText("R$ 432,43").first().waitFor();
const largura = await celular.evaluate(() => document.documentElement.scrollWidth);
await celular.screenshot({ path: `${OUT}/rec-3-celular.png`, fullPage: true });
if (largura > 390) throw new Error(`rolagem horizontal no celular: ${largura}px`);
passo("celular sem rolagem horizontal");

await browser.close();
fs.rmSync(pasta, { recursive: true, force: true });
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
