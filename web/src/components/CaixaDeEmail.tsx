"use client";

import { useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import type { CaixaEmailEstado } from "@/lib/tipos";

import { Aviso, Botao, Campo, Cartao, MensagemErro } from "./ui";

/** Caixa de e-mail (IMAP) do escritório: os XML/ZIP/SPED que chegam nela entram no cliente certo pelo CNPJ. */
export function CaixaDeEmail() {
  const [estado, setEstado] = useState<CaixaEmailEstado | null>(null);
  const [host, setHost] = useState("");
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [pasta, setPasta] = useState("INBOX");
  const [ativo, setAtivo] = useState(true);
  const [erro, setErro] = useState("");
  const [msg, setMsg] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [verificando, setVerificando] = useState(false);

  function aplicar(e: CaixaEmailEstado) {
    setEstado(e);
    if (e.configurada) {
      setHost(e.host ?? "");
      setUsuario(e.usuario ?? "");
      setPasta(e.pasta ?? "INBOX");
      setAtivo(e.ativo);
    }
  }

  useEffect(() => {
    api<CaixaEmailEstado>("/escritorio/caixa-email").then(aplicar).catch(() => setEstado(null));
  }, []);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setMsg("");
    setSalvando(true);
    try {
      aplicar(
        await api<CaixaEmailEstado>("/escritorio/caixa-email", {
          method: "PUT",
          json: { host, porta: 993, usuario, senha: senha || null, pasta, ativo },
        }),
      );
      setSenha("");
      setMsg("Caixa de e-mail salva.");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function verificar() {
    setErro("");
    setMsg("");
    setVerificando(true);
    try {
      aplicar(await api<CaixaEmailEstado>("/escritorio/caixa-email/verificar", { method: "POST" }));
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao verificar");
    } finally {
      setVerificando(false);
    }
  }

  async function remover() {
    if (!confirm("Remover a caixa de e-mail? As notas já importadas continuam nos clientes.")) return;
    await api("/escritorio/caixa-email", { method: "DELETE" });
    setHost("");
    setUsuario("");
    setPasta("INBOX");
    setSenha("");
    setMsg("");
    setEstado(await api<CaixaEmailEstado>("/escritorio/caixa-email"));
  }

  const r = estado?.ultimo_resultado;
  return (
    <Cartao titulo="Caixa de entrada de notas (e-mail)">
      <div className="flex flex-col gap-4 text-sm">
        <p className="text-tinta-2">
          Peça aos clientes para mandarem os XML (soltos, em .zip) ou o SPED para um e-mail do escritório. Conectamos nessa caixa,
          lemos os anexos, achamos o cliente pelo CNPJ dentro do arquivo e importamos sem duplicar. A caixa é lida só para leitura:
          nada é apagado nem marcado como lido.
        </p>
        <Aviso>
          Use uma senha de aplicativo (Gmail, Yahoo) ou a senha da caixa de um provedor próprio. Contas Microsoft 365/Outlook
          costumam bloquear senha em IMAP; nesses casos, crie uma caixa à parte em outro provedor e encaminhe os e-mails para ela.
          A conexão é sempre segura (porta 993) e a senha fica criptografada no servidor.
        </Aviso>
        <form onSubmit={salvar} className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Servidor IMAP" name="imap_host" value={host} onChange={(e) => setHost(e.target.value)} placeholder="imap.seudominio.com.br" required />
          <Campo rotulo="Pasta" name="imap_pasta" value={pasta} onChange={(e) => setPasta(e.target.value)} required />
          <Campo rotulo="Usuário (e-mail)" name="imap_usuario" value={usuario} onChange={(e) => setUsuario(e.target.value)} autoComplete="off" required />
          <Campo
            rotulo="Senha"
            name="imap_senha"
            type="password"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="new-password"
            placeholder={estado?.configurada ? "•••••••• (mantida)" : ""}
            ajuda={estado?.configurada ? "Deixe em branco para manter a atual. Se mudar servidor ou usuário, digite de novo." : undefined}
            required={!estado?.configurada}
          />
          <label className="flex items-center gap-2 sm:col-span-2">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} className="accent-[var(--marca)]" />
            Ler esta caixa
            {estado && (
              <span className="text-xs text-tinta-2">
                {estado.automatico
                  ? `(automático a cada ${estado.intervalo_minutos} min)`
                  : "(a leitura automática está desligada neste servidor; use “Verificar agora”)"}
              </span>
            )}
          </label>
          <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
            <Botao type="submit" carregando={salvando}>Salvar</Botao>
            {estado?.configurada && (
              <>
                <Botao type="button" variante="secundario" onClick={verificar} carregando={verificando}>Verificar agora</Botao>
                <Botao type="button" variante="fantasma" onClick={remover}>Remover</Botao>
              </>
            )}
          </div>
        </form>
        <MensagemErro>{erro}</MensagemErro>
        {msg && <p className="text-emerald-700">{msg}</p>}
        {r && (
          <div className="rounded-lg border border-borda bg-fundo p-3" aria-label="Última verificação">
            <div className="font-medium">Última verificação: {dataHora(estado?.ultima_verificacao_em)}</div>
            {r.ok ? (
              <>
                <p className="mt-1">
                  {r.mensagens} {r.mensagens === 1 ? "mensagem nova" : "mensagens novas"} · {r.com_anexos} com anexos · {r.importados} notas
                  importadas · {r.duplicados} já existiam
                </p>
                {r.por_cliente.length > 0 && (
                  <ul className="mt-1 text-xs text-tinta-2">
                    {r.por_cliente.map((c) => (
                      <li key={c.cliente_id}>{c.cliente}: {c.importados} {c.importados === 1 ? "nota" : "notas"}</li>
                    ))}
                  </ul>
                )}
                {r.sem_cliente.length > 0 && (
                  <p className="mt-2 text-xs text-amber-900">
                    Sem cliente cadastrado com esse CNPJ: {r.sem_cliente.map((s) => `“${s}”`).join(", ")}. Cadastre o cliente (com CNPJ) e
                    peça o reenvio.
                  </p>
                )}
              </>
            ) : (
              <p className="mt-1 text-red-700">{r.erro}</p>
            )}
          </div>
        )}
      </div>
    </Cartao>
  );
}
