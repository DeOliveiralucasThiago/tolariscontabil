"""BrasilAPI falsa para o teste ponta a ponta (a real é bloqueada neste ambiente)."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

DADOS = {
    "11222333000181": {"cnpj": "11222333000181", "razao_social": "TECH SOLUCOES EM SOFTWARE LTDA", "nome_fantasia": "TECHSOL",
        "descricao_situacao_cadastral": "ATIVA", "cnae_fiscal": 6201501, "cnae_fiscal_descricao": "Desenvolvimento de programas de computador sob encomenda",
        "municipio": "CAMPINAS", "uf": "SP", "email": "FINANCEIRO@TECHSOL.COM.BR", "ddd_telefone_1": "1932221111",
        "opcao_pelo_simples": True, "opcao_pelo_mei": False},
}

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        cnpj = self.path.rstrip("/").split("/")[-1]
        corpo = DADOS.get(cnpj)
        self.send_response(200 if corpo else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(corpo or {"message": "CNPJ não encontrado"}).encode())
    def log_message(self, *a): pass

HTTPServer(("127.0.0.1", 8099), H).serve_forever()
