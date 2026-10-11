import { ProvedorSessao } from "@/components/Sessao";
import { Shell } from "@/components/Shell";

export default function LayoutApp({ children }: { children: React.ReactNode }) {
  return (
    <ProvedorSessao>
      <Shell>{children}</Shell>
    </ProvedorSessao>
  );
}
