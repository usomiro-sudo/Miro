"""Coleta provas de corrida (meia maratona 21km e maratona 42km) nos
próximos meses, a partir de config/sites.yaml (seção "provas").

Estratégia "best effort", igual ao resto do projeto: tenta primeiro dados
estruturados schema.org/Event (JSON-LD); se não achar nada, cai num
fallback que varre links da página e o texto ao redor deles procurando
data + distância. Provas sem distância 21km/42km detectada são ignoradas;
provas com data que não dá pra interpretar também são ignoradas (best
effort não é 100% preciso - o dashboard existe pra dar uma visão rápida,
use o link pra conferir).

IMPORTANTE: o site de origem (config "provas.fonte.url") não pôde ser
inspecionado durante o desenvolvimento (bloqueio de rede do ambiente de
dev). Se o formato de data/distância usado por ele for muito diferente do
esperado aqui, pode ser necessário ajustar as regex abaixo depois de ver o
resultado da primeira coleta real.
"""
import calendar
import json
import os
import re
from datetime import date, timedelta
from urllib.parse import urljoin

import yaml
from bs4 import BeautifulSoup

from common import fetch_html, now_iso

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}

RE_DATA_BARRA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
RE_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s*(?:de)?\s*(" + "|".join(MESES) + r")(?:\s*(?:de)?\s*(\d{4}))?\b",
    re.IGNORECASE,
)
MAX_ITENS = 40


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def distancias_do_texto(texto: str) -> list[int]:
    t = texto.lower()
    achadas = set()
    if re.search(r"21\s*km|meia\s+maratona", t):
        achadas.add(21)
    # remove "meia maratona" antes de procurar "maratona" sozinha, senão um evento que
    # oferece as duas distâncias (comum) só seria contado como 21km.
    t_sem_meia = re.sub(r"meia\s+maratona", "", t)
    if re.search(r"42\s*km", t) or re.search(r"\bmaratonas?\b", t_sem_meia):
        achadas.add(42)
    return sorted(achadas)


def add_months(d: date, months: int) -> date:
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def parse_data(texto: str, hoje: date) -> date | None:
    m = RE_DATA_BARRA.search(texto)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ano = ano if ano > 100 else 2000 + ano
        try:
            return date(ano, mes, dia)
        except ValueError:
            return None

    m = RE_DATA_EXTENSO.search(texto)
    if m:
        dia = int(m.group(1))
        mes = MESES[m.group(2).lower()]
        ano_txt = m.group(3)
        try:
            if ano_txt:
                return date(int(ano_txt), mes, dia)
            candidato = date(hoje.year, mes, dia)
            if candidato < hoje - timedelta(days=7):
                candidato = date(hoje.year + 1, mes, dia)
            return candidato
        except ValueError:
            return None

    return None


def extrair_eventos_jsonld(html: str, hoje: date) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    eventos = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data_json = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        itens = data_json if isinstance(data_json, list) else [data_json]
        for item in itens:
            if isinstance(item, dict) and "@graph" in item:
                itens.extend(item["@graph"])
            if not isinstance(item, dict) or item.get("@type") not in ("Event", ["Event"]):
                continue
            nome = item.get("name")
            inicio = item.get("startDate")
            if not nome or not inicio:
                continue
            distancias = distancias_do_texto(f"{nome} {item.get('description', '')}")
            if not distancias:
                continue
            try:
                data_prova = date.fromisoformat(inicio[:10])
            except ValueError:
                continue
            eventos.append({
                "nome": nome.strip(),
                "data": data_prova.isoformat(),
                "distancias_km": distancias,
                "url": item.get("url"),
            })
    return eventos


def extrair_eventos_fallback(html: str, base_url: str, hoje: date) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    eventos = []
    for link in soup.find_all("a", href=True):
        contexto = link.find_parent(["li", "article", "div"]) or link
        texto = contexto.get_text(" ", strip=True)
        if not texto:
            continue

        distancias = distancias_do_texto(texto)
        if not distancias:
            continue

        data_prova = parse_data(texto, hoje)
        if data_prova is None:
            continue

        nome = link.get_text(" ", strip=True) or texto[:80]
        eventos.append({
            "nome": nome.strip(),
            "data": data_prova.isoformat(),
            "distancias_km": distancias,
            "url": urljoin(base_url, link["href"]),
        })
    return eventos


def deduplicar_e_filtrar(eventos: list[dict], hoje: date, limite: date) -> list[dict]:
    vistos = set()
    resultado = []
    for ev in sorted(eventos, key=lambda e: e["data"]):
        data_prova = date.fromisoformat(ev["data"])
        if not (hoje <= data_prova <= limite):
            continue
        chave = (ev["nome"].lower(), ev["data"])
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(ev)
        if len(resultado) >= MAX_ITENS:
            break
    return resultado


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    provas_cfg = sites["provas"]
    fonte_url = provas_cfg["fonte"]["url"]
    janela_meses = provas_cfg["janela_meses"]

    hoje = date.today()
    limite = add_months(hoje, janela_meses)

    html = fetch_html(fonte_url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
    if html is None:
        resultado = {
            "coletado_em": now_iso(), "fonte": provas_cfg["fonte"]["nome"], "fonte_url": fonte_url,
            "erro": "falha ao acessar a fonte de provas", "provas": [],
        }
    else:
        eventos = extrair_eventos_jsonld(html, hoje)
        if not eventos:
            eventos = extrair_eventos_fallback(html, fonte_url, hoje)
            if not eventos:
                print("  [aviso] nenhuma prova de 21km/42km encontrada (pode ser conteudo "
                      "renderizado via JS, ou a home nao lista provas diretamente - considerar "
                      "apontar para uma pagina de calendario especifica)")
        provas = deduplicar_e_filtrar(eventos, hoje, limite)
        resultado = {
            "coletado_em": now_iso(), "fonte": provas_cfg["fonte"]["nome"], "fonte_url": fonte_url,
            "erro": None, "provas": provas,
        }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "provas_latest.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    historico_path = os.path.join(DATA_DIR, "provas_historico.jsonl")
    with open(historico_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    print(f"Provas salvas em data/provas_latest.json ({len(resultado['provas'])} encontradas)")


if __name__ == "__main__":
    main()
