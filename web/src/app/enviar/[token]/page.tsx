"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { aplicarCorMarca } from "@/components/Sessao";
import { Botao, MensagemErro } from "@/components/ui";
import { api, ErroApi } from "@/lib/api";
import type { ResultadoImportacao } from "@/lib/tipos";

interface Caixa {
  escritorio: { nome: string; cor_primaria: string; tem_logo: boolean; email: string | null; telefone: string | null };
  cliente: string;
  limite_mb: number;
}

/** Página aberta pelo cliente (ou pelo sistema emissor) para enviar XML de notas sem login. */
export default function PaginaEnvioDeNotas() {
  const { token } = useParams<{ token: string }>();
  const [caixa, setCaixa] = useState<Caixa | null>(null);
  const [erroPagina, setErroPagina] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const [resultados, setResultados] = useState<ResultadoImportacao[]>([]);
  const entrada = useRef<HTMLInputElement>(null);
  const base = `/api/caixa/${encodeURIComponent(token)}`;

  useEffect(() => {
    api<Caixa>(`/caixa/${encodeURIComponent(token)}`)
      .then((c) => {
        aplicarCorMarca(c.escritorio.cor_primaria);
        setCaixa(c);
      })
      .catch((e) =>
        setErroPagina(
          e instanceof ErroApi && e.status === 404
            ? "Este link não está mais ativo. Peça um novo ao seu escritório contábil."
            : "Não foi possível abrir a página de envio.",
        ),
      );
  }, [token]);

  async function enviar(arquivos: FileList | File[]) {
    if (!arquivos.length) return;
    setErro("");
    setEnviando(true);
    const dados = new FormData();
    Array.from(arquivos).forEach((f) => dados.append("arquivos", f));
    try {
      const r = await api<ResultadoImportacao>(`/caixa/${encodeURIComponent(token)}/arquivos`, { method: "POST", body: dados });
      setResultados((x) => [r, ...x]);
    } catch (e) {
      setErro(e instanceof ErroApi ? e.message : "Falha no envio. Tente novamente.");
    } finally {
      setEnviando(false);
      if (entrada.current) entrada.current.value = "";
    }
  }

  if (!caixa) {
    return <div className="grid min-h-[calc(100vh-var(--faixa))] place-items-center p-6 text-center text-sm text-tinta-2">{erroPagina || "Carregando…"}</div>;
  }
  const esc = caixa.escritorio;
  const total = resultados.reduce((s, r) => s + r.importados, 0);

  return (
    <div className="min-h-[calc(100vh-var(--faixa))]">
      <header className="bg-marca text-white">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-8">
          <div className="flex items-center gap-3">
            {esc.tem_logo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`${base}/logo`} alt="" className="h-11 max-w-40 rounded bg-white object-contain p-1" />
            )}
            <div>
              <div className="text-lg font-semibold">{esc.nome}</div>
              <div className="text-xs text-white/80">Envio de notas fiscais</div>
            </div>
          </div>
          <div className="text-right text-xs text-white/85">
            {esc.email && <div>{esc.email}</div>}
            {esc.telefone && <div>{esc.telefone}</div>}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-8 sm:py-8">
        <h1 className="text-2xl font-semibold tracking-tight">{caixa.cliente}</h1>
        <p className="mt-1 text-sm text-tinta-2">
          Envie os arquivos XML das notas fiscais de venda e de compra. Pode mandar vários de uma vez ou um único arquivo .zip com
          todos. Notas já enviadas antes são ignoradas.
        </p>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setArrastando(true);
          }}
          onDragLeave={() => setArrastando(false)}
          onDrop={(e) => {
            e.preventDefault();
            setArrastando(false);
            enviar(e.dataTransfer.files);
          }}
          className={`mt-6 flex flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center ${
            arrastando ? "border-marca bg-superficie" : "border-borda bg-superficie"
          }`}
        >
          <p className="text-sm text-tinta-2">Arraste os arquivos para cá ou</p>
          <input
            ref={entrada}
            type="file"
            multiple
            accept=".xml,.zip,.txt"
            aria-label="Arquivos de notas"
            className="hidden"
            onChange={(e) => e.target.files && enviar(e.target.files)}
          />
          <Botao onClick={() => entrada.current?.click()} carregando={enviando}>
            Escolher arquivos
          </Botao>
          <p className="text-xs text-tinta-2">XML de NF-e/NFC-e, .zip ou o arquivo .txt do SPED Fiscal · até {caixa.limite_mb} MB por envio</p>
        </div>

        <div className="mt-4">
          <MensagemErro>{erro}</MensagemErro>
        </div>

        {resultados.length > 0 && (
          <section className="mt-4 flex flex-col gap-3" aria-label="Resultado dos envios" aria-live="polite">
            <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              ✓ {total} {total === 1 ? "nota recebida" : "notas recebidas"} nesta visita. Obrigado!
            </p>
            {resultados.map((r, i) => (
              <div key={i} className="rounded-lg border border-borda bg-superficie p-3 text-sm">
                <div className="font-medium">
                  {r.importados} recebidas · {r.duplicados} já existiam · {r.total_ignorados} ignoradas
                </div>
                {r.ignorados.length > 0 && (
                  <ul className="mt-2 max-h-40 overflow-auto text-xs text-tinta-2">
                    {r.ignorados.map((x, n) => (
                      <li key={n}>
                        <span className="font-medium text-tinta">{x.arquivo}</span>: {x.motivo}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </section>
        )}

        <p className="mt-10 text-center text-xs text-tinta-2">Seus arquivos são enviados com segurança ao escritório {esc.nome}. · Tolaris Contábil</p>
      </main>
    </div>
  );
}
