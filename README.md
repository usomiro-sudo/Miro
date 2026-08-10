# MIRO Intelligence

Dashboard simples de monitoramento de concorrentes para a MIRO (roupas fitness masculinas de corrida).

## O que faz

1. **Comparação direta de preços** com Seekdopa, Woom e Vorr, produto a produto (camiseta, meia, boné), com diferença percentual em relação ao preço MIRO.
2. **Painel de lançamentos & tendências** (`dashboard/lancamentos.html`) — desses mesmos 3 concorrentes, mas sem falar de preço: o que entrou/saiu do catálogo desde a última coleta e quais termos aparecem com mais frequência nos nomes dos produtos recentes. É leitura de produto/marketing pra apoiar projeção de tendência do MIRO, não comparação.
3. **Painel de referência de mercado** (Nike, Adidas) — só tendência de preço/lançamentos de corrida masculina, sem comparação direta.

Roda sozinho: um GitHub Action agendado coleta os dados, gera o dashboard e publica no GitHub Pages. Depois da configuração inicial abaixo, não precisa mexer em nada no dia a dia.

## Como funciona por baixo dos panos

- **Preços do MIRO**: via [API oficial da Nuvemshop](https://tiendanube.github.io/api-documentation/intro) (não faz scraping da própria loja).
- **Preços dos concorrentes**: scraping leve, extraindo o bloco padrão `schema.org/Product` (JSON-LD) que a maioria das lojas já inclui para SEO — mais robusto que depender de classes CSS que mudam a cada redesign de tema. Se a página não tiver esse bloco, cai num fallback simples de regex para achar o primeiro "R$ 000,00" (menos confiável — confira no dashboard).
- **Pareamento com o produto MIRO equivalente**: automático. O sistema varre o catálogo de "corrida masculina" de cada concorrente (com paginação), classifica cada item numa categoria (camiseta/meia/boné) pelo nome, e escolhe o mais parecido com o produto MIRO da mesma categoria por similaridade de texto. Cada resultado carrega um % de confiança do match — se um concorrente tira ou adiciona um produto do catálogo, a próxima execução já reflete isso sozinha, sem editar nada.
- **Lançamentos & tendências**: `scripts/scrape_competitors.py` já salva o catálogo completo de cada concorrente (não só os produtos pareados) em `data/catalogo_historico.jsonl`. `scripts/detect_lancamentos.py` compara o snapshot mais novo com o anterior pra achar produto novo/que saiu do catálogo, e conta a frequência de palavras nos nomes dos produtos dos últimos 60 dias como sinal simples de tendência. É heurística (contagem de palavra), não NLP — serve de ponto de partida, não de conclusão.
- **Dados históricos**: cada execução também é anexada em `data/*_historico.jsonl`, então você acumula histórico de preços/catálogo/lançamentos de graça via git.
- **Dashboard**: páginas HTML estáticas geradas por `scripts/build_dashboard.py` (`index.html` e `lancamentos.html`), publicadas no GitHub Pages.

## Configuração inicial (única vez)

### 1. Token da Nuvemshop (preços do MIRO)

1. Crie um app privado em [dev.nuvemshop.com.br](https://dev.nuvemshop.com.br) para a sua própria loja e gere um access token com permissão de leitura de produtos.
2. No repositório do GitHub: **Settings → Secrets and variables → Actions**, adicione:
   - `NUVEMSHOP_STORE_ID`
   - `NUVEMSHOP_ACCESS_TOKEN`
3. Em `config/products.yaml`, preencha `nuvemshop_id` de cada produto com o ID do produto na Nuvemshop (aparece na URL do admin). Sem isso, o script usa `preco_manual` (editado à mão) como fallback.

### 2. Catálogo dos concorrentes (comparação automática)

Em `config/sites.yaml`, preencha `listagem_url` de cada concorrente (Seekdopa, Woom, Vorr) com a URL da categoria "corrida masculina" (ou o catálogo mais próximo disso) na loja deles. O sistema varre essa listagem sozinho a cada execução e faz o pareamento — não precisa colar URL de produto nenhuma.

Cada produto em `config/products.yaml` já vem com uma `categoria` (camiseta/meia/bone) e `palavras_chave` opcionais que ajudam o matching. Se o pareamento automático errar para algum produto/concorrente específico, preencha `concorrentes_override` daquele produto com a URL certa — ela passa a ser usada no lugar do match automático até você tirar.

No dashboard, cada preço de concorrente mostra um "match X%" indicando a confiança do pareamento automático (verde = alta, amarelo = média, vermelho = baixa) — vale conferir de vez em quando, principalmente os matches em vermelho.

### 3. URLs de referência (Nike/Adidas)

Em `config/sites.yaml`, preencha `listagem_url` de cada marca com a URL da categoria "corrida masculina" no site deles.

### 4. Ativar o GitHub Pages

**Settings → Pages → Source: GitHub Actions**. Depois da primeira execução do workflow, o link do dashboard aparece ali.

## Rodar manualmente

Além do agendamento automático (seg/qui), dá pra disparar a qualquer momento em **Actions → Atualizar dashboard MIRO Intelligence → Run workflow**.

Para rodar local:

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha e faça `export $(cat .env | xargs)` ou use direnv
cd scripts
python scrape_competitors.py
python scrape_reference.py
python detect_lancamentos.py
python build_dashboard.py
open ../dashboard/index.html        # comparação de preços
open ../dashboard/lancamentos.html  # lançamentos & tendências
```

O painel de lançamentos só mostra "o que é novo/o que saiu" a partir da <strong>segunda</strong> execução de `scrape_competitors.py` — a primeira só estabelece a linha de base de comparação.

## Limitações conhecidas (fase 1, de propósito simples)

- Sites com conteúdo carregado via JavaScript (comum em Nike/Adidas, mas pode acontecer com qualquer concorrente) podem não ter o bloco JSON-LD acessível via `requests` simples — o script avisa no log quando isso acontece ("considerar Playwright") e o site fica sem matching automático até revisar. Não usamos Playwright de propósito, pra manter o scraping leve e rápido no GitHub Actions.
- O pareamento automático é por similaridade de nome — pode errar (ex. confundir "meia de corrida" com "meia de compressão" se os nomes forem parecidos). O % de confiança no dashboard existe justamente pra sinalizar isso; use `concorrentes_override` em `config/products.yaml` para corrigir um caso pontual.
- A paginação assume o padrão `?page=N` (comum em Nuvemshop/Shopify/Loja Integrada). Se algum concorrente usar outro esquema, só a primeira página do catálogo é lida.
- Sem alertas automáticos (ex. "concorrente baixou o preço 20%") — pode ser adicionado depois se fizer sentido, mas fica fora do escopo do MVP.
- "Termos em alta" é contagem de palavra no nome do produto, sem stopwords óbvias — não entende sinônimo, plural irregular ou contexto. É sinal, não veredito; leia com espírito crítico.
- "Lançamento" e "descontinuado" são definidos por comparação com a execução anterior. Se uma coleta vier com catálogo vazio (site fora do ar, mudança de layout), `detect_lancamentos.py` detecta isso e pula a comparação daquele concorrente nessa execução (em vez de marcar o catálogo inteiro como "descontinuado" por engano) — o dashboard mostra um aviso quando isso acontece.

## Estrutura

```
config/products.yaml     catálogo MIRO + URLs dos concorrentes
config/sites.yaml         config dos sites (bases, listagens de referência, request settings)
scripts/                  scraping + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
