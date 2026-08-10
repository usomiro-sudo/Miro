"""Coleta os precos dos concorrentes de comparacao direta (Seekdopa, Woom, Vorr)
para cada produto do MIRO, usando as URLs configuradas em products.yaml.
"""
import json
import os

import yaml

from common import now_iso, polite_sleep, scrape_product_page
from fetch_miro_products import get_miro_prices

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def diff_percentual(preco_miro: float | None, preco_concorrente: float | None) -> float | None:
    if preco_miro is None or preco_concorrente in (None, 0):
        return None
    return round((preco_miro - preco_concorrente) / preco_concorrente * 100, 1)


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    concorrentes_cfg = sites["comparacao"]

    linhas = []
    for produto in get_miro_prices():
        linha = {"nome": produto["nome"], "preco_miro": produto["preco_miro"], "concorrentes": {}}
        for chave, url in produto["concorrentes"].items():
            if not url:
                linha["concorrentes"][chave] = {"preco": None, "url": None, "diff_pct": None}
                continue
            info = scrape_product_page(url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
            preco = info["preco"] if info else None
            linha["concorrentes"][chave] = {
                "preco": preco,
                "url": url,
                "diff_pct": diff_percentual(linha["preco_miro"], preco),
            }
            polite_sleep(req_cfg["delay_seconds_between_requests"])
        linhas.append(linha)

    os.makedirs(DATA_DIR, exist_ok=True)
    saida = {"coletado_em": now_iso(), "produtos": linhas}
    with open(os.path.join(DATA_DIR, "comparacao_latest.json"), "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=2)

    historico_path = os.path.join(DATA_DIR, "comparacao_historico.jsonl")
    with open(historico_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(saida, ensure_ascii=False) + "\n")

    print(f"Comparacao salva em data/comparacao_latest.json ({len(linhas)} produtos)")


if __name__ == "__main__":
    main()
