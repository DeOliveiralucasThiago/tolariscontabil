// Fase 3 no navegador: esqueci a senha, equipe (convite e permissões), importação de NF-e/SPED,
// planejamento a partir do movimento, envio do relatório por e-mail e portal do cliente.
// A API precisa rodar com TOLARIS_EMAIL_BACKEND=arquivo e TOLARIS_EMAIL_PASTA=<EMAIL_DIR>.
import fs from "fs";
import os from "os";
import path from "path";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
const EMAIL_DIR = process.env.EMAIL_DIR;
if (!EMAIL_DIR) throw new Error("Defina EMAIL_DIR (a mesma pasta de TOLARIS_EMAIL_PASTA)");
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const sufixo = Date.now();
const ADMIN = `admin-${sufixo}@teste.com.br`;
const MEMBRO = `membro-${sufixo}@teste.com.br`;
const CNPJ = "11222333000181";

function novaPagina(ctx) {
  return ctx.newPage().then((p) => {
    p.on("console", (m) => m.type() === "error" && !m.text().includes("401") && erros.push(m.text()));
    p.on("pageerror", (e) => erros.push(String(e)));
    return p;
  });
}

async function ultimoEmail(para, contendo) {
  for (let i = 0; i < 40; i++) {
    const msgs = fs.readdirSync(EMAIL_DIR).filter((f) => f.endsWith(".json")).sort().reverse()
      .map((f) => JSON.parse(fs.readFileSync(path.join(EMAIL_DIR, f), "utf-8")))
      .filter((m) => m.para.includes(para) && m.texto.includes(contendo));
    if (msgs.length) return msgs[0];
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`E-mail para ${para} com "${contendo}" não chegou`);
}
const link = (texto) => texto.match(/https?:\/\/\S+/)[0].replace(/^https?:\/\/[^/]+/, BASE);

// Arquivos fiscais de exemplo
function nfe(n, emit, dest, data, valor) {
  const chave = `3526031122233300018155001${String(n).padStart(9, "0")}1${String(n).padStart(8, "0")}`.slice(0, 43).padEnd(43, "0") + "1";
  return `<?xml version="1.0"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe${chave}">
<ide><mod>55</mod><dhEmi>${data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide><emit><CNPJ>${emit}</CNPJ></emit><dest><CNPJ>${dest}</CNPJ></dest>
<total><ICMSTot><vICMS>${(valor * 0.18).toFixed(2)}</vICMS><vIPI>0.00</vIPI><vPIS>0.00</vPIS><vCOFINS>0.00</vCOFINS><vNF>${valor.toFixed(2)}</vNF></ICMSTot></total>
</infNFe></NFe><protNFe><infProt><chNFe>${chave}</chNFe><cStat>100</cStat></infProt></protNFe></nfeProc>`;
}
const pastaFiscal = fs.mkdtempSync(path.join(os.tmpdir(), "fiscal-"));
const arquivos = [];
for (let m = 1; m <= 6; m++) {
  const mes = String(m).padStart(2, "0");
  const venda = path.join(pastaFiscal, `venda-${mes}.xml`);
  fs.writeFileSync(venda, nfe(m, CNPJ, "45997418000153", `2026-${mes}-10`, 50000 + m * 1000));
  const compra = path.join(pastaFiscal, `compra-${mes}.xml`);
  fs.writeFileSync(compra, nfe(100 + m, "11444777000161", CNPJ, `2026-${mes}-12`, 20000));
  arquivos.push(venda, compra);
}

// 1. Cadastro do administrador e "esqueci a senha"
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const page = await novaPagina(ctx);
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Fase 3");
await page.fill("#nome", "Carla Admin");
await page.fill("#email", ADMIN);
await page.fill("#senha", "senha-original-1");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
await page.click("text=Sair");
await page.waitForURL("**/login");
await page.click("text=Esqueci minha senha");
await page.waitForURL("**/esqueci-senha"); // o login também tem #email: esperar a troca de página
await page.getByRole("heading", { name: "Esqueci minha senha" }).waitFor();
await page.fill("#email", ADMIN);
await page.getByRole("button", { name: "Enviar link" }).click();
await page.getByText("Verifique seu e-mail").waitFor();
const emailSenha = await ultimoEmail(ADMIN, "redefinir-senha");
await page.goto(link(emailSenha.texto));
await page.fill("#senha", "senha-nova-2026");
await page.fill("#confirmacao", "senha-nova-2026");
await page.getByRole("button", { name: "Salvar e entrar" }).click();
await page.waitForURL("**/painel");
passo("esqueci a senha: e-mail recebido, senha redefinida e login automático");

// 2. Equipe: convite e aceite em outro navegador
await page.click("aside >> text=Equipe");
await page.fill("#email_convite", MEMBRO);
await page.fill("#nome_convite", "Diego");
await page.getByRole("button", { name: "Enviar convite" }).click();
await page.getByText(`Convite enviado para ${MEMBRO}.`).waitFor();
await page.screenshot({ path: `${OUT}/f3-1-equipe.png`, fullPage: true });
const emailConvite = await ultimoEmail(MEMBRO, "/convite?token=");
const ctxMembro = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const membro = await novaPagina(ctxMembro);
await membro.goto(link(emailConvite.texto));
await membro.getByText("Contabilidade Fase 3").waitFor();
await membro.fill("#senha", "senha-do-diego-1");
await membro.getByRole("button", { name: "Aceitar convite" }).click();
await membro.waitForURL("**/painel");
await membro.click("aside >> text=Configurações");
await membro.getByText("Apenas administradores alteram os dados").waitFor();
await membro.click("aside >> text=Equipe");
await membro.getByText("Diego").first().waitFor();
if (await membro.getByRole("button", { name: "Enviar convite" }).count()) throw new Error("membro não deveria convidar");
passo("convite aceito; membro entra, mas não administra o escritório");

