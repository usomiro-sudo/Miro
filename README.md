# MIRO Intelligence

Painel simples de tendências dos concorrentes da MIRO (roupas fitness masculinas de corrida): Seekdopa, Woom e Vorr.

## O que faz

Lê a **página principal** de cada concorrente — título, meta descrição, headlines/banners em destaque — e compara com a leitura anterior pra apontar o que é novo ou saiu de destaque, mais os termos que mais aparecem nos destaques recentes. É leitura de produto/marketing pra apoiar projeção de tendência do MIRO, não comparação de preço.

Roda sozinho: um GitHub Action agendado coleta os dados, gera o painel e publica no GitHub Pages. Não precisa mexer em nada no dia a dia — e dá pra forçar uma atualização a qualquer momento sem esperar o agendamento (ver "Rodar manualmente" abaixo).

## Como funciona por baixo dos panos

- **Leitura da home**: `scripts/monitor_tendencias.py` lê `base_url` de cada concorrente (`config/sites.yaml`), extrai título, meta descrição, headlines (h1/h2/h3) e alt de banners/imagens, e compara com a leitura anterior (`data/tendencias_historico.jsonl`) pra marcar o que é novo ou sumiu.
- **Termos em alta**: contagem de frequência de palavras nos destaques dos últimos 60 dias, sem stopwords óbvias — heurística simples (contagem de palavra + diff de texto), não NLP. Serve de ponto de partida, não de conclusão.
- **Dados históricos**: cada execução é anexada em `data/tendencias_historico.jsonl`, então você acumula histórico de graça via git.
- **Dashboard**: página HTML estática gerada por `scripts/build_dashboard.py`, publicada no GitHub Pages.

## Configuração inicial (única vez)

### 1. Concorrentes monitorados

`config/sites.yaml` já vem com `base_url` de Seekdopa, Woom e Vorr preenchido — não precisa mexer, a menos que um desses endereços mude.

### 2. Ativar o GitHub Pages

**Settings → Pages → Source: GitHub Actions**. Depois da primeira execução do workflow, o link do painel aparece ali.

## Rodar manualmente ("botão de atualizar")

Não precisa esperar o agendamento automático (seg/qui). O GitHub já tem um botão pra isso:

**Actions → Atualizar painel de tendências MIRO Intelligence → Run workflow** (canto direito). Clique, confirme, e em menos de 1 minuto o painel está atualizado no GitHub Pages com os dados mais recentes.

Para rodar local em vez disso:

```bash
pip install -r requirements.txt
cd scripts
python monitor_tendencias.py
python build_dashboard.py
open ../dashboard/index.html
```

O painel só mostra "o que é novo/o que sumiu" a partir da <strong>segunda</strong> execução de `monitor_tendencias.py` — a primeira só estabelece a linha de base de comparação.

## Limitações conhecidas (de propósito simples)

- "Termos em alta" é contagem de palavra nos destaques da home (headlines/banners), sem stopwords óbvias — não entende sinônimo, plural irregular ou contexto. É sinal, não veredito; leia com espírito crítico.
- O painel lê só a home (`base_url`) — não entra em categoria/produto nem em catálogo. Se a marca destacar pouca coisa na própria home (site minimalista, tudo carregado via JS), o painel vai ter pouco headline/banner pra mostrar. Isso é esperado, não é erro.
- "Novo" e "sumiu" nos destaques são definidos por comparação de texto exato com a execução anterior — troca de uma palavra no banner já conta como "sumiu o antigo, apareceu o novo", mesmo sendo o mesmo banner com texto levemente diferente.

## Estrutura

```
config/sites.yaml         concorrentes monitorados (base_url) + config de coleta
scripts/                  scraping da home + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
