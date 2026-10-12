"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Botao, Campo, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";

interface Convite {
  escritorio: string;
  email: string;
  nome: string | null;
  papel: string | null;
}

function AceitarConvite() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [convite, setConvite] = useState<Convite | null>(null);
  const [nome, setNome] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!token) return setErro("Link de convite incompleto.");
    api<Convite>(`/convites/${encodeURIComponent(token)}`)
      .then((c) => {
        setConvite(c);
        setNome(c.nome ?? "");
      })
      .catch((e) => setErro(e instanceof ErroApi ? e.message : "Convite inválido"));
  }, [token]);

  async function aceitar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api("/convites/aceitar", { method: "POST", json: { token, nome, senha } });
      router.replace("/painel");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível aceitar o convite");
      setEnviando(false);
    }
  }

  if (!convite) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold">Convite</h1>
        {erro ? <MensagemErro>{erro} Peça um novo convite ao administrador do escritório.</MensagemErro> : <p className="text-sm text-tinta-2">Carregando…</p>}
        <Link href="/login" className="text-sm font-medium text-marca hover:underline">Ir para o login</Link>
      </div>
    );
  }

  return (
    <form onSubmit={aceitar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Entrar na equipe</h1>
        <p className="mt-1 text-sm text-tinta-2">
          Você foi convidado(a) para <strong>{convite.escritorio}</strong>
          {convite.papel === "admin" ? " como administrador(a)" : ""}. Crie sua senha para começar.
        </p>
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <Campo rotulo="E-mail" name="email" value={convite.email} disabled />
      <Campo rotulo="Seu nome" name="nome" autoComplete="name" required minLength={2} value={nome} onChange={(e) => setNome(e.target.value)} />
      <Campo rotulo="Senha" name="senha" type="password" autoComplete="new-password" required minLength={8} ajuda="Mínimo de 8 caracteres." value={senha} onChange={(e) => setSenha(e.target.value)} />
      <Botao type="submit" carregando={enviando}>Aceitar convite</Botao>
    </form>
  );
}

export default function Pagina() {
  return (
    <Suspense>
      <AceitarConvite />
    </Suspense>
  );
}
