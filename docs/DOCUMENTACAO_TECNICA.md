# Scraper Hot Wheels Fandom (v6): documentação técnica

> Público: quem vai manter o scraper ou entender como os dados são gerados.
> Para **consumir** a DB em outro app, veja [`INTEGRACAO.md`](INTEGRACAO.md).

## 1. Visão geral

O scraper monta uma base de dados de todas as versões de miniaturas Hot Wheels documentadas na [Hot Wheels Wiki (Fandom)](https://hotwheels.fandom.com).

Ele **não** faz scraping de HTML. A Fandom roda MediaWiki, e o scraper usa a API oficial (`/api.php`) para baixar o **wikitext**, o texto-fonte de cada página. O processamento acontece **offline**, sobre esse arquivo.

```
┌──────────────┐   API MediaWiki    ┌──────────────────┐   parse local    ┌─────────────────────┐
│ Fandom wiki  │ ─────────────────▶ │ dados/<data>/    │ ───────────────▶ │ saida/<data>/       │
│ ~11.250 pág. │  ~230 requisições  │ dump.jsonl(.gz)  │  hw_parser.py    │ hotwheels_db_v6     │
└──────────────┘  baixar_wiki.py    │ redirects.json   │  hw_build.py     │ castings_v6         │
                                    └──────────────────┘                  │ containers_v6       │
                                                                          │ relatorio_build     │
                                                                          └─────────┬───────────┘
                                                                                    │ atualizar_db.py
                                                                                    ▼
                                                              Hotwheels Manager: data/wiki_v6.jsonl
                                                              + estoque/coleção migrados (*_v6.jsonl)
```

| Etapa | Arquivo | Precisa de internet | Tempo típico |
|---|---|---|---|
| 1. Download | `scraper/baixar_wiki.py` | sim | 3–6 min |
| 2. Parse + montagem | `scraper/hw_parser.py`, `scraper/hw_build.py` | não | ~1 min |
| 3. Entrega no Manager e migração do estoque | `scraper/atualizar_db.py` | não | segundos |

Atalhos com duplo clique: `ATUALIZAR_DB.bat` roda as etapas 1→3; `REMONTAR_SEM_BAIXAR.bat` roda 2→3 com o último dump.

Dependências: Python 3.10+, `requests` e `wikitextparser` (`scraper/requirements.txt`).

## 2. Por que API + wikitext em vez de HTML

| Problema no HTML (v1–v5, Scrapy) | Como o wikitext resolve |
|---|---|
| `td:nth-child(n)` ignorava `rowspan`/`colspan` → colunas trocadas (945 páginas) | `wikitextparser.Table.data(span=True)` expande as células mescladas |
| `::text` pegava só o 1º nó de texto → "Spectraflame Aqua" virava "Aqua" | o texto da célula é limpo inteiro (links viram o texto exibido) |
| 1 requisição por página, crawling por links | 50 páginas por requisição, lista completa via `allpages` |
| Tipo de página adivinhado por cabeçalhos | o template `{{Casting}}` e as categorias identificam o tipo |

## 3. Etapa 1: download (`baixar_wiki.py`)

Função principal: `baixar(pasta, log=print, imagens=False)`.

| Passo | Chamada da API | Saída |
|---|---|---|
| Listar páginas (namespace 0, sem redirects) + categorias | `generator=allpages&gapfilterredir=nonredirects&prop=categories` | memória |
| Wikitext em lotes de 50 | `prop=revisions&rvprop=content\|timestamp&rvslots=main&pageids=…` (POST) | `dump.jsonl` |
| Redirects | `list=allpages&apfilterredir=redirects`, depois `redirects=1&titles=…` | `redirects.json` |
| (opcional) URLs de imagens | `list=allimages&aiprop=url` | `images.json` |

Boas práticas já embutidas: `User-Agent` identificado, `maxlag=5`, 1 requisição por vez com pausa de 0,2 s e até 6 tentativas com espera crescente.

### Formato do `dump.jsonl`

Uma página por linha:

```json
{"pageid": 1234, "title": "Twin Mill", "categories": ["1969 Hot Wheels", "..."],
 "timestamp": "2025-05-01T12:00:00Z", "wikitext": "{{casting|name=Twin Mill|...}} ..."}
```

`hw_build` aceita tanto `dump.jsonl` quanto `dump.jsonl.gz`.

## 4. Etapa 2: parser (`hw_parser.py`)

### 4.1 Classificação das páginas: `classify(page)`

As regras são avaliadas em ordem; vale a primeira que bater.

| Tipo | Regra | Uso | Qtd. (13/10/2026) |
|---|---|---|---|
| `casting` | a página começa com `{{Casting}}` | **fonte principal**: cada linha da tabela de versões vira um registro | 6.624 |
| `disambig` | template `{{Disambig}}` ou categoria *Disambiguation* | ignorada | 308 |
| `designer` | template `{{Designer}}` ou categoria *Designers* | ignorada (gerava duplicados) | 220 |
| `list` | título `List of AAAA …` | completa `col_#` e `series_#` | 132 |
| `monster_list` | título com "Monster Jam/Trucks" e um ano | completa `col_#`; cria linha só se o truck não tiver versões | 29 |
| `pack` | título com "N-Pack", "Gift Pack", "Box Set"… ou categoria de packs | liga o carro à versão (`pack`) | ~870 |
| `trackset` | categoria *Track Sets*/*Playsets* | idem | ~60 |
| `series` | categoria *Hot Wheels by Series* ou título com series/segment/First Editions… | completa `series_#` | ~2.060 |
| `other` | o resto | só gera linhas se tiver tabela típica de versões (ver 4.3) | ~940 |

> Atenção: categorias como *5-Packs* também marcam **páginas de carros** que saíram em 5-packs. Por isso `product_type()` só considera um item como pack/pista quando a página **não** tem tabela de versões.

### 4.2 Páginas `casting`: `parse_casting(page)`

1. Lê os parâmetros do `{{Casting}}`: `name`, `series` (1ª série), `number`, `years`, `designer`, `image`.
2. Percorre cada wikitable da página (com a seção/título `==…==` onde ela está) e expande os spans.
3. Mapeia os cabeçalhos para campos canônicos (`HEADER_MAP`):

| Campo | Cabeçalhos aceitos (normalizados) |
|---|---|
| `year` | year, years, year released |
| `series` | series, series / card, line, segment |
| `series_num` | series #, # in series |
| `col_num` | col #, coll #, col, collector #, `#` |
| `toy_num` | toy #, toy number, number, sku, tool # |
| `name` | name, casting name, casting, model name, truck name |
| `color` | color, body color, color / tampo |
| `tampo` | tampo(s), sticker(s), graphic(s), deco |
| `base` | base color / type e variações, chassis color / type |
| `window` / `interior` / `wheel` / `country` / `notes` | window color, interior color, wheel type, country, notes / variations… |
| `subset` | subset, mini collection, theme |
| `photo` / `photo_carded` | photo, image, photo loose / photo carded |

4. Só aceita tabelas que tenham a coluna **year**. Linhas sem ano e sem nenhum dado são descartadas.
5. Regras de série:
   - Se a tabela **não tem** coluna de série (caso típico dos monster trucks), a série é o **link do ano** (`[[2011 Monster Jam Series|2011]]` → "2011 Monster Jam Series"). Na falta dele, usa o título da seção ou a série do infobox.
   - `subset` diferente de "Standard" é anexado: "2011 Monster Jam Series - Travel Treads".
6. Ano: o 1º `19xx/20xx` da célula. O texto original vai para `year_raw` quando difere ("2022 / 2023", "1998?").
7. Foto: o 1º `[[File:…]]` da célula. Placeholders ("Image Not Available", "No image") são ignorados.

### 4.3 Páginas sem `{{Casting}}` com tabela de versões

Algumas páginas de modelo não usam o template (ex.: *'66 Ford Mustang*). Para `other` e `series` roda `parse_casting(page, strict=True)`, que aceita só tabelas com **year + color** e **sem** coluna de nome. Essas linhas recebem `source = "casting_sem_template"`.

### 4.4 Packs, pistas, listas e séries: `parse_member_tables(page, kind)`

Lê as tabelas que têm coluna de **nome** (casting name / model name / truck name) e gera "membros": quem está dentro do container. O ano vem da coluna `year`, do título da seção ou do título/categorias da página (`year_from_page`). O link da célula de nome identifica a página do modelo (`casting`).

### 4.5 Limpeza de células: `clean(cell)`

Na ordem: remove `<!-- -->` e `<ref>`, remove `[[File:]]`/`[[Category:]]`, troca `<br>` por " / ", remove templates `{{…}}` (inclusive aninhados), converte `[[a|b]]` em `b` e `[url texto]` em `texto`, remove tags HTML, decodifica entidades, remove `''`/`'''` e colapsa os espaços.

### 4.6 URLs

- Página: `https://hotwheels.fandom.com/wiki/<Título_com_underscores>` (`page_url()`).
- Imagem: caminho determinístico do MediaWiki, montado com o **md5 do nome do arquivo** (`file_url()`), sem nenhuma requisição extra:

```
https://static.wikia.nocookie.net/hotwheels/images/{md5[0]}/{md5[0:2]}/{Nome_Do_Arquivo}/revision/latest
```

## 5. Etapa 2b: montagem (`hw_build.py`)

`build(dump_path, redirects_path, out_dir, procs=None, log=print, images_path=None)`

1. **Parse paralelo** (`multiprocessing.Pool`) de todas as páginas.
2. **Produtos sem tabela:** páginas `{{Casting}}` sem tabela de versões (pistas, packs, protótipos não lançados) viram 1 registro com os dados do infobox (`source = "product"`).
3. **Índices:** por `(casting, ano)` e por `(ano, toy#)`. Toy # com mais de um código ("HXH02 / JFF66") é indexado por cada código.
4. **Junção de membros:** redirects resolvidos e regras avaliadas em ordem:
   1. mesmo **ano + toy #** (e mesmo casting, quando houver link) → match;
   2. o nome do container (sem ano, parênteses e "series") aparece em `series`, `notes` ou `series_page` da versão → match;
   3. **cor parecida** (Jaccard ≥ 0,5 sobre as palavras da cor, ignorando metalflake/spectraflame/metallic/pearl…) → match;
   4. só 1 versão naquele ano → match; para pack/pista, só 1 versão cuja série cite pack/multi/set/exclusive → match.
5. **Com match:** o container entra em `pack` (para pack/pista), e são preenchidos `col_#`, `series_#`, `segment` (das listas anuais) e a imagem, quando vazios.
6. **Sem match:** cria linha nova só quando a informação é nova:
   - `pack` / `trackset`: sempre;
   - `monster_list`: só se o truck não tiver versões naquele ano;
   - `series` / `list`: só se o modelo não tiver página própria (ou, em `list`, nenhuma versão naquele ano).
7. **Normalização:** toy # "N/A", "?" e "-" viram vazio; `col_#` "12/250" vira `col_num=12` e `col_total=250`; `pack` é a lista unida por " | ".
8. **IDs:** ver seção 7.
9. **Saída:** ordenada por `casting`, `release_year`, `uid`.

## 6. Arquivos de saída (`saida/<data>/`)

| Arquivo | Granularidade | Chave |
|---|---|---|
| `hotwheels_db_v6.jsonl` | 1 linha = 1 versão/lançamento | `id` |
| `castings_v6.jsonl` | 1 linha = 1 página de modelo | `title` |
| `containers_v6.jsonl` | 1 linha = 1 pack/pista/série/lista, com `members[]` | `title` + `type` |
| `relatorio_build.json` | estatísticas do build | — |

O dicionário completo de campos está em [`INTEGRACAO.md`](INTEGRACAO.md), e os JSON Schemas em [`schemas/`](schemas/).

## 7. Identificadores

| Campo | Formato | Estável entre builds? | Use para |
|---|---|---|---|
| `id` | `{ano}-{modelo}-{toy#}-{cor}` em minúsculas, espaços e `/` viram `_` | **sim**, enquanto ano/nome/toy#/cor não mudarem na wiki | chave pública; estoque e coleção |
| `id` com `~xxxxxx` | sufixo com 6 caracteres do `uid` | sim, enquanto a linha não mudar de posição | 2ª+ variação com o mesmo id base (rodas/base/país diferentes) |
| `uid` | sha1 de `pageid + nº da tabela + nº da linha` (12 hex) | **não**: muda se a wiki inserir linhas acima | referência dentro de um mesmo build |

O formato do `id` é o mesmo do Hotwheels Manager v1–v3, por isso o estoque antigo continua compatível. `atualizar_db.migrar()` reaponta itens cujo `id` não existe mais: busca por página + ano + toy # e desempata pela cor. O id original fica em `id_antigo`.

## 8. Resultado do build de 13/10/2026

| Métrica | DB antiga (Scrapy + Manager) | v6 |
|---|---|---|
| Linhas | 48.870 | 57.086 |
| Páginas cobertas | 6.044 | 6.917 |
| Monster trucks | 139 | 4.223 |
| Série preenchida | 96,2 % | 99,3 % |
| Cor preenchida | 85,2 % | 88,0 % |
| `col_#` preenchido | 27,8 % | 31,0 % |
| Ano válido | 97,8 % | 98,2 % |
| Itens do estoque reconhecidos | — | 139/139 |

Origem das linhas: casting 51.610 · series 2.320 · pack 982 · product 727 · monster_list 580 · trackset 454 · casting_sem_template 305 · list 108.

## 9. Limitações conhecidas

- **Erros da própria wiki** são herdados. Ex.: cabeçalho deslocado faz o país aparecer em `toy_#` ("Thailand"). Para filtrar, valide `toy_#` com `^[A-Z0-9]{3,6}(-\d+)?$`.
- `toy_#` vazio em ~18 % das linhas. É esperado em monster trucks, Leo/Índia, Code 3, protótipos e produtos.
- A junção de membros é heurística. Packs com cores descritas de forma muito diferente da página do modelo podem gerar uma linha extra (`source = "pack"`).
- `uid` não é estável entre builds (seção 7).
- Fotos: a URL é calculada. Se o arquivo citado no wikitext não existir na wiki, a URL dá 404.

## 10. Como estender

| Quero… | Onde mexer |
|---|---|
| Aceitar um cabeçalho novo | `HEADER_MAP` em `hw_parser.py` |
| Tratar um novo tipo de página | `classify()` + um parser novo; registrar o tipo em `KINDS_MEMBER` / `_work()` em `hw_build.py` |
| Mudar as regras de junção | bloco "junção de membros" em `build()` (funções `cont_key`, `similar`) |
| Adicionar um campo de saída | criar no dicionário em `parse_casting`/`parse_member_tables` e incluir na lista `order` em `build()` |
| Testar sem internet | `REMONTAR_SEM_BAIXAR.bat` (usa o último `dados/*/dump.jsonl(.gz)`) |

Depois de qualquer mudança, compare o `relatorio_build.json` novo com o anterior: totais de `rows`, `by_source`, `merge` e `n_errors`.
