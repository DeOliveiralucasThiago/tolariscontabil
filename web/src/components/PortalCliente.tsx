"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import type { PortalEstado } from "@/lib/tipos";

import { Botao, Cartao, MensagemErro, classeCampo } from "./ui";

/** Link de acesso do cliente aos relatórios publicados. O link só aparece ao ser gerado. */
export function PortalCliente({ clienteId, emailCliente, versao }: { clienteId: number; emailCliente: string | null; versao: number }) {
  const [estado, setEstado] = useState<PortalEstado | null>(null);
  const [link, setLink] = useState("");
  const [enviarEmail, setEnviarEmail] = useState(Boolean(emailCliente));
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [gerando, setGerando] = useState(false);
  const [copiado, setCopiado] = useState(false);

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

  async function desativar() {
    if (!confirm("Desativar o portal? O link atual deixa de funcionar.")) return;
    await api(`/clientes/${clienteId}/portal`, { method: "DELETE" });
    setLink("");
    carregar();
  }

  async function copiar() {
    await navigator.clipboard.writeText(link);
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
              <input aria-label="Link do portal" readOnly className={`${classeCampo} num text-xs`} value={link} onFocus={(e) => e.target.select()} />
              <Botao type="button" variante="secundario" onClick={copiar}>{copiado ? "Copiado" : "Copiar"}</Botao>
            </div>
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
