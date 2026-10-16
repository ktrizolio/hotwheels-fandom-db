# Como usar

Guia para quem só quer a base pronta, sem precisar programar. Para usar os dados em outro app, veja [Integração](INTEGRACAO.md).

## 1. O que você precisa

- Um computador com **Windows** (no Linux/macOS também funciona, veja a seção 6).
- **Internet** na primeira vez (o download da wiki tem cerca de 12 MB compactados).
- **Python 3.10 ou mais novo.** Se não tiver:
  1. entre em <https://www.python.org/downloads/> e baixe o instalador;
  2. na **primeira tela** do instalador, marque **"Add python.exe to PATH"**;
  3. clique em *Install Now*.
- Uns **150 MB livres** em disco para cada data baixada (download + base montada).

## 2. Baixar o projeto

1. No topo da página do repositório, clique no botão verde **Code → Download ZIP**.
2. Descompacte numa pasta de sua escolha, por exemplo `Documentos\HotWheels`.

Quem usa Git pode clonar direto:

```bash
git clone https://github.com/ktrizolio/hotwheels-fandom-db.git
```

## 3. Montar a base

Dê **dois cliques em `ATUALIZAR_DB.bat`**. Uma janela preta abre e mostra o andamento:

```
============================================
  Hot Wheels DB - baixar wiki e montar DB
============================================
Preparando o ambiente na primeira execucao...
1/4 Baixando a wiki pela API (leva alguns minutos)...
  páginas listadas: 11247
  wikitext: 1000/11247
  ...
2/4 Montando a DB...
Pronto! Veja saida/<data>/relatorio_build.json para as estatísticas.
Pressione qualquer tecla para continuar. . .
```

- Na **primeira vez**, o programa prepara sozinho um ambiente Python (`scraper/.venv`) e instala as duas bibliotecas de que precisa. Isso leva cerca de 1 minuto e só acontece uma vez.
- O download leva de **3 a 6 minutos**; a montagem, cerca de **1 minuto**.
- Pode usar o computador normalmente enquanto isso. Não feche a janela antes do "Pronto!".

### Remontar sem internet

**`REMONTAR_SEM_BAIXAR.bat`** usa o último download guardado em `dados/` e só refaz a montagem. Serve para quando você atualizou o programa e quer ver o resultado sem baixar a wiki de novo.

## 4. Onde ficam os arquivos

```
saida/
└── 2026-10-13/                 ← uma pasta por data
    ├── hotwheels_db_v6.jsonl   ← a base principal (1 linha por versão)
    ├── castings_v6.jsonl       ← 1 linha por modelo
    ├── containers_v6.jsonl     ← packs, pistas, séries e listas
    └── relatorio_build.json    ← números da montagem
dados/
└── 2026-10-13/                 ← o download bruto da wiki
logs/
└── atualizar_db.log            ← histórico das execuções
```

Use sempre a pasta com a **data mais recente**. As antigas podem ser apagadas quando não forem mais úteis.

## 5. Abrir os dados

Os arquivos `.jsonl` têm um registro por linha, em texto. Algumas formas de abrir:

- **Planilha / banco SQL:** converta para SQLite com o script de exemplo e abra no [DB Browser for SQLite](https://sqlitebrowser.org/) (gratuito), que exporta para CSV/Excel:

  ```bash
  python docs/exemplos/jsonl_para_sqlite.py saida/2026-10-13 hotwheels.db
  ```

- **Python ou JavaScript:** receitas prontas em [Integração §3](INTEGRACAO.md#3-receitas).
- **Só olhar:** qualquer editor de texto que aguente arquivos grandes (VS Code, Notepad++).

O significado de cada campo (`toy_#`, `col_#`, `tampo`, `series_#`, `wheel`…) está em [Integração §2](INTEGRACAO.md#2-modelo-de-dados).

### Integração com o Hotwheels Manager (opcional)

Se existir uma pasta `Hotwheels_Manager/hotwheels-manager/data/` **ao lado** desta pasta, o `ATUALIZAR_DB.bat` também:

- copia a base para lá como `wiki_v6.jsonl`;
- cria cópias do estoque/coleção com os ids da base nova (`<arquivo>_v6.jsonl`). **Os arquivos originais não são alterados.**

Sem essa pasta, essas etapas são puladas e a base fica só em `saida/`.

## 6. Linux, macOS ou linha de comando

```bash
cd scraper
python3 -m venv .venv
. .venv/bin/activate          # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python atualizar_db.py            # baixa e monta
python atualizar_db.py --offline  # só remonta com o último download
```

Para chamar cada etapa separadamente a partir de outro programa Python, veja [Integração §3.5](INTEGRACAO.md#35-chamar-o-scraper-de-dentro-de-outro-app-python).

## 7. Perguntas frequentes

**Aparece "ERRO: nenhum Python funcionando foi encontrado".**
O Python não está instalado ou não foi colocado no PATH. Reinstale marcando **"Add python.exe to PATH"** e rode o `.bat` de novo.

**Deu erro de internet no meio do download.**
O programa tenta de novo sozinho até 6 vezes por requisição. Se mesmo assim falhar, espere alguns minutos e rode outra vez: o download recomeça do zero, mas não estraga nada do que já existe em `saida/`.

**Com que frequência devo atualizar?**
Uma vez por mês é suficiente. A wiki muda pouco de um dia para o outro, e rodar com muita frequência só sobrecarrega o site de quem mantém a wiki.

**O `id` de uma miniatura mudou entre duas datas.**
Acontece quando a wiki corrige o nome, a cor ou o Toy #. Veja as regras em [Integração §4](INTEGRACAO.md#4-regras-para-quem-guarda-referências-estoque-coleção-vendas).

**Algumas fotos não abrem (erro 404).**
O endereço da foto é calculado a partir do nome do arquivo citado na wiki. Se a página cita uma foto que nunca foi enviada, o link não existe. É uma limitação da própria wiki.

**Achei um dado errado.**
Primeiro confira na página da wiki (`page_url`). Se o erro estiver lá, corrija na própria wiki: na próxima atualização ele some daqui também. Se a wiki estiver certa e a base errada, abra uma *issue* neste repositório com o `id` do registro.

**Posso publicar os dados ou as fotos?**
Sim, respeitando a licença **CC BY-SA** da Fandom: cite a Hot Wheels Wiki como fonte e mantenha a mesma licença.
