import os, json, requests, base64, subprocess
from datetime import datetime

CLIENT_ID     = os.environ["BLING_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLING_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["BLING_REFRESH_TOKEN"]
BASE          = "https://www.bling.com.br/Api/v3"
REPO          = "petersonoliveira14-debug/pedidos-ProdutosCarbo"

def get_token():
    cred = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(f"{BASE}/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "Authorization": f"Basic {cred}"},
        data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN})
    if not r.ok:
        print(f"Auth erro {r.status_code}: {r.text}")
        r.raise_for_status()
    data = r.json()
    # Salvar novo refresh_token se rotacionado
    new_rt = data.get("refresh_token")
    if new_rt and new_rt != REFRESH_TOKEN:
        print("Refresh token rotacionado — atualizando Secret...")
        subprocess.run(["gh", "secret", "set", "BLING_REFRESH_TOKEN",
                        "--body", new_rt, "--repo", REPO], check=False)
        print("Secret atualizado OK")
    print("Token OK")
    return data["access_token"]

def get_pedidos(token, data_ini, data_fim):
    headers = {"Authorization": f"Bearer {token}"}
    pedidos, page = [], 1
    while True:
        r = requests.get(f"{BASE}/pedidos/vendas", headers=headers, params={
            "dataInicial": data_ini, "dataFinal": data_fim,
            "pagina": page, "limite": 100
        })
        if not r.ok:
            print(f"Pedidos erro {r.status_code}: {r.text}")
            break
        data = r.json().get("data", [])
        if not data:
            break
        pedidos.extend(data)
        page += 1
    return pedidos

def transform(pedido):
    data_raw = pedido.get("data", "")
    try:
        dt = datetime.strptime(data_raw, "%Y-%m-%d")
        data_fmt = dt.strftime("%d/%m")
        sem = min(4, (dt.day - 1) // 7 + 1)
    except:
        data_fmt, sem = data_raw, 1

    contato  = pedido.get("contato", {})
    vendedor = pedido.get("vendedor", {})
    itens    = pedido.get("itens", [])

    produto, qtd = "100ml", 0
    for item in itens:
        desc = item.get("descricao", "").lower()
        if "1l" in desc or "1 l" in desc:
            produto = "1l"
        qtd += item.get("quantidade", 0)

    situacao = pedido.get("situacao", {})
    cod = situacao.get("valor", 0) if isinstance(situacao, dict) else 0
    status = {6:"venda", 9:"cancelada", 12:"bonificacao", 15:"baixa"}.get(cod, "venda")

    return {
        "nf":      pedido.get("numero", ""),
        "data":    data_fmt,
        "sem":     sem,
        "cliente": contato.get("nome", ""),
        "status":  status,
        "valor":   float(pedido.get("totalProdutos", 0)),
        "produto": produto,
        "qtd":     int(qtd),
        "vendedor": vendedor.get("nome") if vendedor else None
    }

if __name__ == "__main__":
    hoje = datetime.today()
    ini  = hoje.replace(day=1).strftime("%Y-%m-%d")
    fim  = hoje.strftime("%Y-%m-%d")
    print(f"Buscando pedidos de {ini} a {fim}...")
    token   = get_token()
    pedidos = get_pedidos(token, ini, fim)
    notas   = [transform(p) for p in pedidos]
    os.makedirs("data", exist_ok=True)
    with open("data/pedidos.json", "w", encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)
    meta = {"ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"), "total": len(notas)}
    with open("data/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"OK — {len(notas)} pedidos salvos.")
