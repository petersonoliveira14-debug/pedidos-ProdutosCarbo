import os, json, requests
from datetime import datetime, timedelta

CLIENT_ID     = os.environ["BLING_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLING_CLIENT_SECRET"]
BASE          = "https://www.bling.com.br/Api/v3"

def get_token():
    r = requests.post(f"{BASE}/oauth/token",
        data={"grant_type":"client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET))
    r.raise_for_status()
    return r.json()["access_token"]

def get_pedidos(token, data_ini, data_fim):
    headers = {"Authorization": f"Bearer {token}"}
    pedidos, page = [], 1
    while True:
        r = requests.get(f"{BASE}/pedidos", headers=headers, params={
            "dataInicial": data_ini, "dataFinal": data_fim,
            "pagina": page, "limite": 100
        })
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data: break
        pedidos.extend(data)
        page += 1
    return pedidos

def transform(pedido):
    data_raw = pedido.get("data","")
    try:
        dt = datetime.strptime(data_raw, "%Y-%m-%d")
        data_fmt = dt.strftime("%d/%m")
        sem = min(4, (dt.day - 1) // 7 + 1)
    except:
        data_fmt, sem = data_raw, 1

    contato = pedido.get("contato", {})
    vendedor = pedido.get("vendedor", {})
    itens = pedido.get("itens", [])

    produto = "100ml"
    qtd = 0
    for item in itens:
        desc = item.get("descricao","").lower()
        if "1l" in desc or "1 l" in desc:
            produto = "1l"
        qtd += item.get("quantidade", 0)

    situacao = pedido.get("situacao", {})
    cod = situacao.get("valor", 0) if isinstance(situacao, dict) else 0
    status_map = {6:"venda", 9:"cancelada", 12:"bonificacao", 15:"baixa"}
    status = status_map.get(cod, "venda")

    return {
        "nf":      pedido.get("numero", ""),
        "data":    data_fmt,
        "sem":     sem,
        "cliente": contato.get("nome",""),
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

    token   = get_token()
    pedidos = get_pedidos(token, ini, fim)
    notas   = [transform(p) for p in pedidos]

    os.makedirs("data", exist_ok=True)
    with open("data/pedidos.json","w",encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)

    meta = {"ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"), "total": len(notas)}
    with open("data/meta.json","w",encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"OK — {len(notas)} pedidos salvos.")
