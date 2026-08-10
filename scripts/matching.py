"""Categorização e matching automático de produtos de concorrentes, sem depender
de URL fixa: classifica cada item do catálogo do concorrente por categoria (via
palavra-chave) e, dentro da mesma categoria, acha o mais parecido com o produto
MIRO (via similaridade de texto no nome), com um score de confiança.

Isso é inerentemente impreciso (nomes de produtos variam muito entre lojas) —
por isso todo resultado carrega o score, e o dashboard mostra o nível de
confiança em vez de fingir uma correspondência exata.
"""
import re
import unicodedata
from difflib import SequenceMatcher

CATEGORIAS_KEYWORDS = {
    "camiseta": ["camiseta", "camisa", "regata", "top", "blusa", "manga longa", "manga curta"],
    "meia": ["meia", "meias"],
    "bone": ["bone", "viseira"],
}

# Abaixo desse score, o match é descartado (melhor "sem equivalente" do que um
# palpite ruim mostrado como se fosse confiável).
SCORE_MINIMO = 0.2


def _normalizar(texto: str | None) -> str:
    texto = texto or ""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", texto.lower()).strip()


def categorizar(nome: str) -> str | None:
    """Classifica um nome de produto do concorrente em uma categoria conhecida.

    Retorna None se nenhuma palavra-chave bater (produto fora do escopo monitorado,
    ex. tênis, shorts, garrafinha — não é erro, só não é uma das 3 categorias hoje).
    """
    norm = _normalizar(nome)
    for categoria, keywords in CATEGORIAS_KEYWORDS.items():
        if any(kw in norm for kw in keywords):
            return categoria
    return None


def _similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio()


def nivel_confianca(score: float) -> str:
    if score >= 0.6:
        return "alta"
    if score >= 0.35:
        return "media"
    return "baixa"


def melhor_match(nome_miro: str, palavras_chave_miro: list[str], candidatos: list[dict]) -> tuple[dict | None, float]:
    """Entre os candidatos (já filtrados pela mesma categoria), acha o mais parecido
    com o produto MIRO. Combina similaridade textual do nome com um pequeno bônus por
    palavra-chave extra (ex: "corrida", "dry-fit") presente no nome do concorrente.
    """
    melhor = None
    melhor_score = 0.0
    for candidato in candidatos:
        nome_candidato = candidato.get("nome_site") or ""
        score = _similaridade(nome_miro, nome_candidato)
        norm_candidato = _normalizar(nome_candidato)
        bonus = sum(0.05 for kw in palavras_chave_miro if _normalizar(kw) in norm_candidato)
        score = min(1.0, score + bonus)
        if score > melhor_score:
            melhor, melhor_score = candidato, score
    if melhor is not None and melhor_score < SCORE_MINIMO:
        return None, 0.0
    return melhor, melhor_score
