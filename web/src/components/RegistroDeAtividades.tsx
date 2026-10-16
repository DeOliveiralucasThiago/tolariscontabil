"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ErroApi } from "@/lib/api";
import { dataHora } from "@/lib/formato";
import type { PaginaAuditoria } from "@/lib/tipos";

import { Botao, Cartao, MensagemErro, Selecao, classeCampo } from "./ui";

const POR_PAGINA = 20;

function resumo(detalhe: Record<string, unknown> | null): string {
  if (!detalhe) return "";
  return Object.entries(detalhe).map(([k, v]) => `${k.replaceAll("_", " ")}: ${String(v)}`).join(" · ");
}

/** Quem fez o quê no escritório: filtros, paginação e exportação (só administradores). */
export function RegistroDeAtividades() {
  const [pagina, setPagina] = useState<PaginaAuditoria | null>(null);
  const [acao, setAcao] = useState("");
  const [desde, setDesde] = useState("");
  const [ate, setAte] = useState("");
  const [deslocamento, setDeslocamento] = useState(0);
  const [erro, setErro] = useState("");

  const filtros = useCallback(() => {
    const p = new URLSearchParams();
    if (acao) p.set("acao", acao);
    if (desde) p.set("desde", desde);
    if (ate) p.set("ate", ate);
    return p;
  }, [acao, desde, ate]);

  useEffect(() => {
    const p = filtros();
    p.set("limite", String(POR_PAGINA));
    p.set("deslocamento", String(deslocamento));
    api<PaginaAuditoria>(`/escritorio/auditoria?${p}`)
      .then((r) => {
        setPagina(r);
        setErro("");
      })
      .catch((e) => setErro(e instanceof ErroApi ? e.message : "Falha ao carregar o registro"));
  }, [filtros, deslocamento]);

  const total = pagina?.total ?? 0;
  return (
    <Cartao titulo="Registro de atividades" acoes={<a className="text-sm font-medium text-marca hover:underline" href={`/api/escritorio/auditoria/exportar.csv?${filtros()}`}>Exportar CSV</a>}>
      <div className="flex flex-col gap-3 text-sm">
        <p className="text-tinta-2">
          Entradas no sistema, mudanças na equipe, importações, exportações e exclusões de dados. Guardado por {pagina?.retencao_meses ?? 24} meses. Não
          inclui senhas nem o conteúdo das notas.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <Selecao rotulo="Ação" name="filtro_acao" value={acao} onChange={(e) => { setAcao(e.target.value); setDeslocamento(0); }} className="min-w-56">
            <option value="">Todas</option>
            {pagina?.acoes.map((a) => <option key={a.codigo} value={a.codigo}>{a.rotulo}</option>)}
          </Selecao>
          <label className="text-xs text-tinta-2">De<input type="date" className={`${classeCampo} mt-1 block`} value={desde} onChange={(e) => { setDesde(e.target.value); setDeslocamento(0); }} aria-label="De" /></label>
          <label className="text-xs text-tinta-2">Até<input type="date" className={`${classeCampo} mt-1 block`} value={ate} onChange={(e) => { setAte(e.target.value); setDeslocamento(0); }} aria-label="Até" /></label>
        </div>
        <MensagemErro>{erro}</MensagemErro>
        {pagina && pagina.itens.length === 0 && <p className="text-tinta-2">Nenhum registro com esses filtros.</p>}
        {pagina && pagina.itens.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead>
                <tr className="border-b border-borda text-left text-xs text-tinta-2">
                  <th className="py-2 pr-2 font-medium">Quando</th>
                  <th className="px-2 py-2 font-medium">Quem</th>
                  <th className="px-2 py-2 font-medium">O que</th>
                  <th className="px-2 py-2 font-medium">IP</th>
                </tr>
              </thead>
              <tbody>
                {pagina.itens.map((i) => (
                  <tr key={i.id} className="border-b border-borda/70 align-top">
                    <td className="num whitespace-nowrap py-1.5 pr-2">{dataHora(i.quando)}</td>
                    <td className="px-2 py-1.5">{i.usuario ?? <span className="text-tinta-2">Cliente (link)</span>}</td>
                    <td className="px-2 py-1.5">
                      {i.rotulo}
                      {i.entidade && <span className="text-tinta-2"> · {i.entidade} #{i.entidade_id}</span>}
                      {i.detalhe && <div className="text-xs text-tinta-2">{resumo(i.detalhe)}</div>}
                    </td>
                    <td className="num px-2 py-1.5 text-tinta-2">{i.ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > POR_PAGINA && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-tinta-2">{deslocamento + 1}–{Math.min(deslocamento + POR_PAGINA, total)} de {total}</span>
            <div className="flex gap-2">
              <Botao variante="secundario" disabled={deslocamento === 0} onClick={() => setDeslocamento((d) => Math.max(0, d - POR_PAGINA))}>Anteriores</Botao>
              <Botao variante="secundario" disabled={deslocamento + POR_PAGINA >= total} onClick={() => setDeslocamento((d) => d + POR_PAGINA)}>Próximos</Botao>
            </div>
          </div>
        )}
      </div>
    </Cartao>
  );
}
