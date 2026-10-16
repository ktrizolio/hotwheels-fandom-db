# Histórico: por que existe a v6

## Das versões 1 a 5 (Scrapy, HTML)

As primeiras versões eram um projeto Scrapy que lia o **HTML** das páginas da wiki:

1. um "descobridor de links" percorria a wiki a partir de algumas páginas iniciais e guardava as URLs de páginas com tabela "Year + Toy #";
2. um script de limpeza removia URLs repetidas;
3. o spider lia essas URLs, uma requisição por página, e gerava a base. A última versão (julho de 2025) tinha 39.553 linhas de 5.214 páginas;
4. depois, uma extração em lote dentro do Hotwheels Manager somou mais páginas e monster trucks, chegando a 48.870 linhas.

## Problemas encontrados na base antiga

| Problema | Causa | Impacto |
|---|---|---|
| Colunas desalinhadas ("Mario" no ano, "20222023") | `td:nth-child(n)` ignora rowspan (945 páginas de modelo usam) | dados trocados de coluna |
| Cor/tampo cortados ("Aqua" em vez de "Spectraflame Aqua") e 15% das cores vazias | `::text` pega só o primeiro nó de texto, sem os links | informação perdida |
| ~14% de duplicados lógicos | o mesmo carro vinha da página do modelo e da página de série/5-pack/designer, com nome diferente → ID diferente | buscas com repetição |
| Variações perdidas | o filtro descartava IDs iguais, e variações de roda/base/país têm o mesmo ID | versões sumiram |
| Monster trucks e pistas quase ausentes (139) | exigia a coluna "Toy #" | ~4.000 monster trucks fora |
| Foto "Image Not Available" e links `Special:Upload` | placeholder tratado como foto | foto inválida |
| Mesma página com URLs diferentes (`%27` vs `'`, `#âncora`) | URLs não normalizadas | 421 páginas duplicadas |
| Atualização sobrescrevia campos | registros com o mesmo ID vindos de outra página trocavam série e `page_url` | corrupção silenciosa |

## O que mudou na v6: API em vez de HTML

A Fandom roda MediaWiki, que tem uma API oficial (`/api.php`). Ela entrega o **wikitext**, o texto-fonte de cada página, com as tabelas, o infobox `{{Casting}}` e as categorias. Com isso:

- as ~11.250 páginas saem em cerca de **230 requisições** (50 por vez), contra 1 requisição por página no Scrapy;
- o "scraping" vira **parsing local** do arquivo baixado: dá para testar regras novas sem tocar no site;
- tabelas com células mescladas (rowspan/colspan) são expandidas corretamente.

### Como a v6 organiza as páginas

- **casting** (páginas com `{{Casting}}`): fonte principal; cada linha da tabela de versões vira um registro. Inclui carros, motos, aviões e monster trucks (para estes, a série vem do link do ano, ex.: "2011 Monster Jam Series").
- **pack** (5-packs, 10-packs, gift packs, box sets) e **trackset** (pistas e playsets): **não duplicam** carros. O carro do pack é ligado à versão na página do modelo (por Toy #, nome do pack na série ou cor parecida) e ganha o campo `pack`. Só vira linha nova quando o modelo não tem essa versão documentada.
- **list** ("List of 2024 Hot Wheels"): preenche `col_#` e `series_#` das versões (por ano + Toy #).
- **series** e **monster_list**: completam `series_#`/`col_#`; criam linha só para modelos sem página própria.
- Pistas/packs com `{{Casting}}` mas sem tabela viram um registro de produto (`source = product`).
- disambig, designer e outras: ignoradas (antes geravam duplicados).

O `id` segue o formato antigo (`ano-modelo-toy#-cor`), então estoques e coleções feitos com a base antiga continuam compatíveis. Quando duas variações dão o mesmo ID, a segunda recebe o sufixo `~xxxxxx`, e nenhuma variação é descartada.

### Resultado (build de 13/10/2026)

| Métrica | Base antiga | v6 |
|---|---|---|
| Linhas | 48.870 | 57.086 |
| Páginas cobertas | 6.044 | 6.917 |
| Monster trucks | 139 | 4.223 |
| Série preenchida | 96,2 % | 99,3 % |
| Cor preenchida | 85,2 % | 88,0 % |
| `col_#` preenchido | 27,8 % | 31,0 % |
| Ano válido | 97,8 % | 98,2 % |

Detalhes de cada regra estão na [Documentação técnica](DOCUMENTACAO_TECNICA.md).
