"""Utilitários compartilhados: fetch de página + extração de sinal de conteúdo."""
import json
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


def normalizar_texto(texto: str | None) -> str:
    """Minusculo, sem acento, espacos colapsados — usado na deteccao de termos em alta."""
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", texto.lower()).strip()


def fetch_html(url: str, user_agent: str, timeout: int) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"  [aviso] falha ao buscar {url}: {exc}")
        return None


def _price_to_float(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    s = s.replace("R$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_product_from_jsonld(html: str) -> dict | None:
    """Tenta extrair {nome, preco, disponivel} do bloco schema.org/Product."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and "@graph" in item:
                candidates.extend(item["@graph"])
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("Product", ["Product"]):
                continue
            offers = item.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = _price_to_float(offers.get("price"))
            if price is None:
                continue
            return {
                "nome_site": item.get("name"),
                "preco": price,
                "disponivel": offers.get("availability", "").endswith("InStock")
                if offers.get("availability")
                else None,
                "fonte": "json-ld",
            }
    return None


def extract_products_from_listing(html: str) -> list[dict]:
    """Extrai todos os blocos schema.org/Product de uma página (usado pela leitura
    da home, quando a marca expõe produto em destaque via JSON-LD)."""
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        itens = data if isinstance(data, list) else [data]
        for item in itens:
            if isinstance(item, dict) and "@graph" in item:
                itens.extend(item["@graph"])
            if not isinstance(item, dict) or item.get("@type") not in ("Product", ["Product"]):
                continue
            achado = extract_product_from_jsonld(f'<script type="application/ld+json">{json.dumps(item)}</script>')
            if achado:
                achado["url"] = item.get("url")
                produtos.append(achado)
    return produtos


def extract_home_signals(html: str) -> dict:
    """Extrai sinal de tendencia/marketing da PAGINA INICIAL de um site: titulo,
    meta descricao, textos de destaque (h1/h2/h3 + alt de imagem/banner) e
    produtos em JSON-LD se a home expuser algum (nem toda home tem). Usado pro
    painel de tendencias — nao tenta listar o catalogo inteiro, so o que a marca
    escolheu destacar na propria home nesse momento."""
    soup = BeautifulSoup(html, "html.parser")

    titulo = soup.title.get_text(strip=True) if soup.title else None

    descricao = None
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    if meta_desc and meta_desc.get("content"):
        descricao = meta_desc["content"].strip()

    destaques: list[str] = []
    vistos: set[str] = set()
    for tag in soup.find_all(["h1", "h2", "h3"]):
        texto = tag.get_text(" ", strip=True)
        if texto and len(texto) >= 3 and texto.lower() not in vistos:
            vistos.add(texto.lower())
            destaques.append(texto)
    for img in soup.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if alt and len(alt) >= 3 and alt.lower() not in vistos:
            vistos.add(alt.lower())
            destaques.append(alt)

    return {
        "titulo": titulo,
        "descricao": descricao,
        "destaques": destaques[:40],
        "produtos_destaque": extract_products_from_listing(html),
    }


def polite_sleep(seconds: float) -> None:
    time.sleep(seconds)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
