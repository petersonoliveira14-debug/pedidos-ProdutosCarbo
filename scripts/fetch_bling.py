import os, json, requests, base64, subprocess, time
from datetime import datetime, timedelta

CLIENT_ID     = os.environ["BLING_CLIENT_ID"]
CLIENT_SECRET = os.environ["BLING_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["BLING_REFRESH_TOKEN"]
BASE          = "https://www.bling.com.br/Api/v3"
REPO          = "petersonoliveira14-debug/pedidos-ProdutosCarbo"

# Quantos meses para trás buscar (além do atual)
MESES_ATRAS = int(os.environ.get("BLING_MESES_ATRAS", "6"))

MESES_PT = {
    1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",
    7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"
}

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
    new_rt = data.get("refresh_token")
    if new_rt and new_rt != REFRESH_TOKEN:
        print("Refresh token rotacionado — atualizando Secret...")
        subprocess.run(["gh", "secret", "set", "BLING_REFRESH_TOKEN",
                        "--body", new_rt, "--repo", REPO], check=False)
        print("Secret atualizado OK")
    print("Token OK")
    return data["access_token"]

def get_pedidos_lista(token, data_ini, data_fim):
    """Busca lista de pedidos (apenas IDs e dados resumidos)."""
    headers = {"Authorization": f"Bearer {token}"}
    pedidos, page = [], 1
    while True:
        r = requests.get(f"{BASE}/pedidos/vendas", headers=headers, params={
            "dataInicial": data_ini, "dataFinal": data_fim,
            "pagina": page, "limite": 100
        })
        if not r.ok:
            print(f"  Lista pedidos erro {r.status_code}: {r.text}")
            break
        data = r.json().get("data", [])
        if not data:
            break
        pedidos.extend(data)
        page += 1
    return pedidos

def get_pedido_detalhe(token, pedido_id):
    """Busca detalhes completos de um pedido (itens, vendedor, etc)."""
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE}/pedidos/vendas/{pedido_id}", headers=headers)
    if not r.ok:
        print(f"  Detalhe {pedido_id} erro {r.status_code}")
        return None
    return r.json().get("data", {})

def detect_marca(itens):
    """Detecta a marca pelo nome dos produtos nos itens."""
    for item in itens:
        desc = (item.get("descricao", "") or "").lower()
        if any(x in desc for x in ["carbopro", "carbo pro", "carbovapt", "carbo vapt", "vapt"]):
            return "carbopro"
    return "carbozé"

def detect_produto(itens):
    """Detecta o tipo de produto (100ml ou 1l) pelos itens."""
    for item in itens:
        desc = (item.get("descricao", "") or "").lower()
        if "1l" in desc or "1 l" in desc or "1 litro" in desc:
            return "1l"
    return "100ml"

def get_qtd_itens(itens):
    """Soma quantidade de todos os itens."""
    total = 0
    for item in itens:
        total += item.get("quantidade", 0) or 0
    return int(total)

