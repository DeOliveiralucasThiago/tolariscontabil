import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Suspense } from "react";

import { FaixaDeTeste } from "@/components/FaixaDeTeste";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: { default: "Tolaris Contábil", template: "%s · Tolaris" },
  description: "Planejamento tributário, prospecção e Reforma Tributária para escritórios contábeis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className={`${inter.variable} font-sans antialiased`}>
        <Suspense fallback={null}>
          <FaixaDeTeste />
        </Suspense>
        {children}
      </body>
    </html>
  );
}
