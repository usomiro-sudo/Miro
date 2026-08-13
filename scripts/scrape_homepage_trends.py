"""Coleta tendências das home pages dos concorrentes (Seekdopa, Woom, Vorr,
Nike, Adidas): promoções/banners e novos lançamentos em destaque.

Não faz comparação de preço produto a produto - só sinaliza o que muda de
uma coleta para outra, com base em palavras-chave configuráveis em
config/sites.yaml (seção "deteccao").

Sites grandes tem mais protecao anti-bot e conteudo carregado via JS; esse
script é "best effort" e pode nao encontrar nada em toda execucao - isso e
esperado, o painel nao precisa de 100% de precisao.
"""
import json
import os
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from common import fetch_html, now_iso, polite_sleep

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

MAX_ITENS_POR_CATEGORIA = 8
TAMANHO_MIN_TRECHO = 4
TAMANHO_MAX_TRECHO = 140


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def extrair_trechos(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.find_all(["a", "h1", "h2", "h3", "span", "p", "div"])


def bate_palavra_chave(texto: str, palavras_chave: list[str]) -> bool:
    texto_lower = texto.lower()
    return any(p in texto_lower for p in palavras_chave)


def detectar_tendencias(html: str, base_url: str, palavras_promocao: list[str],
                         palavras_lancamento: list[str]) -> dict:
    promocoes: dict[str, None] = {}
    lancamentos: dict[str, dict] = {}

    for tag in extrair_trechos(html):
        texto = tag.get_text(" ", strip=True)
        if not (TAMANHO_MIN_TRECHO <= len(texto) <= TAMANHO_MAX_TRECHO):
            continue

        if bate_palavra_chave(texto, palavras_promocao):
            promocoes.setdefault(texto, None)

        if bate_palavra_chave(texto, palavras_lancamento):
            href = tag.get("href") if tag.name == "a" else None
            url_abs = urljoin(base_url, href) if href else None
            lancamentos.setdefault(texto, {"texto": texto, "url": url_abs})

    return {
        "promocoes": list(promocoes.keys())[:MAX_ITENS_POR_CATEGORIA],
        "lancamentos": list(lancamentos.values())[:MAX_ITENS_POR_CATEGORIA],
    }


def carregar_ultima_coleta(historico_path: str, chave: str) -> dict | None:
    if not os.path.exists(historico_path):
        return None
    ultima = None
    with open(historico_path, encoding="utf-8") as f:
        for linha in f:
            try:
                registro = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if chave in registro.get("concorrentes", {}):
                ultima = registro["concorrentes"][chave]
    return ultima


def marcar_novidades(atual: dict, anterior: dict | None) -> dict:
    promo_anteriores = set(anterior["promocoes"]) if anterior else set()
    lanc_anteriores = {item["texto"] for item in anterior["lancamentos"]} if anterior else set()

    atual["promocoes_novas"] = [p for p in atual["promocoes"] if p not in promo_anteriores]
    atual["promocoes_encerradas"] = sorted(promo_anteriores - set(atual["promocoes"]))
    atual["lancamentos_novos"] = [l["texto"] for l in atual["lancamentos"] if l["texto"] not in lanc_anteriores]
    return atual


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    concorrentes_cfg = sites["concorrentes"]
    palavras_promocao = sites["deteccao"]["promocoes"]
    palavras_lancamento = sites["deteccao"]["lancamentos"]

    os.makedirs(DATA_DIR, exist_ok=True)
    historico_path = os.path.join(DATA_DIR, "tendencias_historico.jsonl")

    resultado = {"coletado_em": now_iso(), "concorrentes": {}}
    for chave, cfg in concorrentes_cfg.items():
        url = cfg["home_url"]
        html = fetch_html(url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
        if html is None:
            entrada = {
                "nome": cfg["nome"], "url": url, "erro": "falha ao acessar a home page",
                "promocoes": [], "lancamentos": [],
            }
        else:
            tendencias = detectar_tendencias(html, url, palavras_promocao, palavras_lancamento)
            entrada = {"nome": cfg["nome"], "url": url, "erro": None, **tendencias}
            if not entrada["promocoes"] and not entrada["lancamentos"]:
                print(f"  [aviso] {cfg['nome']}: nada detectado (pode ser conteudo renderizado via "
                      f"JS - considerar Playwright)")

        anterior = carregar_ultima_coleta(historico_path, chave)
        resultado["concorrentes"][chave] = marcar_novidades(entrada, anterior)
        polite_sleep(req_cfg["delay_seconds_between_requests"])

    with open(os.path.join(DATA_DIR, "tendencias_latest.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    with open(historico_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    print("Tendencias salvas em data/tendencias_latest.json")


if __name__ == "__main__":
    main()
