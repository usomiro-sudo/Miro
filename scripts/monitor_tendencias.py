"""Leitura da PÁGINA PRINCIPAL (home) de cada concorrente de comparação direta
(Seekdopa, Woom, Vorr) — sinal de tendência de produto/marketing, não comparação
de preço nem catálogo completo. Olha o que cada marca está destacando na própria
home agora (título, descrição, headlines/banners, produtos em destaque se
houver) e compara com a leitura anterior pra apontar o que é novo.

Independente de scrape_competitors.py — lê só config/sites.yaml
(comparacao.<site>.base_url). Rode manualmente quando quiser uma leitura fresca
(GitHub Actions → Run workflow) ou deixe no agendamento automático.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

import yaml

from common import extract_home_signals, fetch_html, normalizar_texto, now_iso, polite_sleep

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

JANELA_TENDENCIA_DIAS = 60
TOP_N_TERMOS = 12

STOPWORDS = {
    "de", "da", "do", "das", "dos", "com", "para", "por", "em", "the", "and", "sua", "seu",
    "masculino", "masculina", "feminino", "feminina", "unissex", "adulto", "todos", "todas",
    "corrida", "run", "running", "esportivo", "esportiva", "loja", "compre", "confira", "aqui",
    "nova", "novo", "novidade", "novidades", "colecao", "frete", "gratis", "desconto", "pagina",
}


def load_sites_config() -> dict:
    with open(os.path.join(CONFIG_DIR, "sites.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def termos_em_alta(textos: list[str], top_n: int = TOP_N_TERMOS) -> list[list]:
    contador = Counter()
    for texto in textos:
        for palavra in re.findall(r"[a-z0-9-]+", normalizar_texto(texto)):
            if len(palavra) < 4 or palavra in STOPWORDS:
                continue
            contador[palavra] += 1
    return [[termo, contagem] for termo, contagem in contador.most_common(top_n)]


def carregar_historico() -> list[dict]:
    path = os.path.join(DATA_DIR, "tendencias_historico.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def snapshots_na_janela(historico: list[dict], dias: int) -> list[dict]:
    corte = datetime.now(timezone.utc) - timedelta(days=dias)
    recentes = []
    for snap in historico:
        try:
            quando = datetime.fromisoformat(snap["coletado_em"])
        except (KeyError, ValueError):
            continue
        if quando >= corte:
            recentes.append(snap)
    return recentes or historico[-1:]


def main() -> None:
    sites = load_sites_config()
    req_cfg = sites["request"]
    concorrentes_cfg = sites["comparacao"]

    historico = carregar_historico()
    anterior = historico[-1] if historico else None
    janela_historico = snapshots_na_janela(historico, JANELA_TENDENCIA_DIAS)

    resultado = {"coletado_em": now_iso(), "primeira_leitura": anterior is None, "concorrentes": {}}

    for chave, cfg in concorrentes_cfg.items():
        base_url = cfg.get("base_url")
        if not base_url:
            print(f"[info] {cfg['nome']}: base_url nao configurada, pulando")
            continue

        html = fetch_html(base_url, req_cfg["user_agent"], req_cfg["timeout_seconds"])
        polite_sleep(req_cfg["delay_seconds_between_requests"])

        if not html:
            resultado["concorrentes"][chave] = {
                "nome": cfg["nome"],
                "falha_leitura": True,
                "titulo": None,
                "descricao": None,
                "destaques": [],
                "novos_destaques": [],
                "destaques_sumidos": [],
                "produtos_destaque": [],
                "termos_em_alta": [],
            }
            print(f"[aviso] {cfg['nome']}: falha ao ler a home ({base_url})")
            continue

        sinais = extract_home_signals(html)

        dados_anteriores = (anterior or {}).get("concorrentes", {}).get(chave, {})
        destaques_anteriores = set(dados_anteriores.get("destaques", []))
        destaques_atuais = set(sinais["destaques"])

        novos_destaques = [] if anterior is None else [d for d in sinais["destaques"] if d not in destaques_anteriores]
        destaques_sumidos = (
            [] if anterior is None else [d for d in dados_anteriores.get("destaques", []) if d not in destaques_atuais]
        )

        textos_janela = list(sinais["destaques"])
        if sinais["titulo"]:
            textos_janela.append(sinais["titulo"])
        for snap in janela_historico:
            dados = snap.get("concorrentes", {}).get(chave, {})
            textos_janela.extend(dados.get("destaques", []))
            if dados.get("titulo"):
                textos_janela.append(dados["titulo"])

        resultado["concorrentes"][chave] = {
            "nome": cfg["nome"],
            "falha_leitura": False,
            "titulo": sinais["titulo"],
            "descricao": sinais["descricao"],
            "destaques": sinais["destaques"],
            "novos_destaques": novos_destaques,
            "destaques_sumidos": destaques_sumidos,
            "produtos_destaque": sinais["produtos_destaque"],
            "termos_em_alta": termos_em_alta(textos_janela),
        }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "tendencias_latest.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, "tendencias_historico.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    total_novos = sum(len(c.get("novos_destaques", [])) for c in resultado["concorrentes"].values())
    print(f"Tendencias salvas em data/tendencias_latest.json ({total_novos} novos destaques na home)")


if __name__ == "__main__":
    main()
