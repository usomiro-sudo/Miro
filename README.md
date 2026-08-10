# MIRO Intelligence

Dashboard simples de monitoramento de concorrentes para a MIRO (roupas fitness masculinas de corrida).

## O que faz

1. **Comparação direta de preços** com Seekdopa, Woom e Vorr, produto a produto (camiseta, meia, boné), com diferença percentual em relação ao preço MIRO.
2. **Painel de referência de mercado** (Nike, Adidas) — só tendência de preço/lançamentos de corrida masculina, sem comparação direta.

Roda sozinho: um GitHub Action agendado coleta os dados, gera o dashboard e publica no GitHub Pages. Depois da configuração inicial abaixo, não precisa mexer em nada no dia a dia.

## Como funciona por baixo dos panos

- **Preços do MIRO**: via [API oficial da Nuvemshop](https://tiendanube.github.io/api-documentation/intro) (não faz scraping da própria loja).
- **Preços dos concorrentes**: scraping leve das páginas de produto, extraindo o bloco padrão `schema.org/Product` (JSON-LD) que a maioria das lojas já inclui para SEO — mais robusto que depender de classes CSS que mudam a cada redesign de tema. Se a página não tiver esse bloco, cai num fallback simples de regex para achar o primeiro "R$ 000,00" (menos confiável — confira no dashboard).
- **Dados históricos**: cada execução também é anexada em `data/*_historico.jsonl`, então você acumula histórico de preços de graça via git.
- **Dashboard**: página HTML estática gerada por `scripts/build_dashboard.py`, publicada no GitHub Pages.

## Configuração inicial (única vez)

### 1. Token da Nuvemshop (preços do MIRO)

1. Crie um app privado em [dev.nuvemshop.com.br](https://dev.nuvemshop.com.br) para a sua própria loja e gere um access token com permissão de leitura de produtos.
2. No repositório do GitHub: **Settings → Secrets and variables → Actions**, adicione:
   - `NUVEMSHOP_STORE_ID`
   - `NUVEMSHOP_ACCESS_TOKEN`
3. Em `config/products.yaml`, preencha `nuvemshop_id` de cada produto com o ID do produto na Nuvemshop (aparece na URL do admin). Sem isso, o script usa `preco_manual` (editado à mão) como fallback.

### 2. URLs dos concorrentes (comparação direta)

Em `config/products.yaml`, para cada um dos 3 produtos, cole a URL da página do produto equivalente no Seekdopa, Woom e Vorr. Deixe em branco se não existir equivalente — o dashboard mostra "sem URL" nesse caso.

Isso é feito à mão de propósito: com só 3 produtos, é mais simples e confiável do que tentar casar produtos automaticamente.

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
python build_dashboard.py
open ../dashboard/index.html
```

## Limitações conhecidas (fase 1, de propósito simples)

- Sites com conteúdo carregado via JavaScript (comum em Nike/Adidas) podem não ter o bloco JSON-LD acessível via `requests` simples — o script avisa no log quando isso acontece ("considerar Playwright"). Não é crítico porque essa parte é só referência.
- Mapeamento de produto concorrente é manual (por design, dado o catálogo pequeno).
- Sem alertas automáticos (ex. "concorrente baixou o preço 20%") — pode ser adicionado depois se fizer sentido, mas fica fora do escopo do MVP.

## Estrutura

```
config/products.yaml     catálogo MIRO + URLs dos concorrentes
config/sites.yaml         config dos sites (bases, listagens de referência, request settings)
scripts/                  scraping + geração do dashboard
data/                     snapshots + histórico (JSON/JSONL)
dashboard/                HTML estático publicado no GitHub Pages
.github/workflows/        automação agendada
```
