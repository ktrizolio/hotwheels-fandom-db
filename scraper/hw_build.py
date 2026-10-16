# -*- coding: utf-8 -*-
"""
hw_build.py - monta a DB a partir do dump de wikitext (v6).

Entrada : dump .jsonl (1 página por linha: pageid,title,categories,wikitext)
          redirects.json (de -> para)
Saída   : hotwheels_db_v6.jsonl  (1 linha por versão/lançamento; compatível
                                  com o Hotwheels Manager)
          castings_v6.jsonl      (1 linha por modelo/casting)
          containers_v6.jsonl    (5-packs, pistas, séries, listas e quem está nelas)
          relatorio_build.json   (estatísticas)
"""
import json, re, os, sys, collections
from multiprocessing import Pool
import hw_parser as hp

KINDS_MEMBER = ('pack', 'trackset', 'list', 'series', 'monster_list')


def _work(page):
    kind = hp.classify(page)
    out = {'kind': kind, 'rows': [], 'members': [], 'casting': None}
    try:
        if kind == 'casting':
            rows, info = hp.parse_casting(page)
            info['product_type'] = hp.product_type(page.get('categories'), page['title'], bool(rows))
            out['rows'], out['casting'] = rows, info
            ptype = info['product_type']
            if ptype in ('pack', 'trackset'):
                out['members'] = hp.parse_member_tables(page, ptype)
        else:
            if kind in ('other', 'series'):
                rows, info = hp.parse_casting(page, strict=True)
                if rows:
                    for r in rows:
                        r['source'] = 'casting_sem_template'
                    info['product_type'] = hp.product_type(page.get('categories'), page['title'], True)
                    out['rows'], out['casting'] = rows, info
            if kind in KINDS_MEMBER:
                out['members'] = hp.parse_member_tables(page, kind)
    except Exception as e:  # nunca derruba o build por causa de 1 página
        out['error'] = f"{page.get('title')}: {e!r}"[:300]
    return out


def _iter(path):
    if not os.path.exists(path) and os.path.exists(path + '.gz'):
        path += '.gz'
    import gzip
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def norm_toy(t):
    return re.sub(r'\s+', '', (t or '').upper())


def color_key(c):
    c = (c or '').lower()
    c = re.sub(r'metalflake|spectraflame|metallic|pearl|satin|matte?|flat|candy|enamel|chrome', ' ', c)
    return frozenset(w for w in re.findall(r'[a-z]+', c) if len(w) > 2)


