"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { Botao, Campo, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";

function Redefinir() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    if (senha !== confirmacao) return setErro("As senhas não conferem.");
    setEnviando(true);
    try {
      await api("/auth/redefinir-senha", { method: "POST", json: { token, senha } });
      router.replace("/painel");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível redefinir a senha");
      setEnviando(false);
    }
  }

  if (!token) {
    return (
      <div className="flex flex-col gap-3">
        <h1 className="text-2xl font-semibold">Link incompleto</h1>
        <Link href="/esqueci-senha" className="text-sm font-medium text-marca hover:underline">Pedir um novo link</Link>
      </div>
    );
  }

  return (
    <form onSubmit={salvar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Criar nova senha</h1>
        <p className="mt-1 text-sm text-tinta-2">As sessões abertas em outros aparelhos serão encerradas.</p>
      </div>
      <MensagemErro>
        {erro}
        {erro.includes("Link") && (
          <>
            {" "}
            <Link href="/esqueci-senha" className="font-medium underline">Pedir um novo link</Link>
          </>
        )}
      </MensagemErro>
      <Campo rotulo="Nova senha" name="senha" type="password" autoComplete="new-password" required minLength={8} ajuda="Mínimo de 8 caracteres." value={senha} onChange={(e) => setSenha(e.target.value)} />
      <Campo rotulo="Confirme a nova senha" name="confirmacao" type="password" autoComplete="new-password" required minLength={8} value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)} />
      <Botao type="submit" carregando={enviando}>Salvar e entrar</Botao>
    </form>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <Redefinir />
    </Suspense>
  );
}
