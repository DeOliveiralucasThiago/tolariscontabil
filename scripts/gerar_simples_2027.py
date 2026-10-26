"""Acrescenta a ``simples_nacional.json`` as vigências de 2027 a 2033 (CBS e IBS na partilha do DAS), sem acessar a rede.

Fonte: Resolução CGSN nº 190/2026, Anexos I a V da Resolução CGSN nº 140/2018 (portal de normas da Receita Federal). Converta cada
PDF com ``pdftotext -layout``. Os mesmos valores constam dos Anexos XVIII a XXIII da LC 123/2006 (LC 214/2025 e LC 227/2026).

Cada Anexo traz uma tabela de alíquotas nominais para 2027-2028 e outra para 2029 em diante, e uma tabela de partilha para
2027-2028, 2029, 2030, 2031, 2032 e 2033 em diante. O script confere que cada faixa soma 100% na partilha.

Uso:
    python scripts/gerar_simples_2027.py --anexo I=aI.txt --anexo II=aII.txt --anexo III=aIII.txt --anexo IV=aIV.txt --anexo V=aV.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

JSON = Path(__file__).resolve().parent.parent / "src" / "tolaris_motor" / "tabelas" / "simples_nacional.json"
ANOS = (2027, 2029, 2030, 2031, 2032, 2033)
TETO_ISS = {2027: "0.05", 2029: "0.045", 2030: "0.04", 2031: "0.035", 2032: "0.03", 2033: "0"}
"""Teto do ISS efetivo no DAS: 5% em 2027-28 e cai 0,5 ponto por ano até 3% em 2032; em 2033 o ISS sai do DAS."""
TRIBUTOS = {"IRPJ", "CSLL", "CBS", "CPP", "IPI", "ICMS", "ISS", "IBS"}
FONTE = (
    "Res. CGSN 190/2026 (Anexos I a V da Res. CGSN 140/2018, vigência a partir de 01/01/2027); mesmos valores dos Anexos XVIII a XXIII "
    "da LC 123/2006 (LC 214/2025, LC 227/2026). CBS e IBS substituem PIS, Cofins, ICMS e ISS na partilha, em transição até 2033."
)


def numero(texto: str) -> str:
    """``'1.800.000,01'`` → ``'1800000.01'``; traço vira zero."""
    t = texto.strip().replace("(*)", "").strip()
    if t in {"-", "_", "–", ""}:
        return "0"
    return t.replace(".", "").replace(",", ".")


def percentual(texto: str) -> str:
    return str(Decimal(numero(texto.rstrip("%"))) / 100)


def ler_anexo(texto: str) -> tuple[dict[int, list[dict]], dict[int, list[dict[str, str]]]]:
    """(nominais por ano de início, partilhas por ano). Cada lista tem as 6 faixas na ordem."""
    inicio = 0
    nominais: dict[int, list[dict]] = {}
    partilhas: dict[int, list[dict[str, str]]] = {}
    colunas: list[str] = []
    for linha in texto.splitlines():
        if m := re.search(r"Vig[êe]ncia:\s*1º/1/(\d{4})", linha):
            inicio = int(m.group(1))
            continue
        palavras = re.findall(r"[A-Z]{3,5}", linha.replace("(*)", ""))
        if palavras and set(palavras) <= TRIBUTOS and len(palavras) >= 4 and not re.match(r"\s*\d", linha):
            colunas = palavras
            continue
        m = re.match(r"\s*([1-6])ª Faixa\s+(Até|De)\s+(.*)$", linha)
        if m and inicio:
            partes = re.findall(r"[\d.]+,\d{2}|-|_", m.group(3))
            # "Até 180.000,00 4,00% -" ou "De 180.000,01 a 360.000,00 7,30% 5.940,00"
            ate, aliquota, deduzir = partes[-3], partes[-2], partes[-1]
            nominais.setdefault(inicio, []).append(
                {"ate": numero(ate), "aliquota": percentual(aliquota), "deduzir": numero(deduzir)}
            )
            continue
        m = re.match(r"\s*([1-6])ª Faixa\s+((?:[\d.]+,\d{2}%(?:\s*\(\*\))?\s*|-\s*)+)$", linha)
        if m and colunas and inicio:
            valores = re.findall(r"([\d.]+,\d{2}%|-)", m.group(2))
            if len(valores) != len(colunas):
                raise SystemExit(f"Linha de partilha com {len(valores)} valores para as colunas {colunas}: {linha!r}")
            partilhas.setdefault(inicio, []).append(
                {c.lower(): percentual(v) for c, v in zip(colunas, valores) if v != "-"}
            )
    return nominais, partilhas


def montar(anexos: dict[str, tuple[dict, dict]], base: dict) -> list[dict]:
    vigencias = []
    for ano in ANOS:
        vig = {
            "inicio": f"{ano}-01-01",
            "limite_receita_anual": base["limite_receita_anual"],
            "sublimite_icms_iss": base["sublimite_icms_iss"],
            "fator_r_minimo": base["fator_r_minimo"],
            "iss_efetivo_maximo": TETO_ISS[ano],
            "fonte": FONTE,
            "anexos": {},
        }
        for nome, (nominais, partilhas) in anexos.items():
            grupo = 2027 if ano == 2027 else 2029
            nominal, partilha = nominais[grupo], partilhas[ano]
            if len(nominal) != 6 or len(partilha) != 6:
                raise SystemExit(f"Anexo {nome}, {ano}: esperava 6 faixas, achei {len(nominal)} nominais e {len(partilha)} de partilha")
            faixas = []
            for n, p in zip(nominal, partilha):
                soma = sum(Decimal(v) for v in p.values())
                if abs(soma - 1) > Decimal("0.0002"):
                    raise SystemExit(f"Anexo {nome}, {ano}: partilha soma {soma}, não 100%: {p}")
                faixas.append({**n, "partilha": p})
            vig["anexos"][nome] = {"descricao": base["anexos"][nome]["descricao"], "faixas": faixas}
        vigencias.append(vig)
    return vigencias


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anexo", action="append", required=True, metavar="NOME=ARQUIVO", help="ex.: III=aIII.txt (repita para I a V)")
    ap.add_argument("--json", type=Path, default=JSON)
    args = ap.parse_args()

    dados = json.loads(args.json.read_text(encoding="utf-8"))
    base = dados["vigencias"][0]
    anexos = {}
    for item in args.anexo:
        nome, _, arquivo = item.partition("=")
        anexos[nome] = ler_anexo(Path(arquivo).read_text(encoding="utf-8"))
    if sorted(anexos) != ["I", "II", "III", "IV", "V"]:
        sys.exit("Informe os cinco Anexos: I, II, III, IV e V")

    dados["vigencias"] = [v for v in dados["vigencias"] if int(v["inicio"][:4]) < 2027] + montar(anexos, base)
    dados["fonte"] = base_fonte(dados["fonte"])
    args.json.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(ANOS)} vigências de 2027 em diante gravadas em {args.json}")


def base_fonte(atual: str) -> str:
    marca = " | Vigências de 2027 em diante: "
    atual = atual.split(marca)[0]
    return atual + marca + "Res. CGSN 190/2026 (CBS e IBS na partilha do DAS)"


if __name__ == "__main__":
    main()
