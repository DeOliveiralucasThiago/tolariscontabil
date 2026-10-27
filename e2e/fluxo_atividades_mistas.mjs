// Receitas de mais de uma atividade: cada uma no seu Anexo do Simples, no planejamento completo e no Enquadramento.
// Sem rede externa. E-mail novo a cada execução.
import fs from "fs";
import { chromium } from "playwright";

const BASE = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.argv[2] ?? "e2e/saida";
fs.mkdirSync(OUT, { recursive: true });
const erros = [];
const browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
const passo = (t) => console.log("✓", t);
const corpo = async () => (await page.innerText("body")).replace(/ /g, " ");
const ctx = await browser.newContext({ viewport: { width: 1360, height: 1500 } });
const page = await ctx.newPage();
page.on("console", (m) => m.type() === "error" && !/401|Failed to load resource/.test(m.text()) && erros.push(m.text()));
page.on("pageerror", (e) => erros.push(String(e)));

await page.goto(`${BASE}/cadastro`);
await page.fill("#escritorio_nome", "Contabilidade Mista");
await page.fill("#nome", "Mara Contadora");
await page.fill("#email", `mara-${Date.now()}@teste.com.br`);
await page.fill("#senha", "senha-mista-12345");
await page.click("button[type=submit]");
await page.waitForURL("**/configuracoes?bemvindo=1");
const cid = (await (await page.request.post(BASE + "/api/clientes", { data: { razao_social: "Loja e Consultoria Ltda", atividade: "comercio", regime_atual: "simples" } })).json()).id;

const preencher = async () => {
  await page.getByTestId("bloco-atividades-mistas").waitFor();
  await page.fill("#receita", "180000000");        // R$ 1.800.000,00 (máscara: centavos)
  await page.fill("#folha_anual", "24000000");
  await page.fill("#prolabore_anual", "6000000");
  await page.fill("#compras", "70000000");
  await page.getByTestId("bloco-atividades-mistas").locator("summary").click();
  await page.fill("#outra_servico_fator_r", "60000000");   // R$ 600.000,00 em serviços do fator R
};

// 1. Planejamento completo: comércio (R$ 1,2 mi) + serviços do fator R (R$ 0,6 mi)
await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
await page.getByTestId("bloco-atividades-mistas").waitFor();
await preencher();
await page.click("text=Calcular e salvar planejamento");
await page.getByText("Regime recomendado").first().waitFor();
await page.waitForTimeout(800);
let texto = await corpo();
if (!/Receita segregada por atividade: Anexo I .* Anexo V/.test(texto)) throw new Error("o aviso da segregação por Anexo não apareceu");
if (!/ICMS/.test(texto) || !/ISS/.test(texto)) throw new Error("o Presumido deveria ter ICMS e ISS");
await page.screenshot({ path: `${OUT}/atividades_mistas_completa.png`, fullPage: true });
passo("planejamento: Simples com Anexo I e Anexo V; Presumido com ICMS e ISS");

// 2. Valor acima da receita bruta é barrado na tela
await page.goto(`${BASE}/clientes/${cid}?aba=planejamento`);
await page.fill("#receita", "10000000");
await page.getByTestId("bloco-atividades-mistas").locator("summary").click();
await page.fill("#outra_servico_fator_r", "20000000");
await page.click("text=Calcular e salvar planejamento");
await page.getByText("A soma das receitas das outras atividades não pode passar da receita bruta anual").waitFor();
passo("soma das outras atividades acima da receita é barrada");

// 3. Enquadramento: receita por Anexo hoje e cenários com serviços no Anexo III
await page.goto(`${BASE}/enquadramento?cliente=${cid}`);
await page.getByTestId("bloco-atividades-mistas").waitFor();
await page.getByTestId("cnaes-do-cliente").waitFor({ timeout: 3000 }).catch(() => {});
await page.waitForTimeout(1500);          // o cadastro do cliente termina de carregar e reinicia o formulário
await preencher();
await page.getByRole("button", { name: "Analisar enquadramento" }).click();
await page.getByTestId("resultado-enquadramento").waitFor({ timeout: 10000 }).catch(async (e) => { await page.screenshot({ path: `${OUT}/falha.png`, fullPage: true }); throw new Error((await corpo()).slice(0, 1500)); });
const ra = await page.getByTestId("receita-por-anexo").innerText();
if (!/Anexo I R\$ 1\.200\.000,00/.test(ra.replace(/ /g, " ")) || !/Anexo V R\$ 600\.000,00/.test(ra.replace(/ /g, " "))) throw new Error("receita por Anexo errada: " + ra);
texto = await corpo();
if (!texto.includes("de serviços do fator R")) throw new Error("os cenários deveriam falar da receita de serviços do fator R");
await page.screenshot({ path: `${OUT}/atividades_mistas_enquadramento.png`, fullPage: true });
passo("enquadramento mostra a receita por Anexo e os caminhos para a parte de serviços");

if (erros.length) throw new Error("Erros no console: " + erros.join(" | "));
await browser.close();
console.log("Fluxo das atividades mistas concluído.");