def transform(pedido):
    data_raw = pedido.get("data", "")
    try:
        dt = datetime.strptime(data_raw, "%Y-%m-%d")
        data_fmt = dt.strftime("%d/%m")
        sem = min(4, (dt.day - 1) // 7 + 1)
    except:
        data_fmt, sem = data_raw, 1

    contato  = pedido.get("contato", {}) or {}
    vendedor = pedido.get("vendedor", {}) or {}
    itens    = pedido.get("itens", []) or []

    marca   = detect_marca(itens)
    produto = detect_produto(itens)
    qtd     = get_qtd_itens(itens)

    situacao = pedido.get("situacao", {})
    cod = situacao.get("valor", 0) if isinstance(situacao, dict) else 0
    status = {6:"venda", 9:"cancelada", 12:"bonificacao", 15:"baixa"}.get(cod, "venda")

    # Número da NF (nota fiscal) pode estar separado do número do pedido
    numero_nf = pedido.get("numeroLoja", "") or pedido.get("numero", "")

    return {
        "nf":       numero_nf,
        "data":     data_fmt,
        "sem":      sem,
        "cliente":  contato.get("nome", "") or "",
        "status":   status,
        "valor":    float(pedido.get("totalProdutos", 0) or 0),
        "produto":  produto,
        "qtd":      qtd,
        "vendedor": (vendedor.get("nome") or "").strip() or None,
        "marca":    marca,
        "itens_desc": "; ".join(
            f"{(it.get('descricao',''))} x{it.get('quantidade',0)}"
            for it in itens
        ) if itens else ""
    }

def fetch_mes(token, ano, mes):
    """Busca todos os pedidos de um mês, com detalhes individuais."""
    primeiro = datetime(ano, mes, 1)
    if mes == 12:
        ultimo = datetime(ano + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo = datetime(ano, mes + 1, 1) - timedelta(days=1)

    # Não buscar além de hoje
    hoje = datetime.today()
    if ultimo > hoje:
        ultimo = hoje

    ini = primeiro.strftime("%Y-%m-%d")
    fim = ultimo.strftime("%Y-%m-%d")
    label = f"{MESES_PT[mes]}/{ano}"

    print(f"  [{label}] Buscando lista ({ini} a {fim})...")
    pedidos = get_pedidos_lista(token, ini, fim)
    if not pedidos:
        print(f"  [{label}] Nenhum pedido encontrado")
        return []

    print(f"  [{label}] {len(pedidos)} pedidos — buscando detalhes...")
    detalhados = []
    for i, p in enumerate(pedidos):
        pid = p.get("id")
        if not pid:
            detalhados.append(p)
            continue

        # Busca detalhe individual (com itens, vendedor, etc)
        detail = get_pedido_detalhe(token, pid)
        if detail:
            detalhados.append(detail)
        else:
            detalhados.append(p)  # fallback para dados resumidos

        # Rate limiting: Bling limita a 3 req/s
        if (i + 1) % 3 == 0:
            time.sleep(1.1)

    notas = [transform(d) for d in detalhados]
    print(f"  [{label}] OK — {len(notas)} notas transformadas")
    return notas


if __name__ == "__main__":
    hoje = datetime.today()
    token = get_token()

    # ── Carrega vendor overrides ─────────────────────────────────────────
    vend_path = "data/vendedores.json"
    vend_ov = {}
    if os.path.exists(vend_path):
        with open(vend_path, encoding="utf-8") as f:
            vend_ov = json.load(f)

    os.makedirs("data", exist_ok=True)
    hist_dir = "data/historico"
    os.makedirs(hist_dir, exist_ok=True)

    # ── Determina meses a buscar ─────────────────────────────────────────
    # Lê index.json existente para saber quais meses já temos
    index_path = f"{hist_dir}/index.json"
    meses_existentes = []
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            meses_existentes = json.load(f).get("meses", [])

    # Gera lista de meses a processar (atual + MESES_ATRAS anteriores)
    meses_alvo = []
    dt_cursor = hoje.replace(day=1)
    for _ in range(MESES_ATRAS + 1):
        meses_alvo.append((dt_cursor.year, dt_cursor.month))
        dt_cursor = (dt_cursor - timedelta(days=1)).replace(day=1)

    # Mês atual sempre re-fetcha; meses anteriores só se não existirem
    mes_atual = f"{hoje.year}-{hoje.month:02d}"

    print(f"Período: {MESES_ATRAS} meses para trás + mês atual ({mes_atual})")
    print(f"Meses já existentes: {meses_existentes}")

    for ano, mes in meses_alvo:
        ym = f"{ano}-{mes:02d}"
        hist_file = f"{hist_dir}/{ym}.json"

        # Mês atual: sempre refaz. Meses anteriores: pula se já existem.
        if ym != mes_atual and os.path.exists(hist_file):
            print(f"  [{MESES_PT[mes]}/{ano}] Já existe — pulando")
            continue

        notas = fetch_mes(token, ano, mes)
        if not notas and ym != mes_atual:
            continue

        # Aplica overrides de vendedor
        for nota in notas:
            key = str(nota["nf"])
            if key in vend_ov and vend_ov[key]:
                nota["vendedor"] = vend_ov[key]

        # Salva historico
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(notas, f, ensure_ascii=False, indent=2)

        if ym not in meses_existentes:
            meses_existentes.append(ym)

        cz = sum(1 for n in notas if n["marca"] == "carbozé")
        cp = sum(1 for n in notas if n["marca"] == "carbopro")
        print(f"  [{MESES_PT[mes]}/{ano}] Salvo: {len(notas)} NFs | CZ:{cz} CP:{cp}")

    # ── Salva index.json ─────────────────────────────────────────────────
    meses_existentes = sorted(set(meses_existentes), reverse=True)
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({"meses": meses_existentes, "atual": mes_atual}, f, ensure_ascii=False)

    # ── Salva pedidos.json (mês atual) e meta.json ───────────────────────
    atual_file = f"{hist_dir}/{mes_atual}.json"
    notas_atual = []
    if os.path.exists(atual_file):
        with open(atual_file, encoding="utf-8") as f:
            notas_atual = json.load(f)

    with open("data/pedidos.json", "w", encoding="utf-8") as f:
        json.dump(notas_atual, f, ensure_ascii=False, indent=2)

    meta = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total":   len(notas_atual),
        "periodo": f"{MESES_PT[hoje.month]} {hoje.year}"
    }
    with open("data/meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    total_all = sum(
        len(json.load(open(f"{hist_dir}/{ym}.json", encoding="utf-8")))
        for ym in meses_existentes
        if os.path.exists(f"{hist_dir}/{ym}.json")
    )
    print(f"\nRESUMO: {total_all} NFs totais | {len(meses_existentes)} meses | Histórico: {meses_existentes}")
