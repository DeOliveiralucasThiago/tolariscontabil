"""Leitura de documentos fiscais: NF-e/NFC-e (XML) e SPED Fiscal (EFD ICMS/IPI, registros 0000, 0150 e C100).

Tudo é convertido em ``DocLido`` com valores em centavos e classificado como saída ou
entrada do ponto de vista do cliente (pelo CNPJ). Arquivos ZIP são abertos com limites
de quantidade e tamanho (proteção contra "zip bomb"); XML é lido com defusedxml (sem XXE).
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

MAX_ARQUIVOS_ZIP = 5000
MAX_DESCOMPACTADO = 300 * 1024 * 1024
MAX_POR_ARQUIVO = 20 * 1024 * 1024
STATUS_AUTORIZADA = {"100", "150"}
SITUACOES_SPED_IGNORADAS = {"02": "cancelado", "03": "cancelado", "04": "denegado", "05": "inutilizado"}


class ArquivoInvalido(Exception):
    pass


@dataclass
class DocLido:
    origem: str
    chave: str
    tipo: str
    modelo: str | None
    data: date
    participante_cnpj: str | None
    valor: int
    icms: int = 0
    ipi: int = 0
    pis: int = 0
    cofins: int = 0

    @property
    def competencia(self) -> str:
        return f"{self.data.year:04d}-{self.data.month:02d}"


@dataclass
class ResultadoLeitura:
    documentos: list[DocLido] = field(default_factory=list)
    ignorados: list[tuple[str, str]] = field(default_factory=list)


def centavos(valor: str | None) -> int:
    if not valor:
        return 0
    try:
        return int((Decimal(valor.strip().replace(",", ".")) * 100).quantize(Decimal(1)))
    except InvalidOperation:
        raise ArquivoInvalido(f"Valor inválido: {valor[:20]}") from None


# --- NF-e ------------------------------------------------------------------------------
def _texto(no: Element | None, caminho: str) -> str | None:
    if no is None:
        return None
    alvo = no.find(caminho)
    return alvo.text.strip() if alvo is not None and alvo.text else None


def ler_nfe(conteudo: bytes, cnpj_cliente: str) -> DocLido:
    try:
        raiz = ET.fromstring(conteudo)
    except (ET.ParseError, DefusedXmlException) as erro:
        raise ArquivoInvalido(f"XML inválido ou inseguro ({type(erro).__name__})") from None
    inf = raiz if raiz.tag.endswith("infNFe") else raiz.find(".//{*}infNFe")
    if inf is None:
        raise ArquivoInvalido("Não é NF-e/NFC-e (NFS-e ainda não é suportada)")
    status = _texto(raiz, ".//{*}protNFe/{*}infProt/{*}cStat")
    if status is not None and status not in STATUS_AUTORIZADA:
        raise ArquivoInvalido(f"Nota não autorizada (status {status})")

    chave = (_texto(raiz, ".//{*}protNFe/{*}infProt/{*}chNFe") or (inf.get("Id") or "").removeprefix("NFe"))
    if len(chave) != 44 or not chave.isdigit():
        raise ArquivoInvalido("Chave de acesso ausente ou inválida")
    ide = inf.find("{*}ide")
    emitente = _texto(inf, "{*}emit/{*}CNPJ")
    destinatario = _texto(inf, "{*}dest/{*}CNPJ")
    tp_nf = _texto(ide, "{*}tpNF")
    emissao = _texto(ide, "{*}dhEmi") or _texto(ide, "{*}dEmi")
    if not emissao:
        raise ArquivoInvalido("Data de emissão ausente")
    try:
        data_doc = datetime.fromisoformat(emissao).date() if "T" in emissao else date.fromisoformat(emissao[:10])
    except ValueError:
        raise ArquivoInvalido(f"Data de emissão inválida: {emissao[:30]}") from None

    if emitente == cnpj_cliente:
        tipo = "saida" if tp_nf == "1" else "entrada"
        participante = destinatario
    elif destinatario == cnpj_cliente:
        tipo, participante = "entrada", emitente
    else:
        raise ArquivoInvalido("A nota não tem o CNPJ do cliente como emitente nem destinatário")

    tot = inf.find("{*}total/{*}ICMSTot")
    return DocLido(
        origem="nfe",
        chave=chave,
        tipo=tipo,
        modelo=_texto(ide, "{*}mod"),
        data=data_doc,
        participante_cnpj=participante,
        valor=centavos(_texto(tot, "{*}vNF")),
        icms=centavos(_texto(tot, "{*}vICMS")),
        ipi=centavos(_texto(tot, "{*}vIPI")),
        pis=centavos(_texto(tot, "{*}vPIS")),
        cofins=centavos(_texto(tot, "{*}vCOFINS")),
    )


# --- SPED Fiscal -------------------------------------------------------------------------
def _data_sped(valor: str) -> date:
    try:
        return date(int(valor[4:8]), int(valor[2:4]), int(valor[0:2]))
    except (ValueError, IndexError):
        raise ArquivoInvalido(f"Data inválida no SPED: {valor[:10]}") from None


def ler_sped(conteudo: bytes, cnpj_cliente: str, nome: str) -> ResultadoLeitura:
    texto = conteudo.decode("latin-1")
    res = ResultadoLeitura()
    participantes: dict[str, str] = {}
    cnpj_arquivo = None
    for numero, linha in enumerate(texto.splitlines(), start=1):
        if not linha.startswith("|"):
            continue
        c = linha.split("|")
        registro = c[1] if len(c) > 1 else ""
        if registro == "0000":
            if len(c) < 8:
                raise ArquivoInvalido("Registro 0000 incompleto")
            cnpj_arquivo = c[7]
            if cnpj_arquivo != cnpj_cliente:
                raise ArquivoInvalido("O SPED é de outro CNPJ")
        elif registro == "0150" and len(c) > 5:
            participantes[c[2]] = c[5]
        elif registro == "C100":
            if cnpj_arquivo is None:
                raise ArquivoInvalido("Arquivo sem registro 0000 (não parece SPED Fiscal)")
            if len(c) < 28:
                res.ignorados.append((f"{nome}:{numero}", "Registro C100 incompleto"))
                continue
            situacao = c[6]
            if situacao in SITUACOES_SPED_IGNORADAS:
                continue  # documento sem efeito fiscal
            ind_oper, ind_emit, cod_part, modelo, serie, num, chave = c[2], c[3], c[4], c[5], c[7], c[8], c[9]
            data_doc = _data_sped(c[10])
            if not (len(chave) == 44 and chave.isdigit()):
                chave = f"sped:{modelo}:{serie}:{num}:{ind_emit}:{cod_part}:{c[10]}"[:80]
            res.documentos.append(
                DocLido(
                    origem="sped",
                    chave=chave,
                    tipo="saida" if ind_oper == "1" else "entrada",
                    modelo=modelo or None,
                    data=data_doc,
                    participante_cnpj=participantes.get(cod_part) or None,
                    valor=centavos(c[12]),
                    icms=centavos(c[22]),
                    ipi=centavos(c[25]),
                    pis=centavos(c[26]),
                    cofins=centavos(c[27]),
                )
            )
    if cnpj_arquivo is None:
        raise ArquivoInvalido("Arquivo sem registro 0000 (não parece SPED Fiscal)")
    return res


# --- Entrada: arquivos soltos e ZIP --------------------------------------------------------------------
def _ler_um(nome: str, conteudo: bytes, cnpj_cliente: str, res: ResultadoLeitura) -> None:
    minusculo = nome.lower()
    try:
        if minusculo.endswith(".xml"):
            res.documentos.append(ler_nfe(conteudo, cnpj_cliente))
        elif minusculo.endswith(".txt"):
            lido = ler_sped(conteudo, cnpj_cliente, nome)
            res.documentos.extend(lido.documentos)
            res.ignorados.extend(lido.ignorados)
        else:
            res.ignorados.append((nome, "Formato não suportado (envie .xml, .txt do SPED ou .zip)"))
    except ArquivoInvalido as erro:
        res.ignorados.append((nome, str(erro)))


def ler_arquivos(arquivos: list[tuple[str, bytes]], cnpj_cliente: str) -> ResultadoLeitura:
    res = ResultadoLeitura()
    for nome, conteudo in arquivos:
        if not nome.lower().endswith(".zip"):
            _ler_um(nome, conteudo, cnpj_cliente, res)
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
                membros = [m for m in zf.infolist() if not m.is_dir()]
                if len(membros) > MAX_ARQUIVOS_ZIP:
                    res.ignorados.append((nome, f"ZIP com mais de {MAX_ARQUIVOS_ZIP} arquivos"))
                    continue
                total = 0
                for m in membros:
                    if m.file_size > MAX_POR_ARQUIVO:
                        res.ignorados.append((f"{nome}/{m.filename}", "Arquivo grande demais"))
                        continue
                    total += m.file_size
                    if total > MAX_DESCOMPACTADO:
                        res.ignorados.append((nome, "Conteúdo descompactado grande demais; divida o ZIP"))
                        break
                    if m.filename.lower().endswith(".zip"):
                        res.ignorados.append((f"{nome}/{m.filename}", "ZIP dentro de ZIP não é suportado"))
                        continue
                    with zf.open(m) as f:
                        dados = f.read(MAX_POR_ARQUIVO + 1)
                    _ler_um(f"{nome}/{m.filename}", dados, cnpj_cliente, res)
        except zipfile.BadZipFile:
            res.ignorados.append((nome, "ZIP corrompido"))
    return res
