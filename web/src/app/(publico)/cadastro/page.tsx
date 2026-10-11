"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Botao, Campo, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";

export default function Cadastro() {
  const router = useRouter();
  const [form, setForm] = useState({ escritorio_nome: "", nome: "", email: "", senha: "" });
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const muda = (campo: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [campo]: e.target.value }));

  async function cadastrar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      await api("/auth/cadastro", { method: "POST", json: form });
      router.replace("/configuracoes?bemvindo=1");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Não foi possível cadastrar");
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={cadastrar} className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Cadastrar escritório</h1>
        <p className="mt-1 text-sm text-tinta-2">Você será o administrador da conta.</p>
      </div>
      <MensagemErro>{erro}</MensagemErro>
      <Campo rotulo="Nome do escritório" name="escritorio_nome" required minLength={2} value={form.escritorio_nome} onChange={muda("escritorio_nome")} />
      <Campo rotulo="Seu nome" name="nome" autoComplete="name" required minLength={2} value={form.nome} onChange={muda("nome")} />
      <Campo rotulo="E-mail" name="email" type="email" autoComplete="email" required value={form.email} onChange={muda("email")} />
      <Campo
        rotulo="Senha"
        name="senha"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        ajuda="Mínimo de 8 caracteres."
        value={form.senha}
        onChange={muda("senha")}
      />
      <Botao type="submit" carregando={enviando}>Criar conta</Botao>
      <p className="text-center text-sm text-tinta-2">
        Já tem conta?{" "}
        <Link href="/login" className="font-medium text-marca hover:underline">
          Entrar
        </Link>
      </p>
    </form>
  );
}
