import { connection } from "next/server";

/**
 * Barra no topo avisando que o sistema está em ambiente de testes. Liga com TOLARIS_AMBIENTE_TESTE=true no servidor
 * do site (lido a cada acesso, sem recompilar). Fica no azul do Tolaris, e não na cor do escritório.
 */
export async function FaixaDeTeste() {
  await connection();
  if (process.env.TOLARIS_AMBIENTE_TESTE !== "true") return null;
  return (
    <div
      role="note"
      className="faixa-de-teste sticky top-0 z-50 h-9 overflow-hidden whitespace-nowrap bg-[#1f3a5f] px-3 text-center text-xs leading-9 text-white"
    >
      <strong className="font-semibold">Ambiente de testes</strong>
      <span className="sm:hidden"> · dados fictícios</span>
      <span className="hidden sm:inline">: use apenas para avaliação, com dados fictícios. Seus dados podem ser apagados a qualquer momento.</span>
    </div>
  );
}
