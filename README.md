# MIRO Intelligence

Dashboard simples de monitoramento de concorrentes para a MIRO (roupas fitness masculinas de corrida).

## O que faz

1. **Comparação direta de preços** com Seekdopa, Woom e Vorr, produto a produto (camiseta, meia, boné), com diferença percentual em relação ao preço MIRO.
2. **Painel de tendências** (`dashboard/tendencias.html`) — leitura da PÁGINA PRINCIPAL desses mesmos 3 concorrentes (não o catálogo inteiro, não preço): título, descrição e headlines/banners em destaque na home, comparados com a leitura anterior pra ver o que mudou, mais os termos que mais aparecem nos destaques recentes. É leitura de produto/marketing pra apoiar projeção de tendência do MIRO.
3. **Painel de referência de mercado** (Nike, Adidas) — só tendência de preço/lançamentos de corrida masculina, sem comparação direta.

Roda sozinho: um GitHub Action agendado coleta os dados, gera o dashboard e publica no GitHub Pages. Depois da configuração inicial abaixo, não precisa mexer em nada no dia a dia — e dá pra forçar uma atualização a qualquer momento sem esperar o agendamento (ver "Rodar manualmente" abaixo).

## Como funciona por baixo dos panos

- **Preços do MIRO**: via [API oficial da Nuvemshop](https://tiendanube.github.io/api-documentation/intro) (não faz scraping da própria loja).
- **Preços dos concorrentes**: scraping leve, extraindo o bloco padrão `schema.org/Product` (JSON-LD) que a maioria das lojas já inclui para SEO — mais robusto que depender de classes CSS que mudam a cada redesign de tema. Se a página não tiver esse bloco, cai num fallback simples de regex para achar o primeiro "R$ 000,00" (menos confiável — confira no dashboard).
- **Pareamento com o produto MIRO equivalente**: automático. O sistema varre o catálogo de "corrida masculina" de cada concorrente (com paginação), classifica cada item numa categoria (camiseta/meia/boné) pelo nome, e escolhe o mais parecido com o produto MIRO da mesma categoria por similaridade de texto. Cada resultado carrega um % de confiança do match — se um concorrente tira ou adiciona um produto do catálogo, a próxima execução já reflete isso sozinha, sem editar nada.
- **Tendências**: `scripts/monitor_tendencias.py` é independente do scraping de preço — lê só a home de cada concorrente (`comparacao.<site>.base_url`), extrai título, meta descrição, headlines (h1/h2/h3) e alt de banners/imagens, e compara com a leitura anterior (`data/tendencias_historico.jsonl`) pra marcar o que é novo ou sumiu. Também conta a frequência de palavras nos destaques dos últimos 60 dias como sinal simples de tendência. É heurística (contagem de palavra + diff de texto), não NLP — serve de ponto de partida, não de conclusão.
- **Dados históricos**: cada execução também é anexada em `data/*_historico.jsonl`, então você acumula histórico de preços/tendências de graça via git.
- **Dashboard**: páginas HTML estáticas geradas por `scripts/build_dashboard.py` (`index.html` e `tendencias.html`), publicadas no GitHub Pages.

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

## Rodar manualmente ("botão de atualizar")

Não precisa esperar o agendamento automático (seg/qui). O GitHub já tem um botão pra isso:

**Actions → Atualizar dashboard MIRO Intelligence → Run workflow** (canto direito). Clique, confirme, e em 1-2 minutos o dashboard e o painel de tendências estão atualizados no GitHub Pages com os dados mais recentes.

Para rodar local em vez disso:

```bash
pip install -r requirements.txt
cp .env.example .env   # preencha e faça `export $(cat .env | xargs)` ou use direnv
cd scripts
python scrape_competitors.py
python scrape_reference.py
python monitor_tendencias.py
python build_dashboard.py
open ../dashboard/index.html        # comparação de preços
open ../dashboard/tendencias.html   # tendências
```

O painel de tendências só mostra "o que é novo/o que sumiu" a partir da <strong>segunda</strong> execução de `monitor_tendencias.py` — a primeira só estabelece a linha de base de comparação.

## Limitações conhecidas (fase 1, de propósito simples)

- Sites com conteúdo carregado via JavaScript (comum em Nike/Adidas, mas pode acontecer com qualquer concorrente) podem não ter o bloco JSON-LD acessível via `requests` simples — o script avisa no log quando isso acontece ("considerar Playwright") e o site fica sem matching automático até revisar. Não usamos Playwright de propósito, pra manter o scraping leve e rápido no GitHub Actions.
- O pareamento automático é por similaridade de nome — pode errar (ex. confundir "meia de corrida" com "meia de compressão" se os nomes forem parecidos). O % de confiança no dashboard existe justamente pra sinalizar isso; use `concorrentes_override` em `config/products.yaml` para corrigir um caso pontual.
- A paginação assume o padrão `?page=N` (comum em Nuvemshop/Shopify/Loja Integrada). Se algum concorrente usar outro esquema, só a primeira página do catálogo é lida.
- Sem alertas automáticos (ex. "concorrente baixou o preço 20%") — pode ser adicionado depois se fizer sentido, mas fica fora do escopo do MVP.
- "Termos em alta" é contagem de palavra nos destaques da home (headlines/banners), sem stopwords óbvias — não entende sinônimo, plural irregular ou contexto. É sinal, não veredito; leia com espírito crítico.
- O painel de tendências lê só a home (`base_url`) — não entra em categoria/produto. Se a marca destacar pouca coisa na própria home (site minimalista, tudo carregado via JS), o painel vai ter pouco headline/banner pra mostrar. Isso é esperado, não é erro.
- "Novo" e "sumiu" nos destaques são definidos por comparação de texto exato com a execução anterior — troca de uma palavra no banner já conta como "sumiu o antigo, apareceu o novo", mesmo sendo o mesmo banner com texto levemente diferente.

## Estrutura

```
config/products.yaml     catálogo MIRO + URLs dos concorrentes
config/sites.yaml         config dos sites (bases, listagens de referência, request settings)
scripts/                  scraping + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
