"""Utilitários compartilhados: fetch de página + extração de preço/nome."""
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

PRICE_RE = re.compile(r"R\$\s*([\d.]{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})")


def normalizar_texto(texto: str | None) -> str:
    """Minusculo, sem acento, espacos colapsados — usado tanto no matching de preco
    quanto na deteccao de termos em alta nos lancamentos."""
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


def extract_products_from_listing(html: str) -> list[dict]:
    """Extrai todos os blocos schema.org/Product de uma página de listagem/categoria
    (usado para varrer o catálogo inteiro de um concorrente, não só um produto)."""
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


def _url_com_pagina(url: str, pagina: int) -> str:
    partes = urlsplit(url)
    query = dict(parse_qsl(partes.query))
    query["page"] = str(pagina)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, urlencode(query), partes.fragment))


def fetch_catalog_products(
    listagem_url: str, user_agent: str, timeout: int, delay_seconds: float, max_pages: int = 15
) -> list[dict]:
    """Percorre a paginação de uma página de listagem/categoria coletando produtos via
    JSON-LD (schema.org/Product). Para quando uma página não traz produto novo
    (deduplicado por URL/nome) ou ao atingir max_pages — proteção contra paginação
    mal configurada ou loop infinito em sites que ignoram o parâmetro `page`.

    Assume o padrão de paginação via querystring `?page=N`, comum em Nuvemshop/Shopify/
    Loja Integrada. Se um concorrente usar outro esquema, essa função só vai retornar
    a primeira página (melhor esforço, não é erro fatal).
    """
    vistos: set[str] = set()
    produtos: list[dict] = []
    for pagina in range(1, max_pages + 1):
        url = listagem_url if pagina == 1 else _url_com_pagina(listagem_url, pagina)
        html = fetch_html(url, user_agent, timeout)
        if not html:
            break
        encontrados = extract_products_from_listing(html)
        chaves_novas = [p.get("url") or p.get("nome_site") for p in encontrados]
        novos = [p for p, chave in zip(encontrados, chaves_novas) if chave and chave not in vistos]
        if not novos:
            break
        vistos.update(p.get("url") or p.get("nome_site") for p in novos)
        produtos.extend(novos)
        polite_sleep(delay_seconds)
    return produtos


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