// 3. Cliente com CNPJ e e-mail
await page.goto(`${BASE}/clientes/novo`);
await page.fill("#cnpj", CNPJ);
await page.fill("#razao_social", "Distribuidora Boa Vista Ltda");
await page.selectOption("#atividade", "comercio");
await page.fill("#email", "financeiro@boavista.com.br");
await page.getByRole("button", { name: "Cadastrar cliente" }).click();
await page.waitForURL(/\/clientes\/\d+$/);
passo("cliente cadastrado");

// 4. Movimento fiscal: importação e uso no planejamento
await page.getByRole("tab", { name: "Movimento fiscal" }).click();
await page.setInputFiles('input[aria-label="Arquivos fiscais"]', arquivos);
await page.getByText("12 importados · 0 já existiam").waitFor();
await page.setInputFiles('input[aria-label="Arquivos fiscais"]', arquivos.slice(0, 2));
await page.getByText("0 importados · 2 já existiam").waitFor();
await page.getByText("Movimento mensal").waitFor();
await page.screenshot({ path: `${OUT}/f3-2-movimento.png`, fullPage: true });
await page.getByRole("button", { name: "Usar no planejamento" }).click();
const receita = await page.inputValue("#receita");
if (receita !== "642.000,00") throw new Error(`receita anualizada inesperada: ${receita}`); // 321 mil em 6 meses x 2
await page.getByRole("button", { name: "Calcular e salvar planejamento" }).click();
await page.getByText("Planejamento tributário 2026").first().waitFor();
passo(`12 notas importadas, duplicatas ignoradas, planejamento preenchido (receita anualizada R$ ${receita})`);

// 5. Publicar no portal e enviar por e-mail
const item = page.locator("li", { hasText: "Planejamento tributário 2026" });
await item.getByRole("checkbox").check();
await item.getByRole("button", { name: "Enviar" }).click();
await page.getByRole("button", { name: "Enviar PDF por e-mail" }).click();
await page.getByText("Relatório enviado para financeiro@boavista.com.br.").waitFor();
const emailRelatorio = await ultimoEmail("financeiro@boavista.com.br", "Segue em anexo");
if (!emailRelatorio.anexos[0]?.endsWith(".pdf")) throw new Error("e-mail sem PDF");
passo(`relatório enviado com anexo ${emailRelatorio.anexos[0].split("-").slice(4).join("-")}`);

// 6. Portal do cliente
await page.getByRole("button", { name: "Gerar link do portal" }).click();
const campoLink = page.getByLabel("Link do portal");
await campoLink.waitFor();
const urlPortal = (await campoLink.inputValue()).replace(/^https?:\/\/[^/]+/, BASE);
await page.getByText("Link enviado para financeiro@boavista.com.br.").waitFor();
await page.screenshot({ path: `${OUT}/f3-3-cliente.png`, fullPage: true });
const ctxCliente = await browser.newContext({ viewport: { width: 1360, height: 900 } });
const cliente = await novaPagina(ctxCliente);
await cliente.goto(urlPortal);
await cliente.getByRole("heading", { name: "Distribuidora Boa Vista Ltda" }).waitFor();
await cliente.getByText("Regime recomendado").waitFor();
const pdfPortal = await cliente.request.get(BASE + (await cliente.getByRole("link", { name: "Baixar PDF" }).getAttribute("href")));
if (pdfPortal.headers()["content-type"] !== "application/pdf") throw new Error("PDF do portal não veio");
await cliente.screenshot({ path: `${OUT}/f3-4-portal.png`, fullPage: true });
passo("portal do cliente abre sem login, mostra o relatório publicado e baixa o PDF");

const celular = await (await browser.newContext({ viewport: { width: 390, height: 844 } })).newPage();
await celular.goto(urlPortal);
await celular.getByText("Regime recomendado").waitFor();
const larg = await celular.evaluate(() => document.documentElement.scrollWidth);
await celular.screenshot({ path: `${OUT}/f3-5-portal-celular.png`, fullPage: true });
if (larg > 390) throw new Error(`rolagem horizontal no portal: ${larg}px`);
passo("portal no celular sem rolagem horizontal");

// 7. Novo link derruba o anterior
page.once("dialog", (d) => d.accept()); // confirmação "o link anterior deixa de funcionar"
await page.getByRole("button", { name: "Gerar novo link" }).click();
await page.waitForFunction((antigo) => {
  const el = document.querySelector('input[aria-label="Link do portal"]');
  return el && el.value && !el.value.endsWith(antigo);
}, urlPortal.split("/").pop());
const errosAntes = erros.length;
await cliente.reload();
await cliente.getByText("Este link não está mais ativo").waitFor();
// O 404 do link antigo é o comportamento esperado aqui
erros.splice(errosAntes, erros.length - errosAntes, ...erros.slice(errosAntes).filter((e) => !e.includes("404")));
passo("gerar novo link desativa o anterior");

await browser.close();
fs.rmSync(pastaFiscal, { recursive: true, force: true });
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
