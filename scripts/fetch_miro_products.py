"""Busca os preços atuais do MIRO via API oficial da Nuvemshop.

Se um produto em config/products.yaml nao tiver nuvemshop_id, usa o
preco_manual como fallback (editado a mao no yaml).
"""
import os

import requests
import yaml

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


def load_products_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "products.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_nuvemshop_product(store_id: str, token: str, product_id: str) -> float | None:
    url = f"https://api.nuvemshop.com.br/2025-03/{store_id}/products/{product_id}"
    headers = {
        "Authentication": f"bearer {token}",
        "User-Agent": "MIRO-Intelligence (uso.miro@outlook.com)",
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    variants = data.get("variants") or []
    if not variants:
        return None
    # primeira variante como preco de referencia do produto
    return float(variants[0]["price"])


def get_miro_prices() -> list[dict]:
    config = load_products_config()
    store_id = os.environ.get("NUVEMSHOP_STORE_ID")
    token = os.environ.get("NUVEMSHOP_ACCESS_TOKEN")

    resultados = []
    for produto in config["produtos"]:
        preco = produto.get("preco_manual")
        if produto.get("nuvemshop_id") and store_id and token:
            try:
                preco = fetch_nuvemshop_product(store_id, token, produto["nuvemshop_id"])
            except requests.RequestException as exc:
                print(f"[aviso] falha ao buscar '{produto['nome']}' na Nuvemshop: {exc}")
        resultados.append({"nome": produto["nome"], "preco_miro": preco, "concorrentes": produto["concorrentes"]})
    return resultados


if __name__ == "__main__":
    for item in get_miro_prices():
        print(item)
