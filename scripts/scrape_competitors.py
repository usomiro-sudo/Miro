"""Coleta os precos dos concorrentes de comparacao direta (Seekdopa, Woom, Vorr).

Em vez de depender de uma URL fixa por produto, varre o catalogo de "corrida
masculina" de cada concorrente (config/sites.yaml -> comparacao.<site>.listagem_url)
e faz o pareamento automatico com os produtos MIRO por categoria + similaridade de
nome (scripts/matching.py). Se um produto sumir do catalogo do concorrente ou um
novo aparecer, a proxima execucao ja reflete isso sozinha.

Excecao: se "concorrentes_override" estiver preenchido para algum produto/site em
config/products.yaml, essa URL fixa e usada no lugar do matching automatico.
"""
import json
import os

import yaml

from common import fetch_catalog_products, now_iso, polite_sleep, scrape_product_page
from fetch_miro_products import get_miro_prices
from matching import categorizar, melhor_match, nivel_confianca

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def diff_percentual(preco_miro: float | None, preco_concorrente: float | None) -> float | None:
    if preco_miro is None or preco_concorrente in (None, 0):
        return None
    return round((preco_miro - preco_concorrente) / preco_concorrente * 100, 1)


def coletar_catalogos(concorrentes_cfg: dict, req_cfg: dict) -> dict[str, list[dict]]:
    """Varre o catalogo de cada concorrente uma unica vez e ja classifica cada
    item por categoria, pra reaproveitar entre os 3 produtos MIRO."""
    catalogos: dict[str, list[dict]] = {}
    for chave, cfg in concorrentes_cfg.items():
        url = cfg.get("listagem_url")
        if not url:
            print(f"[info] {cfg['nome']}: listagem_url nao configurada, sem matching automatico")
            catalogos[chave] = []
            continue
        produtos = fetch_catalog_products(
            url, req_cfg["user_agent"], req_cfg["timeout_seconds"], req_cfg["delay_seconds_between_requests"]
        )
        for produto in produtos:
            produto["categoria"] = categorizar(produto.get("nome_site") or "")
        catalogos[chave] = produtos
        print(f"[info] {cfg['nome']}: {len(produtos)} produtos encontrados no catalogo")
    return catalogos


def salvar_snapshot_catalogos(catalogos: dict[str, list[dict]], concorrentes_cfg: dict) -> None:
    """Grava o catalogo completo (nao so os produtos pareados com o MIRO) em
    data/catalogo_historico.jsonl. E a partir dessa serie historica que
    scripts/detect_lancamentos.py detecta produto novo/saiu do catalogo e
    calcula termos em alta — nao tem a ver com comparacao de preco."""
    os.makedirs(DATA_DIR, exist_ok=True)
    snapshot = {
        "coletado_em": now_iso(),
        "concorrentes": {
            chave: {
                "nome": concorrentes_cfg[chave]["nome"],
                "produtos": [
                    {
                        "nome_site": p.get("nome_site"),
                        "preco": p.get("preco"),
                        "url": p.get("url"),
                        "categoria": p.get("categoria"),
                        "disponivel": p.get("disponivel"),
                    }
                    for p in produtos
                ],
            }
            for chave, produtos in catalogos.items()
        },
    }
    with open(os.path.join(DATA_DIR, "catalogo_latest.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "catalogo_historico.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def parear_concorrente(produto_miro: dict, chave: str, cfg: dict, catalogo: list[dict], req_cfg: dict) -> dict:
    override_url = (produto_miro.get("concorrentes_override") or {}).get(chave)
    if override_url:
        info = scrape_product_page(override_url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
        polite_sleep(req_cfg["delay_seconds_between_requests"])
        preco = info["preco"] if info else None
        return {
            "preco": preco,
            "url": override_url,
            "diff_pct": diff_percentual(produto_miro["preco_miro"], preco),
            "origem": "manual",
            "confianca": None,
            "confianca_nivel": None,
            "match_nome": None,
        }

    candidatos = [p for p in catalogo if p.get("categoria") == produto_miro["categoria"]]
    melhor, score = melhor_match(produto_miro["nome"], produto_miro.get("palavras_chave") or [], candidatos)
    if melhor is None:
        return {
            "preco": None,
            "url": None,
            "diff_pct": None,
            "origem": "auto",
            "confianca": 0.0,
            "confianca_nivel": None,
            "match_nome": None,
        }

    preco = melhor.get("preco")
    return {
        "preco": preco,
        "url": melhor.get("url"),
        "diff_pct": diff_percentual(produto_miro["preco_miro"], preco),
        "origem": "auto",
        "confianca": round(score, 2),
        "confianca_nivel": nivel_confianca(score),
        "match_nome": melhor.get("nome_site"),
    }


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    concorrentes_cfg = sites["comparacao"]

    catalogos = coletar_catalogos(concorrentes_cfg, req_cfg)
    salvar_snapshot_catalogos(catalogos, concorrentes_cfg)

    linhas = []
    for produto in get_miro_prices():
        linha = {"nome": produto["nome"], "preco_miro": produto["preco_miro"], "concorrentes": {}}
        for chave, cfg in concorrentes_cfg.items():
            linha["concorrentes"][chave] = parear_concorrente(
                produto, chave, cfg, catalogos.get(chave, []), req_cfg
            )
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
