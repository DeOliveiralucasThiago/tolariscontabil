"""BrasilAPI falsa para o teste ponta a ponta (a real é bloqueada neste ambiente)."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

DADOS = {
    "11222333000181": {"cnpj": "11222333000181", "razao_social": "TECH SOLUCOES EM SOFTWARE LTDA", "nome_fantasia": "TECHSOL",
        "descricao_situacao_cadastral": "ATIVA", "cnae_fiscal": 6201501, "cnae_fiscal_descricao": "Desenvolvimento de programas de computador sob encomenda",
        "municipio": "CAMPINAS", "uf": "SP", "email": "FINANCEIRO@TECHSOL.COM.BR", "ddd_telefone_1": "1932221111",
        "opcao_pelo_simples": True, "opcao_pelo_mei": False},
}

# PTAX falsa (Banco Central): um boletim de abertura e um de fechamento no dia 2026-10-15, sempre devolvidos
PTAX = {"value": [
    {"cotacaoCompra": 3.9500, "cotacaoVenda": 3.9510, "dataHoraCotacao": "2026-10-15 10:08:40.123", "tipoBoletim": "Abertura"},
    {"cotacaoCompra": 4.0000, "cotacaoVenda": 4.0100, "dataHoraCotacao": "2026-10-15 13:06:11.500", "tipoBoletim": "Fechamento"},
]}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if "CotacaoMoedaPeriodo" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(PTAX).encode())
            return
        cnpj = self.path.rstrip("/").split("/")[-1]
        corpo = DADOS.get(cnpj)
        self.send_response(200 if corpo else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(corpo or {"message": "CNPJ não encontrado"}).encode())
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8099), H).serve_forever()
