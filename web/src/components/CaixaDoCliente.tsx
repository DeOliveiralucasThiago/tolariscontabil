"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import type { CaixaEstado } from "@/lib/tipos";
import { linkWhatsapp, numeroWhatsapp } from "@/lib/whatsapp";

import { Botao, Cartao, MensagemErro, Rotulo, classeCampo } from "./ui";

/** Link para o cliente (ou o emissor dele) enviar os XML das notas sem criar conta. */
export function CaixaDoCliente({
  clienteId,
  emailCliente,
  telefoneCliente,
  contatoCliente,
  razaoSocial,
  escritorioNome,
  versao,
  onNovasNotas,
}: {
  clienteId: number;
  emailCliente: string | null;
  telefoneCliente: string | null;
  contatoCliente: string | null;
  razaoSocial: string;
  escritorioNome: string;
  versao: number;
  onNovasNotas: () => void;
}) {
  const [estado, setEstado] = useState<CaixaEstado | null>(null);
  const [link, setLink] = useState("");
  const [enviarEmail, setEnviarEmail] = useState(Boolean(emailCliente));
  const [mensagemZap, setMensagemZap] = useState("");
  const [aviso, setAviso] = useState("");
  const [erro, setErro] = useState("");
  const [gerando, setGerando] = useState(false);
  const [copiado, setCopiado] = useState(false);

  const carregar = useCallback(() => {
    api<CaixaEstado>(`/clientes/${clienteId}/caixa`)
      .then((novo) => {
        setEstado((antes) => {
          if (antes && novo.total_notas > antes.total_notas) onNovasNotas(); // chegaram notas pelo link
          return novo;
        });
      })
      .catch(() => setEstado(null));
  }, [clienteId, onNovasNotas]);

  useEffect(() => {
    carregar();
  }, [carregar, versao]);

  useEffect(() => {
    if (!link) return;
    const primeiro = (contatoCliente ?? "").trim().split(/\s+/)[0];
    setMensagemZap(
      `Olá${primeiro ? `, ${primeiro}` : ""}! Aqui é do escritório ${escritorioNome}. ` +
        `Para enviar as notas fiscais de ${razaoSocial}, é só abrir este link e arrastar os arquivos XML (ou um .zip): ${link}`,
    );
  }, [link, contatoCliente, escritorioNome, razaoSocial]);

  async function gerar() {
    if (estado?.ativo && !confirm("Gerar um novo link desativa o link anterior. Continuar?")) return;
    setErro("");
    setAviso("");
    setGerando(true);
    try {
      const r = await api<{ link: string; enviado_para: string[]; envio_erro: string | null }>(`/clientes/${clienteId}/caixa`, {
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
    if (!confirm("Desativar o link de envio? O link atual deixa de funcionar.")) return;
    await api(`/clientes/${clienteId}/caixa`, { method: "DELETE" });
    setLink("");
    carregar();
  }

  async function copiar() {
    if (navigator.clipboard) await navigator.clipboard.writeText(link);
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  return (
    <Cartao titulo="Receber notas do cliente">
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-tinta-2">
          Gere um link e mande para o cliente ou para o sistema emissor dele: os XML (soltos ou em .zip) entram aqui sozinhos, sem
          criar conta e sem duplicar notas.
          {estado?.ativo && (
            <>
              {" "}
              Link ativo desde {dataHora(estado.criado_em)}.{" "}
              {estado.total_envios > 0
                ? `Recebeu ${estado.total_notas} ${estado.total_notas === 1 ? "nota" : "notas"} em ${estado.total_envios} ${estado.total_envios === 1 ? "envio" : "envios"}; último em ${dataHora(estado.ultimo_envio_em)}.`
                : "Ainda não recebeu envios."}
            </>
          )}
        </p>
        {link && (
          <div className="flex flex-col gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <span className="text-xs text-emerald-900">Copie agora: por segurança, o link não fica salvo para ser mostrado de novo.</span>
            <div className="flex gap-2">
              <input aria-label="Link de envio de notas" readOnly className={`${classeCampo} num text-xs`} value={link} onFocus={(e) => e.target.select()} />
              <Botao type="button" variante="secundario" onClick={copiar}>{copiado ? "Copiado" : "Copiar"}</Botao>
            </div>
          </div>
        )}
        {link && (
          <div className="flex flex-col gap-2 rounded-lg border border-borda bg-fundo p-3">
            <Rotulo htmlFor="mensagem-whatsapp-notas">Mensagem para o WhatsApp</Rotulo>
            <textarea
              id="mensagem-whatsapp-notas"
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
              {!numeroWhatsapp(telefoneCliente) && (
                <span className="text-xs text-tinta-2">Sem telefone válido no cadastro: o WhatsApp vai pedir para escolher o contato.</span>
              )}
            </div>
          </div>
        )}
        {aviso && <p className="text-sm text-emerald-700">{aviso}</p>}
        <MensagemErro>{erro}</MensagemErro>
        <div className="flex flex-wrap items-center gap-3">
          <Botao onClick={gerar} carregando={gerando}>{estado?.ativo ? "Gerar novo link" : "Gerar link de envio"}</Botao>
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
