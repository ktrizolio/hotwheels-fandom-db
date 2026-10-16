# Hot Wheels Fandom DB

Monta, no seu computador, uma base de dados com **todas as versões de miniaturas Hot Wheels** documentadas na [Hot Wheels Wiki (Fandom)](https://hotwheels.fandom.com): cerca de **57 mil versões** de **6,6 mil modelos**, além de 5-packs, pistas, séries e monster trucks.

Os dados saem em arquivos simples (JSON Lines), prontos para usar em planilhas, apps de estoque, coleção ou loja.

## O que é

É um programa em Python que:

1. **baixa a wiki inteira** pela API oficial do MediaWiki (sem scraping de HTML e sem sobrecarregar o site);
2. **lê o texto-fonte de cada página** (o wikitext) e entende o que ela é: um modelo, um 5-pack, uma pista, uma lista anual ou uma série;
3. **junta tudo numa base única**, sem duplicar o carro que aparece ao mesmo tempo na página do modelo e na página do pack;
4. salva o resultado em `saida/<data>/`.

## Para que serve

- **Cadastrar estoque e coleção mais rápido:** ano, nome, Toy #, série, cor, tampo e foto de cada versão.
- **Identificar uma miniatura:** comparar a foto e os detalhes (rodas, base, país) para saber se é a mesma versão.
- **Pesquisar:** todas as versões de um modelo, tudo de um ano, só monster trucks, o conteúdo de um 5-pack…
- **Alimentar outros apps:** o formato é aberto e documentado (ver [Integração](docs/INTEGRACAO.md)).

Exemplo de um registro (resumido):

```json
{"id": "1969-twin_mill-6258-spectraflame_antifreeze", "model_name": "Twin Mill", "release_year": "1969",
 "series": "Mainline", "toy_#": "6258", "color": "Spectraflame Antifreeze", "designer": "Ira Gilford",
 "photo_url": "https://static.wikia.nocookie.net/hotwheels/images/4/4b/Twin_Mill_Anti.JPG/revision/latest",
 "page_url": "https://hotwheels.fandom.com/wiki/Twin_Mill",
 "product_type": "vehicle", "window": "Clear", "wheel": "RL", "country": "USA"}
```

## Como usar (resumo)

> Passo a passo completo, com prints do que esperar e erros comuns: **[Como usar](docs/COMO_USAR.md)**.

**Windows (duplo clique):**

1. Instale o [Python 3](https://www.python.org/downloads/) marcando **"Add python.exe to PATH"**.
2. Baixe este repositório (botão verde **Code → Download ZIP**) e descompacte.
3. Dê dois cliques em **`ATUALIZAR_DB.bat`**. Leva de 5 a 10 minutos.
4. A base fica em `saida/<data de hoje>/hotwheels_db_v6.jsonl`.

Para remontar a base sem internet, a partir do último download: **`REMONTAR_SEM_BAIXAR.bat`**.

**Linux / macOS / linha de comando:**

```bash
cd scraper
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python atualizar_db.py            # baixa a wiki e monta a base
python atualizar_db.py --offline  # remonta com o último download
```

## O que é gerado

| Arquivo (em `saida/<data>/`) | Conteúdo |
|---|---|
| `hotwheels_db_v6.jsonl` | **principal**: 1 linha por versão (~57 mil) |
| `castings_v6.jsonl` | 1 linha por modelo (~6,6 mil) |
| `containers_v6.jsonl` | 5-packs, pistas, séries e listas, com os carros de cada um |
| `relatorio_build.json` | estatísticas da montagem |

O download bruto da wiki fica em `dados/<data>/` (para remontar sem internet).

## Estrutura do repositório

```
├── ATUALIZAR_DB.bat          baixa a wiki e monta a base (duplo clique)
├── REMONTAR_SEM_BAIXAR.bat   remonta com o último download, sem internet
├── scraper/
│   ├── baixar_wiki.py        API da Fandom → dump.jsonl + redirects.json
│   ├── hw_parser.py          entende cada tipo de página
│   ├── hw_build.py           junta tudo, evita duplicados e gera a base
│   ├── atualizar_db.py       roda todas as etapas
│   └── requirements.txt
└── docs/
    ├── COMO_USAR.md              passo a passo para quem não programa
    ├── INTEGRACAO.md             campos, formatos e receitas para outros apps
    ├── DOCUMENTACAO_TECNICA.md   como o parser funciona por dentro
    ├── HISTORICO.md              por que a v6 existe e o que ela corrigiu
    ├── schemas/                  JSON Schema dos três arquivos
    └── exemplos/                 conversor para SQLite
```

As pastas `dados/`, `saida/` e `logs/` são criadas na primeira execução e não vão para o Git.

## Documentação

- **[Como usar](docs/COMO_USAR.md):** instalar, rodar, onde achar os arquivos, perguntas frequentes.
- **[Integração](docs/INTEGRACAO.md):** dicionário de campos, identificadores e exemplos em Python, pandas, JavaScript e SQLite.
- **[Documentação técnica](docs/DOCUMENTACAO_TECNICA.md):** download, classificação das páginas, parser das tabelas e regras de junção.
- **[Histórico](docs/HISTORICO.md):** a versão antiga com Scrapy, os problemas dela e o que mudou.

## Uso responsável e licença dos dados

- O programa usa a API oficial, faz uma requisição por vez, respeita o `maxlag` e se identifica no `User-Agent`. **Rode no máximo algumas vezes por mês**: a wiki muda pouco de um dia para o outro.
- O **conteúdo** (textos, dados e fotos) é da comunidade da Hot Wheels Wiki, publicado sob a licença **[CC BY-SA](https://www.fandom.com/licensing)**. Se você publicar os dados ou as fotos, cite a fonte (o campo `page_url` de cada registro já traz o link) e mantenha a mesma licença.
- Hot Wheels é marca registrada da Mattel. Este projeto não tem ligação com a Mattel nem com a Fandom.
