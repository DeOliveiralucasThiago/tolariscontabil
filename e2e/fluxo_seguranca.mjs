// Segurança e LGPD: verificação em duas etapas (ativar, entrar com código, código errado, código de recuperação),
// registro de atividades, exportação e exclusão definitiva dos dados de um cliente e cabeçalhos de segurança.
// E-mail novo a cada execução; não precisa de e-mail nem da BrasilAPI.
import crypto from "crypto";
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });

const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|429|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

// TOTP (RFC 6238, SHA-1, 6 dígitos, 30 s) como um aplicativo autenticador
function base32(s) {
  const alfabeto = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of s.replace(/\s/g, "").toUpperCase()) bits += alfabeto.indexOf(c).toString(2).padStart(5, "0");
  return Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
}
function totp(segredo, passoExtra = 0) {
  const contador = Math.floor(Date.now() / 30000) + passoExtra;
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(contador));
  const h = crypto.createHmac("sha1", base32(segredo)).update(buf).digest();
  const o = h[19] & 15;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

const EMAIL = `lia-${Date.now()}@teste.com.br`;
const SENHA = "senha-seguranca-1";
await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Segura");
await page.fill("#nome", "Lia Contadora");
await page.fill("#email", EMAIL);
await page.fill("#senha", SENHA);
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");

// 1. Ativar a verificação em duas etapas
await page.getByRole("heading", { name: "Verificação em duas etapas" }).waitFor();
await page.getByRole("button", { name: "Ativar verificação em duas etapas" }).click();
await page.fill("#senha_2fa", SENHA);
await page.getByRole("button", { name: "Continuar" }).click();
await page.getByRole("img", { name: "QR code para o aplicativo autenticador" }).waitFor();
const segredo = (await page.getByLabel("Chave secreta").innerText()).replace(/\s/g, "");
if (segredo.length !== 32) throw new Error(`chave secreta inesperada: ${segredo}`);
await page.screenshot({ path: `${OUT}/seg-1-qr.png`, fullPage: true });
await page.fill("#codigo_ativar_2fa", "000000");
await page.getByRole("button", { name: "Ativar", exact: true }).click();
await page.getByText(/Código inválido/).waitFor();
await page.fill("#codigo_ativar_2fa", totp(segredo));
await page.getByRole("button", { name: "Ativar", exact: true }).click();
const lista = page.getByLabel("Códigos de recuperação");
await lista.waitFor();
const recuperacao = (await lista.locator("li").allInnerTexts()).map((t) => t.trim());
if (recuperacao.length !== 8 || !/^[a-z2-9]{5}-[a-z2-9]{5}$/.test(recuperacao[0])) throw new Error(`códigos inesperados: ${recuperacao}`);
await page.screenshot({ path: `${OUT}/seg-2-codigos.png`, fullPage: true });
await page.getByRole("button", { name: "Já guardei os códigos" }).click();
await page.getByText("Ativada", { exact: true }).waitFor();
passo("2FA ativada pela tela: QR, código errado recusado, código certo aceito e 8 códigos de recuperação");

// 2. Login em duas etapas
async function sair() {
  await page.getByRole("button", { name: "Sair" }).click();
  await page.waitForURL("**/login");
}
await sair();
await page.fill("#email", EMAIL);
await page.fill("#senha", SENHA);
await page.getByRole("button", { name: "Entrar" }).click();
await page.getByRole("heading", { name: "Verificação em duas etapas" }).waitFor();
await page.screenshot({ path: `${OUT}/seg-3-segunda-etapa.png` });
await page.fill("#codigo_2fa", "123456");
await page.getByRole("button", { name: "Verificar e entrar" }).click();
await page.getByText(/Código inválido ou já usado/).waitFor();
await page.fill("#codigo_2fa", totp(segredo, 1)); // o intervalo da ativação já foi usado; o seguinte vale
await page.getByRole("button", { name: "Verificar e entrar" }).click();
await page.waitForURL("**/painel");
passo("login pede o código: errado é recusado, certo entra (o código da ativação não serve de novo)");

await sair();
await page.fill("#email", EMAIL);
await page.fill("#senha", SENHA);
await page.getByRole("button", { name: "Entrar" }).click();
await page.fill("#codigo_2fa", recuperacao[0]);
await page.getByRole("button", { name: "Verificar e entrar" }).click();
await page.waitForURL("**/painel");
await sair();
await page.fill("#email", EMAIL);
await page.fill("#senha", SENHA);
await page.getByRole("button", { name: "Entrar" }).click();
await page.fill("#codigo_2fa", recuperacao[0]);
await page.getByRole("button", { name: "Verificar e entrar" }).click();
await page.getByText(/Código inválido ou já usado/).waitFor();
passo("código de recuperação entra uma vez; a segunda tentativa com o mesmo código é recusada");
await page.fill("#codigo_2fa", recuperacao[1]);
await page.getByRole("button", { name: "Verificar e entrar" }).click();
await page.waitForURL("**/painel");

