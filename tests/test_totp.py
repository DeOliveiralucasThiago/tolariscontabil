"""TOTP (RFC 6238) e códigos de recuperação."""

from __future__ import annotations

import base64

from tolaris_api import totp

# Vetores da RFC 6238 (SHA-1, segredo ASCII "12345678901234567890"); o teste da RFC usa 8 dígitos, aqui são os 6 últimos
SEGREDO_RFC = base64.b32encode(b"12345678901234567890").decode().rstrip("=")


def test_vetores_da_rfc_6238():
    for instante, oito_digitos in ((59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471"), (1234567890, "89005924"), (2000000000, "69279037")):
        assert totp.codigo(SEGREDO_RFC, totp.passo_atual(instante)) == oito_digitos[-6:]


def test_segredo_novo_tem_160_bits_e_nao_repete():
    a, b = totp.novo_segredo(), totp.novo_segredo()
    assert a != b and len(a) == 32 and len(base64.b32decode(a)) == 20


def test_verificar_aceita_a_janela_e_recusa_o_resto():
    agora = 1_700_000_000
    passo = totp.passo_atual(agora)
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo), agora=agora) == passo
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo - 1), agora=agora) == passo - 1
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo + 1), agora=agora) == passo + 1
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo - 2), agora=agora) is None
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo + 2), agora=agora) is None


def test_codigo_nao_vale_duas_vezes():
    agora = 1_700_000_000
    passo = totp.passo_atual(agora)
    c = totp.codigo(SEGREDO_RFC, passo)
    assert totp.verificar(SEGREDO_RFC, c, ultimo_passo=passo, agora=agora) is None
    assert totp.verificar(SEGREDO_RFC, c, ultimo_passo=passo - 1, agora=agora) == passo
    # um código mais antigo que o último aceito também é recusado
    assert totp.verificar(SEGREDO_RFC, totp.codigo(SEGREDO_RFC, passo - 1), ultimo_passo=passo, agora=agora) is None


def test_formato_do_codigo_digitado():
    agora = 1_700_000_000
    c = totp.codigo(SEGREDO_RFC, totp.passo_atual(agora))
    assert totp.verificar(SEGREDO_RFC, f"{c[:3]} {c[3:]}", agora=agora) is not None  # com espaço, como o app mostra
    for ruim in ("", "12345", "1234567", "abcdef", "12345a"):
        assert totp.verificar(SEGREDO_RFC, ruim, agora=agora) is None


def test_uri_para_o_aplicativo():
    u = totp.uri("ABC234", "ana@escritorio.com.br")
    assert u.startswith("otpauth://totp/Tolaris%20Cont%C3%A1bil:ana%40escritorio.com.br?secret=ABC234&issuer=Tolaris%20Cont%C3%A1bil")
    assert "digits=6" in u and "period=30" in u


def test_codigos_de_recuperacao():
    mostrar, hashes = totp.novos_codigos_recuperacao()
    assert len(mostrar) == len(set(mostrar)) == len(hashes) == 8
    assert all(len(c) == 11 and c[5] == "-" for c in mostrar)
    assert all(h not in "".join(mostrar) for h in hashes)  # guarda só o hash
    restantes = totp.consumir_recuperacao(hashes, mostrar[3].upper())  # maiúsculas e minúsculas valem
    assert restantes is not None and len(restantes) == 7
    assert totp.consumir_recuperacao(restantes, mostrar[3]) is None  # só vale uma vez
    assert totp.consumir_recuperacao(hashes, mostrar[0].replace("-", " ")) is not None  # separador livre
    assert totp.consumir_recuperacao(hashes, "aaaaa-bbbbb") is None
    assert totp.consumir_recuperacao(hashes, "123456") is None
    assert totp.consumir_recuperacao(None, mostrar[0]) is None
