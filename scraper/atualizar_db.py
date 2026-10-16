# -*- coding: utf-8 -*-
"""
atualizar_db.py - processo completo (o .bat chama este arquivo)

 1. Baixa a wiki pela API              -> dados/AAAA-MM-DD/
 2. Monta a DB (parser v6)             -> saida/AAAA-MM-DD/
 3. Copia a DB para o Manager          -> Hotwheels_Manager/hotwheels-manager/data/wiki_v6.jsonl
 4. Migra os IDs do estoque/coleção    -> <arquivo>_v6.jsonl (o original não é alterado)

Pastas (relativas a Hotwheels_Fandom_DB_Scrapping/):
  dados/AAAA-MM-DD/  dump da wiki      saida/AAAA-MM-DD/  DB gerada      logs/  histórico

Uso: python atualizar_db.py            (baixa e monta)
     python atualizar_db.py --offline  (remonta usando o último dump baixado)
"""
import os, sys, json, glob, re, shutil, datetime, collections, urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))          # .../Hotwheels_Fandom_DB_Scrapping/scraper
RAIZ = os.path.dirname(AQUI)                               # .../Hotwheels_Fandom_DB_Scrapping
sys.path.insert(0, AQUI)
import hw_build
import baixar_wiki

MANAGER_DATA = os.path.normpath(os.path.join(RAIZ, '..', 'Hotwheels_Manager', 'hotwheels-manager', 'data'))


def log(msg):
    print(msg, flush=True)
    os.makedirs(os.path.join(RAIZ, 'logs'), exist_ok=True)
    with open(os.path.join(RAIZ, 'logs', 'atualizar_db.log'), 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}\n")


def migrar(arquivo, db_rows, redirects):
    """Reaponta itens de estoque/coleção para os IDs da DB nova. Não altera o original."""
    ids = {r['id']: r for r in db_rows}
    idx = collections.defaultdict(list)
    for r in db_rows:
        for t in re.split(r'[/,]', r['toy_#'] or '') or ['']:
            idx[(r['casting'], r['release_year'], t.strip().upper())].append(r)

    def titulo(u):
        t = urllib.parse.unquote((u or '').split('/wiki/')[-1].split('#')[0]).replace('_', ' ')
        return redirects.get(t, t)

    saida, stats = [], collections.Counter()
    with open(arquivo, encoding='utf-8') as f:
        itens = [json.loads(l) for l in f if l.strip()]
    for it in itens:
        novo = ids.get(it.get('id'))
        if novo:
            stats['id_identico'] += 1
        else:
            c = idx.get((titulo(it.get('page_url')), it.get('release_year', ''), (it.get('toy_#') or '').split('/')[0].strip().upper()), [])
            if c:
                cor = set((it.get('color') or '').lower().split())
                novo = max(c, key=lambda r: len(cor & set(r['color'].lower().split())))
                stats['mapeado'] += 1
            else:
                stats['sem_par'] += 1
        if novo:
            extra = {k: v for k, v in it.items() if k not in novo}   # preços, quantidade etc.
            it2 = dict(novo); it2.update(extra); it2['id_antigo'] = it.get('id')
            saida.append(it2)
        else:
            it['migracao'] = 'SEM_PAR_NA_DB_V6'
            saida.append(it)
    destino = arquivo[:-6] + '_v6.jsonl'
    with open(destino, 'w', encoding='utf-8') as f:
        for it in saida:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')
    return destino, dict(stats)


def main():
    hoje = f"{datetime.date.today():%Y-%m-%d}"
    offline = '--offline' in sys.argv
    if offline:
        dumps = sorted(glob.glob(os.path.join(RAIZ, 'dados', '*', 'dump.jsonl*')))
        if not dumps:
            log('Nenhum dump encontrado em dados/. Rode sem --offline.'); return
        pasta_dados = os.path.dirname(dumps[-1])
        log(f'Modo offline: usando {pasta_dados}')
    else:
        pasta_dados = os.path.join(RAIZ, 'dados', hoje)
        log('1/4 Baixando a wiki pela API (leva alguns minutos)...')
        baixar_wiki.baixar(pasta_dados, log=log)

    pasta_saida = os.path.join(RAIZ, 'saida', os.path.basename(pasta_dados))
    log('2/4 Montando a DB...')
    hw_build.build(os.path.join(pasta_dados, 'dump.jsonl'), os.path.join(pasta_dados, 'redirects.json'),
                   pasta_saida, log=log, images_path=os.path.join(pasta_dados, 'images.json'))
    db_path = os.path.join(pasta_saida, 'hotwheels_db_v6.jsonl')
    with open(db_path, encoding='utf-8') as f:
        rows = [json.loads(l) for l in f if l.strip()]

    if os.path.isdir(MANAGER_DATA):
        log('3/4 Copiando para o Manager como data/wiki_v6.jsonl ...')
        shutil.copy2(db_path, os.path.join(MANAGER_DATA, 'wiki_v6.jsonl'))
        log('4/4 Migrando estoque/coleção (os originais ficam intactos)...')
        red = json.load(open(os.path.join(pasta_dados, 'redirects.json'), encoding='utf-8'))
        for arq in glob.glob(os.path.join(MANAGER_DATA, '*.jsonl')):
            nome = os.path.basename(arq).lower()
            if nome.startswith('wiki') or nome.endswith('_v6.jsonl') or nome.startswith('descricoes'):
                continue
            if os.path.getsize(arq) == 0:
                continue
            destino, st = migrar(arq, rows, red)
            log(f'   {os.path.basename(arq)} -> {os.path.basename(destino)}  {st}')
    else:
        log(f'Pasta do Manager não encontrada ({MANAGER_DATA}); DB ficou só em {pasta_saida}')
    log('Pronto! Veja saida/<data>/relatorio_build.json para as estatísticas.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f'ERRO: {e!r}')
        raise
