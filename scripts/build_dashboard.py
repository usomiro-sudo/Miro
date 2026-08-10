"""Gera dashboard/index.html estatico a partir dos dados coletados."""
import json
import os

from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(BASE_DIR, "data")
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")


def load_json(name: str) -> dict | None:
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_brl(value) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def main() -> None:
    comparacao = load_json("comparacao_latest.json")
    referencia = load_json("referencia_latest.json")
    lancamentos = load_json("lancamentos_latest.json")

    env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, "scripts", "templates")))
    env.filters["brl"] = fmt_brl

    os.makedirs(DASHBOARD_DIR, exist_ok=True)

    template = env.get_template("dashboard.html.j2")
    html = template.render(comparacao=comparacao, referencia=referencia)
    with open(os.path.join(DASHBOARD_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard gerado em dashboard/index.html")

    template_lancamentos = env.get_template("lancamentos.html.j2")
    html_lancamentos = template_lancamentos.render(lancamentos=lancamentos)
    with open(os.path.join(DASHBOARD_DIR, "lancamentos.html"), "w", encoding="utf-8") as f:
        f.write(html_lancamentos)
    print(f"Painel de lançamentos gerado em dashboard/lancamentos.html")


if __name__ == "__main__":
    main()
