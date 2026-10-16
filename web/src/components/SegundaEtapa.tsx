"use client";

import { useState } from "react";

import { api, ErroApi } from "@/lib/api";

import { Botao, Campo, MensagemErro } from "./ui";

/** Segunda etapa do login: código do aplicativo autenticador ou código de recuperação. */
export function SegundaEtapa({
  token,
  onConcluido,
  onVoltar,
  aviso,
}: {
  token: string;
  onConcluido: () => void;
  onVoltar: () => void;
  aviso?: string;
}) {
  const [codigo, setCodigo] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api("/auth/login/2fa", { method: "POST", json: { token_2fa: token, codigo } });
      onConcluido();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível verificar o código");
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={confirmar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Verificação em duas etapas</h1>
        <p className="mt-1 text-sm text-tinta-2">
          {aviso && <>{aviso} </>}
          Digite o código de 6 dígitos do aplicativo autenticador. Sem o celular, use um código de recuperação (ex.: abcde-fghjk).
        </p>
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <Campo
        rotulo="Código"
        name="codigo_2fa"
        autoComplete="one-time-code"
        autoFocus
        required
        inputMode="text"
        value={codigo}
        onChange={(e) => setCodigo(e.target.value)}
      />
      <Botao type="submit" carregando={enviando}>Verificar e entrar</Botao>
      <button type="button" onClick={onVoltar} className="text-center text-sm text-tinta-2 hover:text-tinta">
        Voltar
      </button>
    </form>
  );
}
