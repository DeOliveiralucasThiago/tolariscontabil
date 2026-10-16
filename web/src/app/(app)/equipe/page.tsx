"use client";

import { useCallback, useEffect, useState } from "react";

import { useSessao } from "@/components/Sessao";
import { Botao, Campo, Cartao, Etiqueta, MensagemErro, Selecao, Titulo, classeCampo } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import { data } from "@/lib/formato";
import type { Convite, Membro } from "@/lib/tipos";

export default function Equipe() {
  const { sessao } = useSessao();
  const admin = sessao.usuario.papel === "admin";
  const [membros, setMembros] = useState<Membro[]>([]);
  const [convites, setConvites] = useState<Convite[]>([]);
  const [novo, setNovo] = useState({ email: "", nome: "", papel: "membro" });
  const [erro, setErro] = useState("");
  const [ok, setOk] = useState("");
  const [enviando, setEnviando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      const r = await api<{ membros: Membro[]; convites: Convite[] }>("/equipe");
      setMembros(r.membros);
      setConvites(r.convites);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha ao carregar a equipe");
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function acao(fn: () => Promise<unknown>, sucesso = "") {
    setErro("");
    setOk("");
    try {
      await fn();
      setOk(sucesso);
      await carregar();
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha na operação");
    }
  }

  async function convidar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    await acao(
      () => api("/equipe/convites", { method: "POST", json: { ...novo, nome: novo.nome || null } }),
      `Convite enviado para ${novo.email}.`,
    );
    setNovo({ email: "", nome: "", papel: "membro" });
    setEnviando(false);
  }

  return (
    <>
      <Titulo sub={admin ? "Convide colegas e defina quem administra o escritório." : "Pessoas com acesso ao escritório."}>
        Equipe
      </Titulo>
      <div className="flex flex-col gap-6">
        <MensagemErro>{erro}</MensagemErro>
        {ok && <p className="text-sm text-emerald-700">{ok}</p>}

        <Cartao titulo={`Membros (${membros.length})`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-borda text-left text-xs text-tinta-2">
                  <th className="py-2 font-medium">Nome</th>
                  <th className="py-2 font-medium">Papel</th>
                  <th className="py-2 font-medium">Situação</th>
                  <th className="py-2 font-medium">Desde</th>
                  {admin && <th className="py-2" />}
                </tr>
              </thead>
              <tbody>
                {membros.map((m) => {
                  const eu = m.id === sessao.usuario.id;
                  return (
                    <tr key={m.id} className="border-b border-borda/70">
                      <td className="py-2.5">
                        <div className="font-medium">{m.nome}{eu && <span className="text-tinta-2"> (você)</span>}</div>
                        <div className="text-xs text-tinta-2">{m.email}</div>
                      </td>
                      <td className="py-2.5">
                        {admin && !eu ? (
                          <select
                            aria-label={`Papel de ${m.nome}`}
                            className={`${classeCampo} h-9 w-36`}
                            value={m.papel}
                            onChange={(e) => acao(() => api(`/equipe/${m.id}`, { method: "PATCH", json: { papel: e.target.value } }))}
                          >
                            <option value="membro">Membro</option>
                            <option value="admin">Administrador</option>
                          </select>
                        ) : m.papel === "admin" ? "Administrador" : "Membro"}
                      </td>
                      <td className="py-2.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Etiqueta tom={m.ativo ? "ativo" : "inativo"}>{m.ativo ? "Ativo" : "Desativado"}</Etiqueta>
                          {m.totp_ativo && <Etiqueta tom="prospect">2 etapas</Etiqueta>}
                        </div>
                      </td>
                      <td className="num py-2.5 text-tinta-2">{data(m.criado_em)}</td>
                      {admin && (
                        <td className="space-x-2 py-2.5 text-right">
                          {!eu && m.totp_ativo && (
                            <Botao
                              variante="secundario"
                              className="h-8 px-3 text-xs"
                              onClick={() => {
                                if (confirm(`Remover a verificação em duas etapas de ${m.nome}? Use quando a pessoa perdeu o celular e os códigos de recuperação. As sessões abertas dela serão encerradas.`))
                                  acao(() => api(`/equipe/${m.id}/redefinir-2fa`, { method: "POST" }), `Verificação em duas etapas de ${m.nome} removida.`);
                              }}
                            >
                              Redefinir 2 etapas
                            </Botao>
                          )}
                          {!eu && (
                            <Botao
                              variante={m.ativo ? "perigo" : "secundario"}
                              className="h-8 px-3 text-xs"
                              onClick={() => acao(() => api(`/equipe/${m.id}`, { method: "PATCH", json: { ativo: !m.ativo } }))}
                            >
                              {m.ativo ? "Desativar" : "Reativar"}
                            </Botao>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Cartao>

        {admin && (
          <div className="grid gap-6 lg:grid-cols-2">
            <Cartao titulo="Convidar">
              <form onSubmit={convidar} className="flex flex-col gap-4">
                <Campo rotulo="E-mail" name="email_convite" type="email" required value={novo.email} onChange={(e) => setNovo((n) => ({ ...n, email: e.target.value }))} />
                <Campo rotulo="Nome (opcional)" name="nome_convite" value={novo.nome} onChange={(e) => setNovo((n) => ({ ...n, nome: e.target.value }))} />
                <Selecao rotulo="Papel" name="papel_convite" value={novo.papel} onChange={(e) => setNovo((n) => ({ ...n, papel: e.target.value }))}
                  ajuda="Administradores alteram os dados do escritório e gerenciam a equipe.">
                  <option value="membro">Membro</option>
                  <option value="admin">Administrador</option>
                </Selecao>
                <div><Botao type="submit" carregando={enviando}>Enviar convite</Botao></div>
              </form>
            </Cartao>
            <Cartao titulo={`Convites pendentes (${convites.length})`}>
              {convites.length === 0 ? (
                <p className="text-sm text-tinta-2">Nenhum convite pendente.</p>
              ) : (
                <ul className="divide-y divide-borda">
                  {convites.map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                      <div>
                        <div className="text-sm font-medium">{c.email}</div>
                        <div className="text-xs text-tinta-2">
                          {c.papel === "admin" ? "Administrador" : "Membro"} · expira em {data(c.expira_em)}
                        </div>
                      </div>
                      <Botao variante="fantasma" className="h-8 px-3 text-xs" onClick={() => acao(() => api(`/equipe/convites/${c.id}`, { method: "DELETE" }), "Convite cancelado.")}>
                        Cancelar
                      </Botao>
                    </li>
                  ))}
                </ul>
              )}
            </Cartao>
          </div>
        )}
      </div>
    </>
  );
}
