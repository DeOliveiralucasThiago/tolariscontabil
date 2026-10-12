"use client";

import { useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import type { Envio } from "@/lib/tipos";

import { Botao, MensagemErro, Rotulo, classeCampo } from "./ui";

const separar = (texto: string) =>
  texto
    .split(/[,;\s]+/)
    .map((e) => e.trim())
    .filter(Boolean);

/** Envia o PDF de uma simulação por e-mail e mostra o histórico de envios. */
export function EnviarRelatorio({ simulacaoId, emailCliente, onFechar }: { simulacaoId: number; emailCliente: string | null; onFechar: () => void }) {
  const [para, setPara] = useState(emailCliente ?? "");
  const [mensagem, setMensagem] = useState("");
  const [envios, setEnvios] = useState<Envio[]>([]);
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api<Envio[]>(`/simulacoes/${simulacaoId}/envios`).then(setEnvios).catch(() => setEnvios([]));
  }, [simulacaoId]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setOk("");
    const destinatarios = separar(para);
    if (!destinatarios.length) return setErro("Informe ao menos um e-mail.");
    setEnviando(true);
    try {
      const envio = await api<Envio>(`/simulacoes/${simulacaoId}/enviar`, {
        method: "POST",
        json: { para: destinatarios, mensagem: mensagem.trim() || null },
      });
      setEnvios((x) => [envio, ...x]);
      setOk(`Relatório enviado para ${envio.para}.`);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha no envio");
      api<Envio[]>(`/simulacoes/${simulacaoId}/envios`).then(setEnvios).catch(() => undefined);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="mt-3 flex flex-col gap-3 rounded-lg border border-borda bg-fundo p-4">
      <div>
        <Rotulo htmlFor={`para-${simulacaoId}`}>Enviar para</Rotulo>
        <input
          id={`para-${simulacaoId}`}
          className={classeCampo}
          placeholder="email@cliente.com.br (separe vários por vírgula)"
          value={para}
          onChange={(e) => setPara(e.target.value)}
        />
      </div>
      <div>
        <Rotulo htmlFor={`msg-${simulacaoId}`}>Mensagem (opcional)</Rotulo>
        <textarea
          id={`msg-${simulacaoId}`}
          rows={3}
          className={`${classeCampo} h-auto py-2`}
          placeholder="Se deixar em branco, enviamos uma mensagem padrão com o nome do escritório."
          value={mensagem}
          onChange={(e) => setMensagem(e.target.value)}
        />
      </div>
      <MensagemErro>{erro}</MensagemErro>
      {ok && <p className="text-sm text-emerald-700">{ok}</p>}
      <div className="flex gap-2">
        <Botao type="submit" carregando={enviando}>Enviar PDF por e-mail</Botao>
        <Botao type="button" variante="fantasma" onClick={onFechar}>Fechar</Botao>
      </div>
      {envios.length > 0 && (
        <div className="text-xs text-tinta-2">
          <div className="mb-1 font-medium text-tinta">Envios</div>
          <ul className="flex flex-col gap-1">
            {envios.map((e) => (
              <li key={e.id} className="num">
                {dataHora(e.criado_em)} · {e.para} ·{" "}
                <span className={e.status === "enviado" ? "text-emerald-700" : "text-red-700"}>
                  {e.status === "enviado" ? "enviado" : "falhou"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
