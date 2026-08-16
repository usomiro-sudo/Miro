# MIRO Intelligence

Dashboard simples de monitoramento de concorrentes para a MIRO (roupas fitness masculinas de corrida).

## O que faz

O dashboard tem duas abas:

1. **Tendências dos concorrentes** — acompanha as **home pages** de Seekdopa, Woom, Vorr, Nike e Adidas (sem comparação de preço produto a produto):
   - **Promoções / banners** — trechos de texto na home que batem com palavras-chave como "% off", "desconto", "cupom", "frete grátis" etc.
   - **Lançamentos em destaque** — trechos que batem com palavras-chave como "novo", "lançamento", "chegou" etc.
   - Cada coleta é comparada com a anterior: itens que apareceram desde a última execução ganham a etiqueta "novo"; promoções que desapareceram aparecem riscadas como encerradas.
2. **Provas de corrida** — lista provas de **meia maratona (21km)** e **maratona (42km)** nos próximos 12 meses, coletadas do [Corridinhas](https://www.corridinhas.com.br). Outras distâncias (5km, 10km etc.) são ignoradas de propósito.

O topo da página sempre mostra quando os dados foram coletados pela última vez (horário de Brasília).

Roda sozinho: um GitHub Action agendado coleta os dados, gera o dashboard e publica no GitHub Pages. Depois da configuração inicial abaixo, não precisa mexer em nada no dia a dia.

## Como funciona por baixo dos panos

- **Coleta**: `requests` busca o HTML de cada página configurada; nenhuma autenticação é necessária, é tudo público.
- **Tendências**: `scripts/scrape_homepage_trends.py` varre os textos de links, títulos e blocos da página e classifica cada trecho contra as listas de palavras-chave em `config/sites.yaml` (seção `deteccao`) — ajustáveis sem mexer em código.
- **Provas**: `scripts/scrape_provas.py` tenta primeiro dados estruturados `schema.org/Event` na página; se não achar, cai num fallback que varre links e o texto ao redor procurando data + distância ("21km"/"meia maratona" ou "42km"/"maratona"). Provas fora da janela configurada (`provas.janela_meses` em `config/sites.yaml`) ou sem distância 21km/42km detectada são descartadas.
- **Dados históricos**: cada execução é anexada em `data/*_historico.jsonl`, o que permite comparar a coleta atual com a anterior (usado hoje só pelo painel de tendências, pra detectar novidades).
- **Dashboard**: página HTML estática gerada por `scripts/build_dashboard.py`, publicada no GitHub Pages.

## Configuração inicial (única vez)

### 1. Home pages dos concorrentes

Em `config/sites.yaml`, confira/ajuste `home_url` de cada concorrente (Seekdopa, Woom, Vorr, Nike, Adidas).

### 2. Palavras-chave de detecção

Ainda em `config/sites.yaml`, ajuste as listas `deteccao.promocoes` e `deteccao.lancamentos` conforme o que você quer captar — são comparadas em minúsculas contra o texto da home.

### 3. Fonte e janela das provas

Em `config/sites.yaml`, seção `provas`: `fonte.url` (hoje Corridinhas) e `janela_meses` (hoje 12).

### 4. Ativar o GitHub Pages

**Settings → Pages → Source: GitHub Actions**. Depois da primeira execução do workflow, o link do dashboard aparece ali.

## Rodar manualmente

Além do agendamento automático (todo dia às 4h de Brasília), dá pra disparar a qualquer momento em **Actions → Atualizar dashboard MIRO Intelligence → Run workflow**.

Para rodar local:

```bash
pip install -r requirements.txt
cd scripts
python scrape_homepage_trends.py
python scrape_provas.py
python build_dashboard.py
open ../dashboard/index.html
```

## Limitações conhecidas (fase 1, de propósito simples)

- Sites com conteúdo carregado via JavaScript (comum em Nike/Adidas) podem não ter o texto acessível via `requests` simples — o script avisa no log quando isso acontece ("considerar Playwright"). O dashboard sinaliza esses casos como "não foi possível coletar".
- Detecção por palavra-chave é heurística: pode ter falso positivo (ex. "novo" em um contexto sem relação com lançamento) — o dashboard existe para dar uma visão rápida, não uma verdade absoluta; use os links para conferir.
- O scraper de provas (`scrape_provas.py`) foi escrito sem conseguir inspecionar `corridinhas.com.br` ao vivo (bloqueio de rede do ambiente de desenvolvimento) — as regras de data/distância são best-effort e podem precisar de ajuste depois de ver o resultado da primeira coleta real. Se o painel de provas vier vazio mesmo devendo ter provas, confira o log do workflow.
- Sem alertas automáticos por e-mail/Slack — pode ser adicionado depois se fizer sentido, mas fica fora do escopo do MVP.

## Estrutura

```
config/sites.yaml         concorrentes, palavras-chave de detecção, fonte/janela de provas, request settings
scripts/                  scraping + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
