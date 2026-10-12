"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useRef, useState } from "react";

import { aplicarCorMarca, useSessao } from "@/components/Sessao";
import { Botao, Campo, Cartao, MensagemErro, Rotulo, Titulo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import { cnpjValido, mascaraCnpj, soDigitos } from "@/lib/formato";
import type { Sessao } from "@/lib/tipos";

function AlterarSenha() {
  const { atualizar } = useSessao();
  const [f, setF] = useState({ senha_atual: "", nova_senha: "", confirmacao: "" });
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [salvando, setSalvando] = useState(false);

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setOk("");
    if (f.nova_senha !== f.confirmacao) return setErro("As senhas não conferem.");
    setSalvando(true);
    try {
      atualizar(await api<Sessao>("/auth/alterar-senha", { method: "POST", json: { senha_atual: f.senha_atual, nova_senha: f.nova_senha } }));
      setF({ senha_atual: "", nova_senha: "", confirmacao: "" });
      setOk("Senha alterada. As sessões em outros aparelhos foram encerradas.");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao alterar a senha");
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Cartao titulo="Minha senha">
      <form onSubmit={salvar} className="grid gap-4 sm:grid-cols-3">
        <Campo rotulo="Senha atual" name="senha_atual" type="password" autoComplete="current-password" required value={f.senha_atual} onChange={(e) => setF((x) => ({ ...x, senha_atual: e.target.value }))} />
        <Campo rotulo="Nova senha" name="nova_senha" type="password" autoComplete="new-password" required minLength={8} value={f.nova_senha} onChange={(e) => setF((x) => ({ ...x, nova_senha: e.target.value }))} />
        <Campo rotulo="Confirme" name="confirmacao_senha" type="password" autoComplete="new-password" required minLength={8} value={f.confirmacao} onChange={(e) => setF((x) => ({ ...x, confirmacao: e.target.value }))} />
        <div className="sm:col-span-3 flex flex-col gap-2">
          <MensagemErro>{erro}</MensagemErro>
          {ok && <p className="text-sm text-emerald-700">{ok}</p>}
          <div><Botao type="submit" variante="secundario" carregando={salvando}>Alterar senha</Botao></div>
        </div>
      </form>
    </Cartao>
  );
}

function Configuracoes() {
  const { sessao, atualizar } = useSessao();
  const admin = sessao.usuario.papel === "admin";
  const bemVindo = useSearchParams().get("bemvindo");
  const esc = sessao.escritorio;
  const [f, setF] = useState({
    nome: esc.nome,
    cnpj: esc.cnpj ? mascaraCnpj(esc.cnpj) : "",
    contador_responsavel: esc.contador_responsavel ?? "",
    crc: esc.crc ?? "",
    email: esc.email ?? "",
    telefone: esc.telefone ?? "",
    cor_primaria: esc.cor_primaria,
  });
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [versaoLogo, setVersaoLogo] = useState(0);
  const arquivo = useRef<HTMLInputElement>(null);
  const muda = (c: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((x) => ({ ...x, [c]: e.target.value }));

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    setOk("");
    if (f.cnpj && !cnpjValido(f.cnpj)) return setErro("CNPJ do escritório inválido.");
    setSalvando(true);
    try {
      const s = await api<Sessao>("/escritorio", {
        method: "PATCH",
        json: {
          ...f,
          cnpj: f.cnpj ? soDigitos(f.cnpj) : null,
          email: f.email || null,
          telefone: f.telefone || null,
          crc: f.crc || null,
          contador_responsavel: f.contador_responsavel || null,
        },
      });
      atualizar(s);
      setOk("Dados salvos.");
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  async function enviarLogo(file: File) {
    setErro("");
    const dados = new FormData();
    dados.append("arquivo", file);
    try {
      atualizar(await api<Sessao>("/escritorio/logo", { method: "PUT", body: dados }));
      setVersaoLogo((v) => v + 1);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao enviar a logo");
    }
  }

  async function removerLogo() {
    atualizar(await api<Sessao>("/escritorio/logo", { method: "DELETE" }));
  }

  return (
    <>
      <Titulo sub="Estes dados aparecem nas propostas em PDF enviadas aos clientes.">Configurações do escritório</Titulo>
      {bemVindo && (
        <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          Conta criada! Envie a logo e escolha a cor do escritório para personalizar as propostas.
        </div>
      )}
      {!admin && (
        <div className="mb-4 rounded-lg border border-borda bg-superficie px-4 py-3 text-sm text-tinta-2">
          Apenas administradores alteram os dados e a marca do escritório.
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Cartao titulo="Identificação">
          <form onSubmit={salvar} className="flex flex-col gap-4">
            <fieldset disabled={!admin} className="flex flex-col gap-4 disabled:opacity-70">
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo rotulo="Nome do escritório" name="nome" required minLength={2} value={f.nome} onChange={muda("nome")} />
              <Campo rotulo="CNPJ" name="cnpj_escritorio" inputMode="numeric" value={f.cnpj} onChange={(e) => setF((x) => ({ ...x, cnpj: mascaraCnpj(e.target.value) }))} />
              <Campo rotulo="Contador responsável" name="contador_responsavel" value={f.contador_responsavel} onChange={muda("contador_responsavel")} />
              <Campo rotulo="CRC" name="crc" placeholder="SP-123456/O-7" value={f.crc} onChange={muda("crc")} />
              <Campo rotulo="E-mail" name="email" type="email" value={f.email} onChange={muda("email")} />
              <Campo rotulo="Telefone" name="telefone" value={f.telefone} onChange={muda("telefone")} />
            </div>
            <div>
              <Rotulo htmlFor="cor">Cor da marca</Rotulo>
              <div className="flex items-center gap-3">
                <input
                  id="cor"
                  type="color"
                  value={f.cor_primaria}
                  onChange={(e) => {
                    setF((x) => ({ ...x, cor_primaria: e.target.value }));
                    aplicarCorMarca(e.target.value);
                  }}
                  className="h-10 w-14 cursor-pointer rounded border border-borda bg-superficie"
                />
                <span className="num text-sm text-tinta-2">{f.cor_primaria.toUpperCase()}</span>
              </div>
            </div>
            </fieldset>
            <MensagemErro>{erro}</MensagemErro>
            {ok && <p className="text-sm text-emerald-700">{ok}</p>}
            {admin && (
              <div>
                <Botao type="submit" carregando={salvando}>Salvar</Botao>
              </div>
            )}
          </form>
        </Cartao>

        <Cartao titulo="Logo">
          <div className="flex flex-col items-start gap-3">
            <div className="grid h-28 w-full place-items-center rounded-lg border border-dashed border-borda bg-fundo">
              {esc.tem_logo ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={`/api/escritorio/logo?v=${versaoLogo}`} alt="Logo do escritório" className="max-h-24 max-w-[90%] object-contain" />
              ) : (
                <span className="text-sm text-tinta-2">Sem logo</span>
              )}
            </div>
            <p className="text-xs text-tinta-2">PNG ou JPG, até 512 KB. Fundo transparente fica melhor.</p>
            <input
              ref={arquivo}
              type="file"
              accept="image/png,image/jpeg"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && enviarLogo(e.target.files[0])}
            />
            {admin && (
              <div className="flex gap-2">
                <Botao variante="secundario" onClick={() => arquivo.current?.click()}>Enviar logo</Botao>
                {esc.tem_logo && <Botao variante="fantasma" onClick={removerLogo}>Remover</Botao>}
              </div>
            )}
          </div>
        </Cartao>
      </div>
      <div className="mt-6">
        <AlterarSenha />
      </div>
    </>
  );
}

export default function PaginaConfiguracoes() {
  return (
    <Suspense>
      <Configuracoes />
    </Suspense>
  );
}
