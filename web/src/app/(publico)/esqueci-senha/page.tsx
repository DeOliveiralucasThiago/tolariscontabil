"use client";

import Link from "next/link";
import { useState } from "react";

import { Botao, Campo, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";

export default function EsqueciSenha() {
  const [email, setEmail] = useState("");
  const [enviado, setEnviado] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api("/auth/esqueci-senha", { method: "POST", json: { email } });
      setEnviado(true);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível enviar");
    } finally {
      setEnviando(false);
    }
  }

  if (enviado) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Verifique seu e-mail</h1>
        <p className="text-sm text-tinta-2">
          Se <strong>{email}</strong> estiver cadastrado, você vai receber um link para criar uma nova senha. O link vale
          por 1 hora.
        </p>
        <Link href="/login" className="text-sm font-medium text-marca hover:underline">Voltar para o login</Link>
      </div>
    );
  }

  return (
    <form onSubmit={enviar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Esqueci minha senha</h1>
        <p className="mt-1 text-sm text-tinta-2">Informe o e-mail da sua conta e enviaremos um link para redefinir a senha.</p>
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <Campo rotulo="E-mail" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Botao type="submit" carregando={enviando}>Enviar link</Botao>
      <Link href="/login" className="text-center text-sm text-tinta-2 hover:text-tinta">Voltar para o login</Link>
    </form>
  );
}
