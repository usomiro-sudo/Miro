"""Utilitários compartilhados: fetch de página + extração de preço/nome."""
import json
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"R\$\s*([\d.]{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})")


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


def extract_price_fallback(html: str) -> dict | None:
    """Sem JSON-LD: pega o primeiro valor em formato R$ 000,00 da página.

    Impreciso (pode pegar frete, produto relacionado etc.) - usar como
    último recurso e conferir manualmente os resultados no dashboard.
    """
    match = PRICE_RE.search(html)
    if not match:
        return None
    price = _price_to_float(match.group(1))
    if price is None:
        return None
    return {"nome_site": None, "preco": price, "disponivel": None, "fonte": "regex-fallback"}


def scrape_product_page(url: str, user_agent: str, timeout: int) -> dict | None:
    if not url:
        return None
    html = fetch_html(url, user_agent, timeout)
    if html is None:
        return None
    result = extract_product_from_jsonld(html)
    if result is None:
        result = extract_price_fallback(html)
        if result is None:
            print(f"  [aviso] nenhum preco encontrado em {url}")
    if result is not None:
        result["url"] = url
    return result


def polite_sleep(seconds: float) -> None:
    time.sleep(seconds)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
