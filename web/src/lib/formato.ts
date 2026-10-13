const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const moedaCurta = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

export const brl = (v: number | null | undefined) => (v == null ? "—" : moeda.format(v));
const decimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
/** Valor sem o símbolo (para tabelas largas cujo cabeçalho já diz "R$"). */
export const numero = (v: number) => decimal.format(v);
export const brlCurto = (v: number) => moedaCurta.format(v);

export const pct = (v: number | null | undefined, casas = 2) =>
  v == null
    ? "—"
    : new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: casas, maximumFractionDigits: casas }).format(v);

export const soDigitos = (v: string) => v.replace(/\D/g, "");

export function mascaraCnpj(v: string): string {
  const d = soDigitos(v).slice(0, 14);
  return d
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

export function cnpjValido(v: string): boolean {
  const d = soDigitos(v);
  if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
  const dv = (base: string, pesos: number[]) => {
    const resto = base.split("").reduce((s, n, i) => s + Number(n) * pesos[i], 0) % 11;
    return resto < 2 ? 0 : 11 - resto;
  };
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const d1 = dv(d.slice(0, 12), p1);
  const d2 = dv(d.slice(0, 12) + d1, [6, ...p1]);
  return d.endsWith(`${d1}${d2}`);
}

// A API devolve datas em UTC; sem "Z" o navegador interpretaria como horário local.
const comoUtc = (iso: string) => new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`);

export const data = (iso: string | null | undefined) =>
  iso ? comoUtc(iso).toLocaleDateString("pt-BR") : "—";

export const dataHora = (iso: string | null | undefined) =>
  iso ? comoUtc(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—";

const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
/** "2026-03" -> "mar/26" */
export const competenciaCurta = (c: string) => `${MESES_CURTOS[Number(c.slice(5, 7)) - 1]}/${c.slice(2, 4)}`;
