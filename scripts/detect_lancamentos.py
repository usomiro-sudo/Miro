"""Painel de lançamentos & tendências dos concorrentes (Seekdopa, Woom, Vorr).

Não é sobre preço — é sobre produto/marketing: o que cada concorrente está
lançando, o que saiu do catálogo, e quais termos aparecem com mais frequência
nos nomes dos produtos recentes (proxy simples de tendência: "compressão",
"UV50", "trail", "reciclado" etc. aparecendo com mais frequência sinaliza pra
onde o concorrente está apostando).

Compara o snapshot de catálogo mais recente (data/catalogo_historico.jsonl,
gerado por scrape_competitors.py) com o snapshot anterior. Por isso precisa
de pelo menos 2 execuções de scrape_competitors.py pra começar a mostrar
lançamentos/saídas — a primeira execução só estabelece a linha de base.

A contagem de termos é uma heurística simples (frequência de palavra no nome
do produto, sem stopwords óbvias) — não é NLP de verdade. Serve como ponto de
partida pra leitura qualitativa, não como conclusão pronta.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from common import normalizar_texto

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

JANELA_TENDENCIA_DIAS = 60
TOP_N_TERMOS = 12

STOPWORDS = {
    "de", "da", "do", "das", "dos", "com", "para", "por", "em", "the", "and",
    "masculino", "masculina", "feminino", "feminina", "unissex", "adulto",
    "corrida", "run", "running", "esportivo", "esportiva", "linha", "colecao",
    "novo", "nova", "kit", "conjunto", "tamanho", "cor", "modelo",
}


def _chave_produto(produto: dict) -> str | None:
    return produto.get("url") or (produto.get("nome_site") or "").strip().lower() or None


def carregar_historico_catalogo() -> list[dict]:
    path = os.path.join(DATA_DIR, "catalogo_historico.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def termos_em_alta(produtos: list[dict], top_n: int = TOP_N_TERMOS) -> list[list]:
    contador = Counter()
    for produto in produtos:
        nome_norm = normalizar_texto(produto.get("nome_site"))
        for palavra in re.findall(r"[a-z0-9-]+", nome_norm):
            if len(palavra) < 4 or palavra in STOPWORDS:
                continue
            contador[palavra] += 1
    return [[termo, contagem] for termo, contagem in contador.most_common(top_n)]


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
    historico = carregar_historico_catalogo()
    if not historico:
        print("[info] sem data/catalogo_historico.jsonl ainda — rode scrape_competitors.py primeiro")
        return

    atual = historico[-1]
    anterior = historico[-2] if len(historico) >= 2 else None
    janela = snapshots_na_janela(historico, JANELA_TENDENCIA_DIAS)

    resultado = {
        "coletado_em": atual["coletado_em"],
        "primeira_coleta": anterior is None,
        "concorrentes": {},
    }

    for chave, dados_atual in atual["concorrentes"].items():
        produtos_atuais = dados_atual.get("produtos", [])
        chaves_atuais = {_chave_produto(p) for p in produtos_atuais if _chave_produto(p)}

        produtos_anteriores = (anterior or {}).get("concorrentes", {}).get(chave, {}).get("produtos", [])
        chaves_anteriores = {_chave_produto(p) for p in produtos_anteriores if _chave_produto(p)}

        # Catalogo atual vazio mas o anterior nao era: provavelmente falha de coleta
        # (site fora do ar, layout mudou) e nao um esvaziamento real do catalogo.
        # Nesse caso nao calcula lancamentos/descontinuados - senao o catalogo
        # inteiro apareceria como "descontinuado" por engano.
        falha_coleta = anterior is not None and not produtos_atuais and bool(produtos_anteriores)

        if anterior is None or falha_coleta:
            lancamentos = []
            descontinuados = []
        else:
            lancamentos = [p for p in produtos_atuais if _chave_produto(p) not in chaves_anteriores]
            descontinuados = [p for p in produtos_anteriores if _chave_produto(p) not in chaves_atuais]

        # produtos distintos vistos em qualquer snapshot dentro da janela de tendencia
        vistos: set[str] = set()
        produtos_janela = []
        for snap in janela:
            for p in snap.get("concorrentes", {}).get(chave, {}).get("produtos", []):
                k = _chave_produto(p)
                if k and k not in vistos:
                    vistos.add(k)
                    produtos_janela.append(p)

        resultado["concorrentes"][chave] = {
            "nome": dados_atual.get("nome", chave),
            "total_catalogo": len(produtos_atuais),
            "lancamentos": lancamentos,
            "descontinuados": descontinuados,
            "falha_coleta": falha_coleta,
            "termos_em_alta": termos_em_alta(produtos_janela),
            "por_categoria": dict(Counter(p.get("categoria") or "outro" for p in produtos_atuais)),
        }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "lancamentos_latest.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    with open(os.path.join(DATA_DIR, "lancamentos_historico.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(resultado, ensure_ascii=False) + "\n")

    total_lancamentos = sum(len(c["lancamentos"]) for c in resultado["concorrentes"].values())
    total_descontinuados = sum(len(c["descontinuados"]) for c in resultado["concorrentes"].values())
    print(
        f"Lancamentos salvos em data/lancamentos_latest.json "
        f"({total_lancamentos} produtos novos, {total_descontinuados} sairam do catalogo)"
    )


if __name__ == "__main__":
    main()
