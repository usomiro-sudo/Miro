"""Utilitários compartilhados: fetch de página."""
import time
from datetime import datetime, timezone

import requests


def fetch_html(url: str, user_agent: str, timeout: int) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        print(f"  [aviso] falha ao buscar {url}: {exc}")
        return None


def polite_sleep(seconds: float) -> None:
    time.sleep(seconds)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
