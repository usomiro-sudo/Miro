"""Coleta de referencia (Nike, Adidas): sem comparacao direta, so acompanha
precos e produtos de corrida masculina em destaque nas paginas de listagem
configuradas em config/sites.yaml (referencia.<marca>.listagem_url).

Sites grandes tem mais protecao anti-bot e conteudo carregado via JS; esse
script é "best effort" e pode nao encontrar produtos em toda execucao -
isso e esperado, o painel de referencia nao precisa de 100% de precisao.
"""
import json
import os

import yaml
from bs4 import BeautifulSoup

from common import fetch_html, now_iso, polite_sleep
from common import extract_product_from_jsonld

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_listagem_jsonld(html: str) -> list[dict]:
    """Paginas de listagem as vezes trazem varios blocos Product em JSON-LD."""
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        itens = data if isinstance(data, list) else [data]
        for item in itens:
            if isinstance(item, dict) and item.get("@type") == "Product":
                achado = extract_product_from_jsonld(f"<script type=\"application/ld+json\">{json.dumps(item)}</script>")
                if achado:
                    produtos.append(achado)
    return produtos


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    marcas = sites["referencia"]

    resultado = {"coletado_em": now_iso(), "marcas": {}}
    for chave, cfg in marcas.items():
        url = cfg.get("listagem_url")
        if not url:
            print(f"[info] {cfg['nome']}: listagem_url nao configurada, pulando")
            resultado["marcas"][chave] = {"nome": cfg["nome"], "produtos": []}
            continue
        html = fetch_html(url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
        produtos = extract_listagem_jsonld(html) if html else []
        if html and not produtos:
            print(f"[aviso] {cfg['nome']}: pagina carregada mas sem Product JSON-LD "
                  f"(provavelmente renderizada via JS - considerar Playwright)")
        resultado["marcas"][chave] = {"nome": cfg["nome"], "produtos": produtos}
        polite_sleep(req_cfg["delay_seconds_between_requests"])

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "referencia_latest.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    historico_path = os.path.join(DATA_DIR, "referencia_historico.jsonl")
    with open(historico_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    print("Referencia salva em data/referencia_latest.json")


if __name__ == "__main__":
    main()
