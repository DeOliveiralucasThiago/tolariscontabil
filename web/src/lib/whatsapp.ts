/** Número para o WhatsApp (só dígitos, com o 55 do Brasil), ou null se não parecer um telefone brasileiro. */
export function numeroWhatsapp(telefone: string | null | undefined): string | null {
  const d = (telefone ?? "").replace(/\D/g, "").replace(/^0+/, "");
  if (d.length === 10 || d.length === 11) return `55${d}`; // DDD + número
  if ((d.length === 12 || d.length === 13) && d.startsWith("55")) return d;
  return null;
}

/** Link que abre o WhatsApp com a mensagem pronta; sem número válido, o usuário escolhe o contato. */
export function linkWhatsapp(telefone: string | null | undefined, mensagem: string): string {
  const numero = numeroWhatsapp(telefone);
  return `https://wa.me/${numero ?? ""}?text=${encodeURIComponent(mensagem)}`;
}
