export default function LayoutPublico({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-[calc(100vh-var(--faixa))] lg:grid-cols-2">
      <div className="hidden flex-col justify-between bg-marca p-12 text-white lg:flex">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-tolaris.png" alt="Tolaris — Tecnologia Integrada" className="h-36 w-auto self-start" />
        <div>
          <h2 className="text-3xl font-semibold leading-tight">
            Diagnóstico tributário em minutos.
            <br />
            Proposta pronta para o cliente.
          </h2>
          <ul className="mt-6 space-y-2 text-white/85">
            <li>• Simples, Presumido e Real lado a lado, com memória de cálculo</li>
            <li>• Consulta de CNPJ e sugestão de anexo pelo CNAE</li>
            <li>• PDF com a marca do seu escritório</li>
          </ul>
        </div>
        <p className="text-xs text-white/60">Estimativas não substituem a análise do contador responsável.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