def cont_key(t):
    t = (t or '').lower().replace('\u2011', '-').replace('\u2010', '-')
    t = re.sub(r'\(.*?\)', ' ', t)
    t = re.sub(r'\b(19|20)\d\d\b|\bseries\b|\bhot wheels\b|\bthe\b', ' ', t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def similar(a, b):
    A, B = color_key(a), color_key(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def build(dump_path, redirects_path, out_dir, procs=None, log=print, images_path=None):
    red = json.load(open(redirects_path, encoding='utf-8')) if redirects_path and os.path.exists(redirects_path) else {}

    imgs = json.load(open(images_path, encoding='utf-8')) if images_path and os.path.exists(images_path) else {}

    def img_url(f):
        if not f:
            return ''
        f = f[:1].upper() + f[1:]
        return imgs.get(f) or hp.file_url(f)

    def resolve(t):
        if not t:
            return ''
        t = t[:1].upper() + t[1:]
        return red.get(t, t).split('#')[0]

    rows, members, castings, errors = [], [], {}, []
    kinds = collections.Counter()
    with Pool(procs) as pool:
        for o in pool.imap_unordered(_work, _iter(dump_path), chunksize=25):
            kinds[o['kind']] += 1
            if o.get('error'):
                errors.append(o['error'])
            rows += o['rows']
            members += o['members']
            if o['casting']:
                castings[o['casting']['title']] = o['casting']
    log(f"páginas: {dict(kinds)} | linhas de versão: {len(rows)} | membros: {len(members)}")

    # ---------- produtos sem tabela (pistas, packs, protótipos não lançados)
    with_rows = {r['casting'] for r in rows}
    for t, c in castings.items():
        if t in with_rows:
            continue
        y = hp._YEAR.search(c['years'])
        rec = {'model_name': c['model_name'], 'casting': t, 'release_year': y.group(1) if y else '',
               'year_raw': c['years'], 'series': c['first_series'], 'series_page': '', 'series_#': '',
               'col_#': '', 'toy_#': c['number'] if c['number'] not in ('?', 'N/A') else '',
               'color': '', 'tampo': '', 'base': '', 'window': '', 'interior': '', 'wheel': '',
               'country': '', 'notes': '', 'subset': '', 'image_file': c['image_file'],
               'section': '', 'designer': c['designer'], 'page_url': c['page_url'],
               'source': 'product', 'pageid': c['pageid'], 'uid': hp.uid_of(str(c['pageid']), 'p')}
        rows.append(rec)

    # ---------- índice por casting/ano
    by_cy = collections.defaultdict(list)
    by_toy = collections.defaultdict(list)
    for r in rows:
        r['product_type'] = castings.get(r['casting'], {}).get('product_type', 'vehicle')
        r['packs'] = []
        by_cy[(r['casting'], r['release_year'])].append(r)
        if r['toy_#']:
            for tt in re.split(r'[/,]', r['toy_#']):
                if norm_toy(tt):
                    by_toy[(r['release_year'], norm_toy(tt))].append(r)

    stats = collections.Counter()
    added = []
    for m in members:
        kind = m['container_type']
        cast = resolve(m['casting'])
        m['casting_resolved'] = cast
        cands = by_cy.get((cast, m['year']), []) if cast else []
        match = None
        # 1) toy # é a chave mais forte
        if m['toy_#']:
            tk = [r for r in by_toy.get((m['year'], norm_toy(m['toy_#'])), []) if not cast or r['casting'] == cast]
            if len(tk) >= 1:
                match = tk if len(tk) == 1 else [max(tk, key=lambda r: similar(r['color'], m['color']))]
        # 2) o nome do pack/pista/série aparece na coluna série da versão
        if not match and cands and kind != 'list':
            ck = cont_key(m['container'])
            nm = [r for r in cands if ck and (ck in cont_key(r['series'] + ' ' + r['notes'] + ' ' + r.get('series_page', '')))]
            if len(nm) > 1 and m['color']:
                nm = [max(nm, key=lambda r: similar(r['color'], m['color']))]
            if len(nm) == 1:
                match = nm
            elif len(nm) > 1 and kind == 'monster_list':
                match = nm[:1]
        # 3) cor parecida na mesma página/ano
        if not match and cands:
            if m['color']:
                best = max(cands, key=lambda r: similar(r['color'], m['color']))
                if similar(best['color'], m['color']) >= 0.5:
                    match = [best]
            elif len(cands) == 1:
                match = cands
            elif kind in ('pack', 'trackset'):
                pk = [r for r in cands if re.search(r'pack|multi|set|exclusive', r['series'] + ' ' + r['notes'], re.I)]
                if len(pk) == 1:
                    match = pk
        if match:
            r = match[0]
            stats[f'{kind}:match'] += 1
            if kind in ('pack', 'trackset'):
                if m['container'] not in r['packs']:
                    r['packs'].append(m['container'])
            if m['col_#'] and not r['col_#']:
                r['col_#'] = m['col_#']; stats['fill:col_#'] += 1
            if m['series_#'] and not r['series_#']:
                r['series_#'] = m['series_#']; stats['fill:series_#'] += 1
            if kind == 'list' and m['series'] and (not r['series'] or r['series'].lower() in ('mainline',)) and m['series'].lower() not in ('mainline',):
                r['segment'] = m['series']
            if m['image_file'] and not r['image_file']:
                r['image_file'] = m['image_file']; stats['fill:image'] += 1
            continue
        stats[f'{kind}:nomatch'] += 1
        # sem correspondência: cria linha só quando a info é nova (evita duplicar)
        create = False
        if kind in ('pack', 'trackset'):
            create = True
        elif kind == 'monster_list' and not cands:
            create = True
        elif kind in ('list', 'series') and cast not in castings:
            create = True
        elif kind == 'list' and not cands:
            create = True
        if not create or not m['model_name'] or not m['year']:
            continue
        rec = {'model_name': re.sub(r'\s*\(.*?\)\s*$', '', m['model_name']) if cast in castings else m['model_name'],
               'casting': cast or m['model_name'], 'release_year': m['year'], 'year_raw': '',
               'series': m['series'] or (m['container'] if kind != 'list' else ''),
               'series_page': m['container'] if kind != 'list' else '', 'series_#': m['series_#'],
               'col_#': m['col_#'], 'toy_#': m['toy_#'], 'color': m['color'], 'tampo': m['tampo'],
               'base': m['base'], 'window': m['window'], 'interior': m['interior'], 'wheel': m['wheel'],
               'country': m['country'], 'notes': m['notes'], 'subset': m['subset'],
               'image_file': m['image_file'], 'section': m['section'], 'designer': '',
               'page_url': hp.page_url(cast) if cast in castings else m['page_url'],
               'source': kind, 'pageid': None, 'uid': m['uid'],
               'product_type': 'monster_truck' if kind == 'monster_list' else castings.get(cast, {}).get('product_type', 'vehicle'),
               'packs': [m['container']] if kind in ('pack', 'trackset') else []}
        if m['subset'] and m['subset'].lower() != 'standard' and m['subset'] not in rec['series']:
            rec['series'] = f"{rec['series']} - {m['subset']}"
        added.append(rec)
        stats[f'{kind}:new_row'] += 1
    rows += added

    # ---------- finalização: normaliza e gera IDs únicos
    seen = collections.Counter()
    for r in rows:
        r['toy_#'] = r['toy_#'].strip()
        if r['toy_#'].upper() in ('N/A', 'NA', '-', '?', 'NONE', 'UNKNOWN'):
            r['toy_#'] = ''
        cm = re.fullmatch(r'\s*(\d+)\s*/\s*(\d+)\s*', r['col_#'] or '')
        r['col_num'], r['col_total'] = (int(cm.group(1)), int(cm.group(2))) if cm else (None, None)
        r['pack'] = ' | '.join(r.pop('packs'))
        r['photo_url'] = img_url(r['image_file'])
        r['id'] = hp.make_id(r['release_year'], r['model_name'], r['toy_#'], r['color'])
        seen[r['id']] += 1
    dup = collections.Counter()
    for r in rows:
        if seen[r['id']] > 1:
            dup[r['id']] += 1
            if dup[r['id']] > 1:
                r['id'] = f"{r['id']}~{r['uid'][:6]}"
        r.pop('pageid', None)

    order = ['id', 'model_name', 'release_year', 'series', 'col_#', 'toy_#', 'color', 'tampo',
             'photo_url', 'page_url', 'casting', 'product_type', 'series_#', 'segment', 'pack',
             'base', 'window', 'interior', 'wheel', 'country', 'notes', 'subset', 'section',
             'designer', 'year_raw', 'col_num', 'col_total', 'image_file', 'series_page', 'source', 'uid']
    rows.sort(key=lambda r: (r['casting'].lower(), r['release_year'], r['uid']))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'hotwheels_db_v6.jsonl'), 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps({k: r.get(k, '') for k in order}, ensure_ascii=False) + '\n')
    with open(os.path.join(out_dir, 'castings_v6.jsonl'), 'w', encoding='utf-8') as f:
        cnt = collections.Counter(r['casting'] for r in rows)
        for t, c in sorted(castings.items()):
            c = dict(c); c['n_versions'] = cnt.get(t, 0); c.pop('pageid', None)
            f.write(json.dumps(c, ensure_ascii=False) + '\n')
    with open(os.path.join(out_dir, 'containers_v6.jsonl'), 'w', encoding='utf-8') as f:
        cont = collections.defaultdict(list)
        for m in members:
            cont[(m['container'], m['container_type'])].append(m)
        for (t, k), ms in sorted(cont.items()):
            f.write(json.dumps({'title': t, 'type': k, 'page_url': ms[0]['page_url'],
                                'members': [{x: m[x] for x in ('year', 'model_name', 'casting_resolved', 'color', 'toy_#', 'col_#', 'series_#', 'section')} for m in ms]},
                               ensure_ascii=False) + '\n')
    rep = {'pages': dict(kinds), 'rows': len(rows), 'castings': len(castings),
           'by_source': dict(collections.Counter(r['source'] for r in rows)),
           'by_product_type': dict(collections.Counter(r['product_type'] for r in rows)),
           'merge': dict(stats), 'errors': errors[:200], 'n_errors': len(errors)}
    json.dump(rep, open(os.path.join(out_dir, 'relatorio_build.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    log(json.dumps({k: v for k, v in rep.items() if k != 'errors'}, ensure_ascii=False, indent=1))
    return rep


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3], images_path=sys.argv[4] if len(sys.argv) > 4 else None)