// 3. Registro de atividades
await page.goto(`${BASE}/configuracoes`);
const registro = page.getByRole("heading", { name: "Registro de atividades" });
await registro.waitFor();
await page.getByRole("cell", { name: /Ativou a verificação em duas etapas/ }).first().waitFor();
await page.getByRole("cell", { name: /Usou um código de recuperação/ }).first().waitFor();
await page.getByRole("cell", { name: /Código de verificação recusado/ }).first().waitFor();
await page.screenshot({ path: `${OUT}/seg-4-registro.png`, fullPage: true });
await page.getByLabel("Ação").selectOption("codigo_recuperacao_usado");
await page.waitForFunction(() => document.querySelectorAll("tbody tr").length === 2);
const csv = await page.request.get(`${BASE}/api/escritorio/auditoria/exportar.csv?acao=codigo_recuperacao_usado`);
if (!(csv.headers()["content-type"] ?? "").startsWith("text/csv") || (await csv.text()).split("\n").length < 3) throw new Error("exportação CSV não veio");
passo("registro de atividades mostra ativação, recusas e códigos de recuperação; filtro e CSV funcionam");

// 4. LGPD: exportar e excluir os dados de um cliente
const api = async (metodo, caminho, opcoes = {}) => {
  const r = await page.request.fetch(BASE + "/api" + caminho, { method: metodo, ...opcoes });
  if (!r.ok()) throw new Error(`${metodo} ${caminho}: ${r.status()} ${await r.text()}`);
  return r.status() === 204 ? null : r.json();
};
const cliente = await api("POST", "/clientes", { data: { razao_social: "Titular dos Dados Ltda", cnpj: "11222333000181", email: "titular@exemplo.com.br", contato_nome: "Maria Titular" } });
await api("POST", `/clientes/${cliente.id}/simulacoes/completa`, { data: { atividade: "comercio", receita_bruta_anual: 600000, compras_anual: 300000 } });
await page.goto(`${BASE}/clientes/${cliente.id}?aba=dados`);
await page.getByRole("heading", { name: "Privacidade e dados (LGPD)" }).waitFor();
const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("link", { name: "Baixar todos os dados (JSON)" }).click()]);
const arquivo = await download.path();
const dados = JSON.parse(fs.readFileSync(arquivo, "utf8"));
if (dados.cliente.razao_social !== "Titular dos Dados Ltda" || dados.simulacoes.length !== 1 || dados.cliente.contato_nome !== "Maria Titular") throw new Error("exportação incompleta");
if (!download.suggestedFilename().startsWith(`dados-cliente-${cliente.id}-`)) throw new Error("nome do arquivo inesperado");
await page.screenshot({ path: `${OUT}/seg-5-lgpd.png`, fullPage: true });
passo("exportação baixa o JSON com cadastro, simulações e histórico do cliente");

page.once("dialog", (d) => d.accept());
await page.getByRole("button", { name: "Excluir cliente e todos os dados" }).click();
await page.waitForURL("**/clientes");
const lista2 = await api("GET", "/clientes");
if (lista2.some((c) => c.id === cliente.id)) throw new Error("cliente não foi excluído");
const aud = await api("GET", "/escritorio/auditoria?acao=cliente_excluido");
if (aud.total !== 1 || JSON.stringify(aud).includes("Titular dos Dados")) throw new Error("registro da exclusão inesperado");
passo("exclusão definitiva: cliente some e o registro guarda só o fato, sem o nome");

// 5. Cabeçalhos de segurança
const r = await page.request.get(`${BASE}/login`);
const h = r.headers();
if (h["x-frame-options"] !== "DENY" || h["x-content-type-options"] !== "nosniff" || !h["content-security-policy"]?.includes("frame-ancestors 'none'")) throw new Error(`cabeçalhos do site: ${JSON.stringify(h)}`);
const a = await page.request.get(`${BASE}/api/saude`);
if (a.headers()["cache-control"] !== "no-store" || a.headers()["x-content-type-options"] !== "nosniff") throw new Error(`cabeçalhos da API: ${JSON.stringify(a.headers())}`);
passo("site e API com cabeçalhos de segurança (sem moldura, nosniff, API sem cache)");

await browser.close();
console.log(erros.length ? "ERROS NO CONSOLE:\n" + erros.join("\n") : "Sem erros no console");
process.exit(erros.length ? 1 : 0);
