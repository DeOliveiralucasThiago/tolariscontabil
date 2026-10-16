"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import { linkWhatsapp, numeroWhatsapp } from "@/lib/whatsapp";
import type { PortalEstado } from "@/lib/tipos";

import { Botao, Cartao, MensagemErro, Rotulo, classeCampo } from "./ui";

/** Link de acesso do cliente aos relatórios publicados. O link só aparece ao ser gerado. */
export function PortalCliente({
  clienteId,
  emailCliente,
  telefoneCliente,
  contatoCliente,
  razaoSocial,
  escritorioNome,
  versao,
}: {
  clienteId: number;
  emailCliente: string | null;
  telefoneCliente: string | null;
  contatoCliente: string | null;
  razaoSocial: string;
  escritorioNome: string;
  versao: number;
}) {
  const [estado, setEstado] = useState<PortalEstado | null>(null);
  const [link, setLink] = useState("");
  const [enviarEmail, setEnviarEmail] = useState(Boolean(emailCliente));
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [gerando, setGerando] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const [mensagemZap, setMensagemZap] = useState("");
  const campoLink = useRef<HTMLInputElement>(null);

  const carregar = useCallback(() => {
    api<PortalEstado>(`/clientes/${clienteId}/portal`).then(setEstado).catch(() => setEstado(null));
  }, [clienteId]);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  async function gerar() {
    if (estado?.ativo && !confirm("Gerar um novo link desativa o link anterior. Continuar?")) return;
    setErro("");
    setAviso("");
    setGerando(true);
    try {
      const r = await api<{ link: string; enviado_para: string[]; envio_erro: string | null }>(`/clientes/${clienteId}/portal`, {
        method: "POST",
        json: { enviar_para: enviarEmail && emailCliente ? [emailCliente] : [] },
      });
      setLink(r.link);
      setAviso(r.envio_erro ?? (r.enviado_para.length ? `Link enviado para ${r.enviado_para.join(", ")}.` : ""));
      carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao gerar o link");
    } finally {
      setGerando(false);
    }
  }

  // Mensagem padrão do WhatsApp com o link recém-gerado (o usuário pode editar antes de enviar)
  useEffect(() => {
    if (!link) return;
    const primeiro = (contatoCliente ?? "").trim().split(/\s+/)[0];
    setMensagemZap(
      `Olá${primeiro ? `, ${primeiro}` : ""}! Aqui é do escritório ${escritorioNome}. ` +
        `Deixamos os relatórios de ${razaoSocial} no seu portal exclusivo: ${link}`,
    );
  }, [link, contatoCliente, escritorioNome, razaoSocial]);

  async function desativar() {
    if (!confirm("Desativar o portal? O link atual deixa de funcionar.")) return;
    await api(`/clientes/${clienteId}/portal`, { method: "DELETE" });
    setLink("");
    carregar();
  }

  async function copiar() {
    // Fora de HTTPS (ex.: teste na rede local) o navegador não oferece navigator.clipboard
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(link);
    } else {
      campoLink.current?.select();
      document.execCommand("copy");
    }
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  return (
    <Cartao titulo="Portal do cliente">
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-tinta-2">
          O cliente acessa por um link os relatórios marcados como <strong>publicados no portal</strong>, com a marca do
          escritório.{" "}
          {estado && (
            <>
              {estado.publicadas} {estado.publicadas === 1 ? "relatório publicado" : "relatórios publicados"}.
              {estado.ativo && <> Link ativo desde {dataHora(estado.criado_em)}; último acesso: {estado.ultimo_acesso_em ? dataHora(estado.ultimo_acesso_em) : "nunca"}.</>}
            </>
          )}
        </p>
        {link && (
          <div className="flex flex-col gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <span className="text-xs text-emerald-900">Copie agora: por segurança, o link não fica salvo para ser mostrado de novo.</span>
            <div className="flex gap-2">
              <input ref={campoLink} aria-label="Link do portal" readOnly className={`${classeCampo} num text-xs`} value={link} onFocus={(e) => e.target.select()} />
              <Botao type="button" variante="secundario" onClick={copiar}>{copiado ? "Copiado" : "Copiar"}</Botao>
            </div>
          </div>
        )}
        {link && (
          <div className="flex flex-col gap-2 rounded-lg border border-borda bg-fundo p-3">
            <Rotulo htmlFor="mensagem-whatsapp">Mensagem para o WhatsApp</Rotulo>
            <textarea
              id="mensagem-whatsapp"
              rows={3}
              className={`${classeCampo} h-auto py-2`}
              value={mensagemZap}
              onChange={(e) => setMensagemZap(e.target.value)}
            />
            <div className="flex flex-wrap items-center gap-3">
              <a
                href={linkWhatsapp(telefoneCliente, mensagemZap)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center rounded-lg border border-borda bg-superficie px-4 text-sm font-medium hover:bg-fundo"
              >
                Enviar pelo WhatsApp
              </a>
              <span className="text-xs text-tinta-2">
                {numeroWhatsapp(telefoneCliente)
                  ? `Abre a conversa com ${telefoneCliente}.`
                  : "Sem telefone válido no cadastro do cliente: o WhatsApp vai pedir para escolher o contato."}
              </span>
            </div>
            <p className="text-xs text-tinta-2">O link dá acesso a todos os relatórios publicados; envie só a quem deve vê-los.</p>
          </div>
        )}
        {aviso && <p className="text-sm text-emerald-700">{aviso}</p>}
        <MensagemErro>{erro}</MensagemErro>
        <div className="flex flex-wrap items-center gap-3">
          <Botao onClick={gerar} carregando={gerando}>{estado?.ativo ? "Gerar novo link" : "Gerar link do portal"}</Botao>
          {emailCliente && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={enviarEmail} onChange={(e) => setEnviarEmail(e.target.checked)} className="accent-[var(--marca)]" />
              Enviar para {emailCliente}
            </label>
          )}
          {estado?.ativo && <Botao variante="fantasma" onClick={desativar}>Desativar</Botao>}
        </div>
      </div>
    </Cartao>
  );
}
