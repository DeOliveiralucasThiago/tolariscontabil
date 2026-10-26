"""Gera ``src/tolaris_motor/tabelas/cnae.json`` a partir dos arquivos das fontes (sem acessar a rede).

Fontes (baixe de novo para atualizar):
- IBGE/Concla: planilha "CNAE_Subclasses_2_3_Estrutura_Detalhada.xlsx" (todas as seções, divisões e subclasses, com nomes);
- Receita Federal, Resolução CGSN 140/2018, Anexos VI (CNAEs impeditivos) e VII (CNAEs ambíguos): PDFs do portal de normas,
  convertidos para texto com ``pdftotext -layout``;
- Contabilizei, página "Tabela CNAE": Anexo e fator R de cada CNAE que a empresa atende. É uma fonte comercial e uma
  interpretação da lei (a Resolução define o Anexo pela descrição da atividade, não por CNAE), por isso fica marcada à parte.

Uso:
    python scripts/gerar_tabela_cnae.py --ibge cnae.xlsx --anexo6 a6.txt --anexo7 a7.txt --contabilizei cb.html \
        --atualizado-em 2026-10-26
"""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

SAIDA = Path(__file__).resolve().parent.parent / "src" / "tolaris_motor" / "tabelas" / "cnae.json"


def so_digitos(codigo: str) -> str:
    return re.sub(r"\D", "", codigo)


def ler_ibge(caminho: Path) -> tuple[dict[str, str], dict[str, dict[str, str]], dict[str, str]]:
    ws = openpyxl.load_workbook(caminho, read_only=True)["Estrutura Det. CNAE Subclass2.3"]
    secoes: dict[str, str] = {}
    divisoes: dict[str, dict[str, str]] = {}
    subclasses: dict[str, str] = {}
    secao = ""
    classe_sem_subclasse: tuple[str, str] | None = None  # a CNAE 9900-8/00 aparece só como classe na planilha
    for linha in ws.iter_rows(min_row=5, values_only=True):
        sec, div, _grupo, classe, sub, nome = linha[:6]
        if classe_sem_subclasse and not sub:
            subclasses[so_digitos(classe_sem_subclasse[0]) + "00"] = classe_sem_subclasse[1]
        classe_sem_subclasse = (str(classe), str(nome).strip()) if classe else None
        if sec:
            secao = str(sec).strip()
            secoes[secao] = str(nome).strip()
        elif div:
            divisoes[str(div).strip()] = {"nome": str(nome).strip(), "secao": secao}
        elif sub:
            subclasses[so_digitos(str(sub))] = str(nome).strip()
    if classe_sem_subclasse:
        subclasses[so_digitos(classe_sem_subclasse[0]) + "00"] = classe_sem_subclasse[1]
    return secoes, divisoes, subclasses


def ler_codigos_do_anexo(caminho: Path) -> list[str]:
    return sorted({so_digitos(m.group(1)) for m in re.finditer(r"^\s*(\d{4}-\d/\d{2})\s", caminho.read_text(encoding="utf-8"), re.M)})


def ler_contabilizei(caminho: Path) -> dict[str, dict]:
    pagina = caminho.read_text(encoding="utf-8", errors="ignore")
    linhas = re.findall(
        r'<tr><td><a[^>]*>(\d{7})</a></td><td class="desc"><a[^>]*>.*?</a></td><td>(.*?)</td><td>(.*?)</td><td>.*?</td><td>.*?</td></tr>',
        pagina,
        re.S,
    )
    achados: dict[str, dict] = defaultdict(lambda: {"anexos": set(), "fator_r": False})
    for codigo, anexo, fator_r in linhas:
        achados[codigo]["anexos"].add(html.unescape(anexo).strip())
        achados[codigo]["fator_r"] = achados[codigo]["fator_r"] or fator_r.strip().lower() == "sim"
    return {c: {"anexos": sorted(v["anexos"], key=["I", "II", "III", "IV", "V"].index), "fator_r": v["fator_r"]} for c, v in sorted(achados.items())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ibge", type=Path, required=True)
    ap.add_argument("--anexo6", type=Path, required=True)
    ap.add_argument("--anexo7", type=Path, required=True)
    ap.add_argument("--contabilizei", type=Path, required=True)
    ap.add_argument("--atualizado-em", required=True, help="AAAA-MM-DD da coleta das fontes")
    ap.add_argument("--saida", type=Path, default=SAIDA)
    args = ap.parse_args()

    secoes, divisoes, subclasses = ler_ibge(args.ibge)
    vedacao = {c: "impeditivo" for c in ler_codigos_do_anexo(args.anexo6)}
    vedacao.update({c: "ambiguo" for c in ler_codigos_do_anexo(args.anexo7)})
    anexos = ler_contabilizei(args.contabilizei)

    for nome, codigos in (("vedação (Anexos VI e VII)", vedacao), ("Contabilizei", anexos)):
        fora = sorted(c for c in codigos if c not in subclasses)
        if fora:
            print(f"Aviso: {len(fora)} código(s) de {nome} que não estão no CNAE 2.3 do IBGE: {', '.join(fora)}")

    dados = {
        "atualizado_em": args.atualizado_em,
        "fontes": {
            "subclasses": "IBGE/Concla, CNAE-Subclasses 2.3, estrutura detalhada (https://concla.ibge.gov.br)",
            "vedacao": "Receita Federal, Resolução CGSN nº 140/2018, Anexos VI (impeditivos) e VII (ambíguos), art. 8º, §§ 1º e 2º",
            "anexos": "Contabilizei, Tabela CNAE (fonte comercial; a lei define o Anexo pela descrição da atividade, não por CNAE)",
        },
        "secoes": secoes,
        "divisoes": divisoes,
        "subclasses": subclasses,
        "vedacao": vedacao,
        "anexos": anexos,
    }
    args.saida.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(
        f"{len(subclasses)} subclasses, {len(divisoes)} divisões, {len(vedacao)} vedações "
        f"({sum(v == 'impeditivo' for v in vedacao.values())} impeditivos), {len(anexos)} CNAEs com Anexo → {args.saida}"
    )


if __name__ == "__main__":
    main()
