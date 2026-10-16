"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { SegundaEtapa } from "@/components/SegundaEtapa";
import { Botao, Campo, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import type { Requer2fa } from "@/lib/tipos";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [token2fa, setToken2fa] = useState<string | null>(null);

  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const r = await api<Requer2fa | object>("/auth/login", { method: "POST", json: { email, senha } });
      if ("requer_2fa" in r) {
        setToken2fa(r.token_2fa);
        setEnviando(false);
        return;
      }
      router.replace("/painel");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível entrar");
      setEnviando(false);
    }
  }

  if (token2fa) {
    return <SegundaEtapa token={token2fa} onConcluido={() => router.replace("/painel")} onVoltar={() => { setToken2fa(null); setSenha(""); }} />;
  }

  return (
    <form onSubmit={entrar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Entrar</h1>
        <p className="mt-1 text-sm text-tinta-2">Acesse a área do seu escritório.</p>
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <Campo rotulo="E-mail" name="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      <Campo rotulo="Senha" name="senha" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
      <Botao type="submit" carregando={enviando}>Entrar</Botao>
      <Link href="/esqueci-senha" className="text-center text-sm text-tinta-2 hover:text-tinta">
        Esqueci minha senha
      </Link>
      <p className="text-center text-sm text-tinta-2">
        Novo por aqui?{" "}
        <Link href="/cadastro" className="font-medium text-marca hover:underline">
          Cadastre seu escritório
        </Link>
      </p>
    </form>
  );
}
