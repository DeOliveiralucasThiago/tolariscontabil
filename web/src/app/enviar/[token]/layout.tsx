import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Envio de notas fiscais",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function LayoutEnvio({ children }: { children: React.ReactNode }) {
  return children;
}
