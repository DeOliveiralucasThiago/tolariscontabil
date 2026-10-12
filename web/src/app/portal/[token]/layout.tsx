import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Portal do cliente",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function LayoutPortal({ children }: { children: React.ReactNode }) {
  return children;
}
