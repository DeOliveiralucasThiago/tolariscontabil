// Cliente HTTP da API. As chamadas vão para /api (mesma origem; o Next faz o proxy),
// e a sessão segue no cookie httpOnly — o JavaScript nunca vê o token.

export class ErroApi extends Error {
  constructor(
    public status: number,
    mensagem: string,
  ) {
    super(mensagem);
  }
}

function mensagemDeErro(status: number, corpo: unknown): string {
  const detalhe = (corpo as { detail?: unknown } | null)?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    // Erros de validação do FastAPI: [{loc: [...], msg: "..."}]
    return detalhe
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const campo = d.loc?.filter((p) => p !== "body").join(".");
        const msg = (d.msg ?? "inválido").replace(/^Value error, /, "");
        return campo ? `${campo}: ${msg}` : msg;
      })
      .join("; ");
  }
  if (status >= 500) return "Erro no servidor. Tente novamente em instantes.";
  return `Erro ${status}`;
}

export async function api<T>(caminho: string, opcoes: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...resto } = opcoes;
  const resp = await fetch(`/api${caminho}`, {
    credentials: "same-origin",
    ...resto,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : resto.body,
  });
  if (resp.status === 204) return undefined as T;
  const corpo = resp.headers.get("content-type")?.includes("application/json") ? await resp.json() : null;
  if (!resp.ok) throw new ErroApi(resp.status, mensagemDeErro(resp.status, corpo));
  return corpo as T;
}

export const urlProposta = (simulacaoId: number) => `/api/simulacoes/${simulacaoId}/proposta.pdf`;
