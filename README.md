# MIRO Intelligence

Dashboard simples de monitoramento de concorrentes para a MIRO (roupas fitness masculinas de corrida).

## O que faz

Acompanha as **home pages** de Seekdopa, Woom, Vorr, Nike e Adidas e sinaliza tendências — sem comparação de preço produto a produto:

1. **Promoções / banners** — trechos de texto na home que batem com palavras-chave como "% off", "desconto", "cupom", "frete grátis" etc.
2. **Lançamentos em destaque** — trechos que batem com palavras-chave como "novo", "lançamento", "chegou" etc.

Cada coleta é comparada com a anterior: itens que apareceram desde a última execução ganham a etiqueta "novo"; promoções que desapareceram aparecem riscadas como encerradas.

Roda sozinho: um GitHub Action agendado coleta os dados, gera o dashboard e publica no GitHub Pages. Depois da configuração inicial abaixo, não precisa mexer em nada no dia a dia.

## Como funciona por baixo dos panos

- **Coleta**: `requests` busca o HTML de cada home page configurada; nenhuma autenticação é necessária, é tudo público.
- **Detecção**: `scripts/scrape_homepage_trends.py` varre os textos de links, títulos e blocos da página e classifica cada trecho contra as listas de palavras-chave em `config/sites.yaml` (seção `deteccao`) — ajustáveis sem mexer em código.
- **Dados históricos**: cada execução é anexada em `data/tendencias_historico.jsonl`, o que permite comparar a coleta atual com a anterior e detectar novidades.
- **Dashboard**: página HTML estática gerada por `scripts/build_dashboard.py`, publicada no GitHub Pages.

## Configuração inicial (única vez)

### 1. Home pages dos concorrentes

Em `config/sites.yaml`, confira/ajuste `home_url` de cada concorrente (Seekdopa, Woom, Vorr, Nike, Adidas).

### 2. Palavras-chave de detecção

Ainda em `config/sites.yaml`, ajuste as listas `deteccao.promocoes` e `deteccao.lancamentos` conforme o que você quer captar — são comparadas em minúsculas contra o texto da home.

### 3. Ativar o GitHub Pages

**Settings → Pages → Source: GitHub Actions**. Depois da primeira execução do workflow, o link do dashboard aparece ali.

## Rodar manualmente

Além do agendamento automático (seg/qui), dá pra disparar a qualquer momento em **Actions → Atualizar dashboard MIRO Intelligence → Run workflow**.

Para rodar local:

```bash
pip install -r requirements.txt
cd scripts
python scrape_homepage_trends.py
python build_dashboard.py
open ../dashboard/index.html
```

## Limitações conhecidas (fase 1, de propósito simples)

- Sites com conteúdo carregado via JavaScript (comum em Nike/Adidas) podem não ter o texto acessível via `requests` simples — o script avisa no log quando isso acontece ("considerar Playwright"). O dashboard sinaliza esses casos como "não foi possível coletar".
- Detecção por palavra-chave é heurística: pode ter falso positivo (ex. "novo" em um contexto sem relação com lançamento) — o dashboard existe para dar uma visão rápida, não uma verdade absoluta; use os links para conferir.
- Sem alertas automáticos por e-mail/Slack — pode ser adicionado depois se fizer sentido, mas fica fora do escopo do MVP.

## Estrutura

```
config/sites.yaml         home pages monitoradas + palavras-chave de detecção + request settings
scripts/                  scraping + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
