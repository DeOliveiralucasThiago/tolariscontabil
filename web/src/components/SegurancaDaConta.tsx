"use client";

import { useState } from "react";

import { api, ErroApi } from "@/lib/api";
import type { Configurar2fa, Sessao } from "@/lib/tipos";

import { useSessao } from "./Sessao";
import { Aviso, Botao, Campo, Cartao, Etiqueta, MensagemErro } from "./ui";

type Etapa = "inicio" | "senha" | "qr" | "codigos" | "desativar" | "novos";

/** Verificação em duas etapas do próprio usuário: aplicativo autenticador e códigos de recuperação. */
export function SegurancaDaConta() {
  const { sessao, atualizar } = useSessao();
  const ativo = Boolean(sessao.usuario.totp_ativo);
  const [etapa, setEtapa] = useState<Etapa>("inicio");
  const [senha, setSenha] = useState("");
  const [codigo, setCodigo] = useState("");
  const [config, setConfig] = useState<Configurar2fa | null>(null);
  const [codigos, setCodigos] = useState<string[]>([]);
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [copiado, setCopiado] = useState(false);

  async function executar(fn: () => Promise<void>) {
    setErro("");
    setOcupado(true);
    try {
      await fn();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha na operação");
    } finally {
      setOcupado(false);
    }
  }

  const recarregarSessao = async () => atualizar(await api<Sessao>("/auth/me"));

  function limpar(proxima: Etapa = "inicio") {
    setEtapa(proxima);
    setSenha("");
    setCodigo("");
    setErro("");
  }

  const comecar = (e: React.FormEvent) => {
    e.preventDefault();
    return executar(async () => {
      setConfig(await api<Configurar2fa>("/auth/2fa/configurar", { method: "POST", json: { senha } }));
      setSenha("");
      setEtapa("qr");
    });
  };

  const ativar = (e: React.FormEvent) => {
    e.preventDefault();
    return executar(async () => {
      const r = await api<{ codigos_recuperacao: string[] }>("/auth/2fa/ativar", { method: "POST", json: { codigo } });
      setCodigos(r.codigos_recuperacao);
      setConfig(null);
      setCodigo("");
      setEtapa("codigos");
      await recarregarSessao();
    });
  };

  const desativar = (e: React.FormEvent) => {
    e.preventDefault();
    return executar(async () => {
      await api("/auth/2fa/desativar", { method: "POST", json: { senha, codigo } });
      limpar();
      await recarregarSessao();
    });
  };

  const novosCodigos = (e: React.FormEvent) => {
    e.preventDefault();
    return executar(async () => {
      const r = await api<{ codigos_recuperacao: string[] }>("/auth/2fa/novos-codigos", { method: "POST", json: { senha, codigo } });
      setCodigos(r.codigos_recuperacao);
      limpar("codigos");
    });
  };

  async function copiar() {
    if (navigator.clipboard) await navigator.clipboard.writeText(codigos.join("\n"));
    setCopiado(true);
    setTimeout(() => setCopiado(false), 2000);
  }

  function baixar() {
    const blob = new Blob([`Códigos de recuperação do Tolaris Contábil (${sessao.usuario.email})\nCada código vale uma vez.\n\n${codigos.join("\n")}\n`], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "codigos-de-recuperacao-tolaris.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <Cartao titulo="Verificação em duas etapas" acoes={<Etiqueta tom={ativo ? "ativo" : "inativo"}>{ativo ? "Ativada" : "Desativada"}</Etiqueta>}>
      <div className="flex flex-col gap-4 text-sm">
        <p className="text-tinta-2">
          Além da senha, o login pede um código do aplicativo autenticador do celular (Google Authenticator, Microsoft Authenticator, Authy…). Se a senha
          vazar, ninguém entra sem o seu celular.
        </p>
        <MensagemErro>{erro}</MensagemErro>

        {etapa === "inicio" && !ativo && <div><Botao onClick={() => setEtapa("senha")}>Ativar verificação em duas etapas</Botao></div>}
        {etapa === "inicio" && ativo && (
          <div className="flex flex-wrap gap-2">
            <Botao variante="secundario" onClick={() => setEtapa("novos")}>Gerar novos códigos de recuperação</Botao>
            <Botao variante="perigo" onClick={() => setEtapa("desativar")}>Desativar</Botao>
          </div>
        )}

        {etapa === "senha" && (
          <form onSubmit={comecar} className="flex max-w-sm flex-col gap-3">
            <Campo rotulo="Confirme a sua senha" name="senha_2fa" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
            <div className="flex gap-2">
              <Botao type="submit" carregando={ocupado}>Continuar</Botao>
              <Botao type="button" variante="fantasma" onClick={() => limpar()}>Cancelar</Botao>
            </div>
          </form>
        )}

        {etapa === "qr" && config && (
          <form onSubmit={ativar} className="flex flex-col gap-3">
            <ol className="list-decimal pl-5 text-tinta-2">
              <li>Abra o aplicativo autenticador no celular e escolha adicionar uma conta.</li>
              <li>Leia o QR code abaixo (ou digite a chave manualmente).</li>
              <li>Digite aqui o código de 6 dígitos que o aplicativo mostrar.</li>
            </ol>
            <div className="flex flex-wrap items-center gap-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                alt="QR code para o aplicativo autenticador"
                width={176}
                height={176}
                className="rounded-lg border border-borda bg-white p-1"
                src={`data:image/svg+xml;utf8,${encodeURIComponent(config.qr_svg)}`}
              />
              <div>
                <div className="text-xs text-tinta-2">Chave para digitar</div>
                <code className="num select-all break-all text-sm" aria-label="Chave secreta">{config.segredo.match(/.{1,4}/g)?.join(" ")}</code>
              </div>
            </div>
            <Campo rotulo="Código do aplicativo" name="codigo_ativar_2fa" inputMode="numeric" autoComplete="one-time-code" required className="max-w-xs" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
            <div className="flex gap-2">
              <Botao type="submit" carregando={ocupado}>Ativar</Botao>
              <Botao type="button" variante="fantasma" onClick={() => limpar()}>Cancelar</Botao>
            </div>
          </form>
        )}

        {etapa === "codigos" && (
          <div className="flex flex-col gap-3">
            <Aviso>Guarde estes códigos num lugar seguro (gerenciador de senhas ou papel). Cada um vale uma vez e serve para entrar se você perder o celular. Eles não serão mostrados de novo.</Aviso>
            <ul className="num grid max-w-md grid-cols-2 gap-2 rounded-lg border border-borda bg-fundo p-3" aria-label="Códigos de recuperação">
              {codigos.map((c) => <li key={c} className="select-all">{c}</li>)}
            </ul>
            <div className="flex flex-wrap gap-2">
              <Botao variante="secundario" onClick={copiar}>{copiado ? "Copiados" : "Copiar"}</Botao>
              <Botao variante="secundario" onClick={baixar}>Baixar .txt</Botao>
              <Botao onClick={() => { setCodigos([]); limpar(); }}>Já guardei os códigos</Botao>
            </div>
          </div>
        )}

        {(etapa === "desativar" || etapa === "novos") && (
          <form onSubmit={etapa === "desativar" ? desativar : novosCodigos} className="flex max-w-sm flex-col gap-3">
            <p className="text-tinta-2">
              {etapa === "desativar" ? "Para desativar, confirme a senha e um código do aplicativo (ou de recuperação)." : "Os códigos antigos deixam de valer. Confirme a senha e um código do aplicativo."}
            </p>
            <Campo rotulo="Senha" name="senha_2fa_op" type="password" autoComplete="current-password" required value={senha} onChange={(e) => setSenha(e.target.value)} />
            <Campo rotulo="Código" name="codigo_2fa_op" autoComplete="one-time-code" required value={codigo} onChange={(e) => setCodigo(e.target.value)} />
            <div className="flex gap-2">
              <Botao type="submit" variante={etapa === "desativar" ? "perigo" : "primario"} carregando={ocupado}>{etapa === "desativar" ? "Desativar" : "Gerar códigos"}</Botao>
              <Botao type="button" variante="fantasma" onClick={() => limpar()}>Cancelar</Botao>
            </div>
          </form>
        )}
      </div>
    </Cartao>
  );
}
