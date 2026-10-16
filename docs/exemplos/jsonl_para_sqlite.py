# -*- coding: utf-8 -*-
"""Converte a saída da v6 (JSONL) em um banco SQLite.
Uso: python jsonl_para_sqlite.py <pasta saida/AAAA-MM-DD> hotwheels.db"""
import json, os, sqlite3, sys


def ler(caminho):
    with open(caminho, encoding='utf-8') as f:
        for l in f:
            if l.strip():
                yield json.loads(l)


def main(pasta, destino):
    if os.path.exists(destino):
        os.remove(destino)
    con = sqlite3.connect(destino)
    db = list(ler(os.path.join(pasta, 'hotwheels_db_v6.jsonl')))
    cols = list(db[0].keys())
    con.execute('CREATE TABLE versoes (' + ', '.join(f'"{c}"' + (' TEXT PRIMARY KEY' if c == 'id' else '') for c in cols) + ')')
    con.executemany(f'INSERT INTO versoes VALUES ({",".join("?" * len(cols))})', [[r.get(c) for c in cols] for r in db])
    for c in ('casting', 'toy_#', 'release_year', 'series'):
        con.execute(f'CREATE INDEX "ix_versoes_{c}" ON versoes ("{c}")')

    con.execute('CREATE TABLE castings (title TEXT PRIMARY KEY, model_name, designer, first_series, number, years, '
                'image_file, categories, page_url, product_type, n_versions INTEGER)')
    con.executemany('INSERT INTO castings VALUES (?,?,?,?,?,?,?,?,?,?,?)', [
        (c['title'], c['model_name'], c['designer'], c['first_series'], c['number'], c['years'], c['image_file'],
         ' | '.join(c['categories']), c['page_url'], c['product_type'], c['n_versions'])
        for c in ler(os.path.join(pasta, 'castings_v6.jsonl'))])

    con.execute('CREATE TABLE containers (title TEXT, type TEXT, page_url TEXT)')
    con.execute('CREATE TABLE membros (container_id INTEGER, year, model_name, casting_resolved, color, '
                '"toy_#", "col_#", "series_#", section)')
    for c in ler(os.path.join(pasta, 'containers_v6.jsonl')):
        cid = con.execute('INSERT INTO containers VALUES (?,?,?)', (c['title'], c['type'], c['page_url'])).lastrowid
        con.executemany('INSERT INTO membros VALUES (?,?,?,?,?,?,?,?,?)', [
            (cid, m['year'], m['model_name'], m['casting_resolved'], m['color'], m['toy_#'], m['col_#'], m['series_#'], m['section'])
            for m in c['members']])
    con.execute('CREATE INDEX ix_membros_casting ON membros (casting_resolved)')
    con.commit()
    n = con.execute('SELECT (SELECT COUNT(*) FROM versoes), (SELECT COUNT(*) FROM castings), (SELECT COUNT(*) FROM containers), (SELECT COUNT(*) FROM membros)').fetchone()
    print(f'OK: {destino}  versoes={n[0]} castings={n[1]} containers={n[2]} membros={n[3]}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'hotwheels.db')
