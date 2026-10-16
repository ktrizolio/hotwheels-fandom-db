# Integração: como usar a DB Hot Wheels em outros apps

> Contrato de dados da v6. Para entender **como** os dados são gerados, veja [`DOCUMENTACAO_TECNICA.md`](DOCUMENTACAO_TECNICA.md).

## 1. Onde estão os dados

```
hotwheels-fandom-db/saida/<AAAA-MM-DD>/
├── hotwheels_db_v6.jsonl   ← principal: 1 linha por versão (~57 mil)
├── castings_v6.jsonl       ← 1 linha por modelo (~6,6 mil)
├── containers_v6.jsonl     ← packs, pistas, séries e listas, com seus membros
└── relatorio_build.json    ← estatísticas do build
```

- Use sempre a pasta de **data mais recente**. O Manager recebe uma cópia em `Hotwheels_Manager/hotwheels-manager/data/wiki_v6.jsonl`.
- Formato: **JSON Lines**, UTF-8 sem BOM, 1 objeto por linha. Strings vazias (`""`) significam "sem informação"; `null` aparece só em `col_num`/`col_total`.
- Os JSON Schemas estão em [`schemas/`](schemas/).

## 2. Modelo de dados

```
castings_v6 (title) 1 ───< N  hotwheels_db_v6 (casting)
containers_v6 (title) 1 ───< N  members[].casting_resolved ──> castings_v6.title
hotwheels_db_v6.pack  ── contém títulos de containers_v6 (separados por " | ")
```

### 2.1 `hotwheels_db_v6.jsonl`: versões

Os 10 primeiros campos são os do Hotwheels Manager. Os demais são extras.

| Campo | Tipo | Exemplo | Descrição |
|---|---|---|---|
| `id` | string | `1969-twin_mill-6258-spectraflame_aqua` | **chave pública** (ver §4) |
| `model_name` | string | `Twin Mill` | nome do modelo nesta versão |
| `release_year` | string `AAAA` ou `""` | `1969` | ano de lançamento |
| `series` | string | `Mainline`, `2011 Monster Jam Series - Travel Treads` | série/linha (+ subset) |
| `col_#` | string | `63/80`, `135` | número de colecionador como na wiki |
| `toy_#` | string | `6258`, `HXH02 / JFF66` | código Mattel; pode ter vários separados por " / " |
| `color` | string | `Spectraflame Aqua` | cor da carroceria |
| `tampo` | string | `Red, yellow & white HW logo` | decoração |
| `photo_url` | URL ou `""` | `https://static.wikia.nocookie.net/...` | foto da versão |
| `page_url` | URL | `https://hotwheels.fandom.com/wiki/Twin_Mill` | página de origem |
| `casting` | string | `Twin Mill` | título da página do modelo → `castings_v6.title` |
| `product_type` | enum | `vehicle` · `monster_truck` · `trackset` · `pack` | tipo de produto |
| `series_#` | string | `3/10` | posição na série |
| `segment` | string | `2006 Open Stock` | seção da lista anual ("List of AAAA") onde a versão aparece; só preenchido quando a série é vazia ou "Mainline" |
| `pack` | string | `Exotics 5-Pack \| SharkBite Bay` | packs/pistas em que esta versão saiu |
| `base` / `window` / `interior` / `wheel` / `country` | string | `ZAMAC` / `Clear` / `Black` / `5SP` / `Malaysia` | detalhes da versão |
| `notes` | string | | observações da wiki |
| `subset` | string | `Travel Treads` | subconjunto (monster trucks, mini collections) |
| `section` | string | `1969 Original Versions` | seção da página onde estava a tabela |
| `designer` | string | `Ira Gilford` | designer do casting |
| `year_raw` | string | `2022 / 2023`, `1998?` | ano original, quando não era um ano limpo |
| `col_num` / `col_total` | int ou `null` | `63` / `80` | `col_#` decomposto, quando no formato N/M |
| `image_file` | string | `Twinmill.jpg` | nome do arquivo na wiki |
| `series_page` | string | `1969 Hot Wheels` | página da série linkada |
| `source` | enum | ver abaixo | de onde a linha veio |
| `uid` | string (12 hex) | `0118d58e47db` | id interno do build, **não estável** |

Valores de `source`:

| Valor | Significado | Confiabilidade |
|---|---|---|
| `casting` | tabela de versões da página do modelo | alta |
| `casting_sem_template` | idem, em página sem `{{Casting}}` | alta |
| `list` / `series` | lista anual ou página de série (modelo sem página própria) | média |
| `pack` / `trackset` | carro de pack/pista sem versão correspondente no modelo | média (pode duplicar) |
| `monster_list` | lista anual de Monster Jam | média |
| `product` | pista/pack/protótipo sem tabela; só dados do infobox | baixa (sem cor) |

### 2.2 `castings_v6.jsonl`: modelos

| Campo | Descrição |
|---|---|
| `title` | título da página (chave) |
| `model_name` | nome no infobox |
| `designer`, `first_series`, `number`, `years`, `image_file` | parâmetros do `{{Casting}}` |
| `categories` | categorias da wiki (ano, marca, tipo de carroceria, licenciado…) |
| `page_url`, `product_type`, `n_versions` | URL, tipo e quantidade de versões na DB |

