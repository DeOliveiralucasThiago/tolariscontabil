"use client";

import { useRouter } from "next/navigation";

import { FormCliente } from "@/components/FormCliente";
import { Cartao, Titulo } from "@/components/ui";
import { api } from "@/lib/api";
import type { Cliente } from "@/lib/tipos";

export default function NovoCliente() {
  const router = useRouter();
  return (
    <>
      <Titulo sub="Busque o CNPJ para preencher os dados da Receita.">Novo cliente</Titulo>
      <Cartao>
        <FormCliente
          textoBotao="Cadastrar cliente"
          onSalvar={async (dados) => {
            const c = await api<Cliente>("/clientes", { method: "POST", json: dados });
            router.push(`/clientes/${c.id}`);
          }}
        />
      </Cartao>
    </>
  );
}