### 2.3 `containers_v6.jsonl`: packs, pistas, séries e listas

```json
{"title": "\"Real Riders\" Series (1995)", "type": "series", "page_url": "https://...",
 "members": [{"year": "1995", "model_name": "Dump Truck", "casting_resolved": "Peterbilt Dump Truck",
              "color": "", "toy_#": "13304", "col_#": "317", "series_#": "1/4", "section": ""}]}
```

`type` ∈ `pack`, `trackset`, `list`, `series`, `monster_list`. `casting_resolved` já tem os redirects aplicados.

## 3. Receitas

### 3.1 Python, sem dependências

```python
import json, glob, os

def ultima_saida(raiz="hotwheels-fandom-db/saida"):
    return sorted(glob.glob(os.path.join(raiz, "*")))[-1]

def ler_jsonl(caminho):
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

pasta = ultima_saida()
db = ler_jsonl(os.path.join(pasta, "hotwheels_db_v6.jsonl"))
por_id = {r["id"]: r for r in db}

# todas as versões de um modelo
twin = [r for r in db if r["casting"] == "Twin Mill"]
# busca por toy # (considera códigos múltiplos)
achar = lambda toy: [r for r in db if toy.upper() in r["toy_#"].upper().split(" / ")]
# só monster trucks de 2024
mt24 = [r for r in db if r["product_type"] == "monster_truck" and r["release_year"] == "2024"]
```

### 3.2 pandas

```python
import pandas as pd
df = pd.read_json(".../hotwheels_db_v6.jsonl", lines=True, dtype=False)
df.groupby("release_year").size()
```

### 3.3 JavaScript / Node

```js
import { readFileSync } from "node:fs";
const db = readFileSync("hotwheels_db_v6.jsonl", "utf8")
  .split("\n").filter(Boolean).map(JSON.parse);
const byId = new Map(db.map(r => [r.id, r]));
```

### 3.4 SQLite (para apps que preferem SQL)

Use o script [`exemplos/jsonl_para_sqlite.py`](exemplos/jsonl_para_sqlite.py): `python jsonl_para_sqlite.py <pasta_saida> hotwheels.db`. Ele cria as tabelas `versoes`, `castings`, `containers` e `membros`, com índices em `casting`, `toy_#`, `release_year` e `series`.

```sql
SELECT model_name, color, series FROM versoes WHERE "toy_#" LIKE '%HXH02%';
SELECT c.title, COUNT(*) FROM membros m JOIN containers c ON c.rowid = m.container_id
WHERE c.type = 'pack' GROUP BY c.title;
```

### 3.5 Chamar o scraper de dentro de outro app Python

```python
import sys; sys.path.insert(0, "hotwheels-fandom-db/scraper")
import baixar_wiki, hw_build, hw_parser

if __name__ == "__main__":            # obrigatório no Windows (usa multiprocessing)
    baixar_wiki.baixar("dados/2026-10-13")                      # opcional (internet)
    hw_build.build("dados/2026-10-13/dump.jsonl", "dados/2026-10-13/redirects.json",
                   "saida/2026-10-13")

# Parsear uma página isolada (ex.: wikitext obtido da API por outro app)
pagina = {"pageid": 1, "title": "Twin Mill", "categories": [], "wikitext": wikitext}
versoes, info = hw_parser.parse_casting(pagina)
tipo = hw_parser.classify(pagina)
```

Funções públicas e estáveis: `hw_parser.classify`, `parse_casting`, `parse_member_tables`, `clean`, `file_url`, `page_url`, `make_id`; `hw_build.build`; `baixar_wiki.baixar`; `atualizar_db.migrar`.

## 4. Regras para quem guarda referências (estoque, coleção, vendas)

1. **Guarde o `id`**, nunca o `uid`.
2. A cada build novo, valide os ids guardados. Para os que sumiram (a wiki corrigiu nome ou cor), use `atualizar_db.migrar(arquivo, linhas_db, redirects)`. A função gera `<arquivo>_v6.jsonl` com o id novo e grava o antigo em `id_antigo`, mantendo os campos próprios do seu app (preço, quantidade…).
3. Ids com `~xxxxxx` são variações (rodas/base/país) que compartilham o id base. Mostre `wheel`, `base` e `country` para o usuário distinguir.
4. Guarde também `page_url` + `release_year` + `toy_#`, que permitem reencontrar o item mesmo se o id mudar.

## 5. Boas práticas de consumo

- Trate `""` como desconhecido e não use para ordenar/filtrar ano sem checar.
- Para validar `toy_#`: `^[A-Z0-9]{3,6}(-\d+)?$` por código (separe por " / "). Valores fora disso são erros herdados da wiki.
- Imagens: `photo_url` aponta para o CDN da Fandom (`static.wikia.nocookie.net`). Faça cache local, mande um `User-Agent` e trate 404.
- Atribuição: o conteúdo vem da Hot Wheels Wiki (Fandom), sob licença **CC BY-SA**, e esta base é distribuída sob **CC BY-SA 4.0**. Se publicar os dados ou fotos, cite a fonte (`page_url`) e use a mesma licença; veja o modelo de citação no [README](../README.md#licença).
- Atualização: rode `ATUALIZAR_DB.bat` no máximo algumas vezes por mês. A wiki muda pouco por dia.
