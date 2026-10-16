# -*- coding: utf-8 -*-
"""
baixar_wiki.py - baixa a Hot Wheels Fandom inteira pela API oficial (MediaWiki).

Não faz scraping de HTML. Gera em <pasta>/:
  dump.jsonl       1 página por linha: pageid, title, categories, timestamp, wikitext
  redirects.json   {"Título antigo": "Título atual"}
  images.json      {"Arquivo.jpg": "https://static.wikia.nocookie.net/..."}

~230 requisições para o texto + ~340 para as imagens. Educado com o servidor:
1 requisição por vez, maxlag, User-Agent identificado e novas tentativas.
"""
import json, os, sys, time
import requests

API = 'https://hotwheels.fandom.com/api.php'
UA = 'HotWheelsFandomDB/6.0 (projeto de catalogação; +https://github.com/ktrizolio/hotwheels-fandom-db)'
S = requests.Session()
S.headers['User-Agent'] = UA


def call(params, method='get', tries=6):
    params = dict(params, format='json', formatversion='2', maxlag='5')
    for a in range(tries):
        try:
            r = S.post(API, data=params, timeout=60) if method == 'post' else S.get(API, params=params, timeout=60)
            if r.status_code == 200:
                j = r.json()
                if j.get('error', {}).get('code') == 'maxlag':
                    time.sleep(5); continue
                return j
        except (requests.RequestException, ValueError):
            pass
        time.sleep(2 * (a + 1))
    raise RuntimeError(f'Falha na API após {tries} tentativas: {params.get("list") or params.get("prop")}')


def paginate(params, key):
    cont = {}
    while True:
        j = call({**params, **cont})
        yield j.get('query', {}).get(key, [])
        if 'continue' not in j:
            break
        cont = j['continue']
        time.sleep(0.2)


def baixar(pasta, log=print, imagens=False):
    os.makedirs(pasta, exist_ok=True)
    # 1) lista de páginas (namespace 0, sem redirects) + categorias
    pages = {}
    for chunk in paginate({'action': 'query', 'generator': 'allpages', 'gapnamespace': 0,
                           'gapfilterredir': 'nonredirects', 'gaplimit': 500,
                           'prop': 'categories', 'cllimit': 'max'}, 'pages'):
        for p in chunk:
            o = pages.setdefault(p['pageid'], {'pageid': p['pageid'], 'title': p['title'], 'categories': []})
            o['categories'] += [c['title'].split(':', 1)[1] for c in p.get('categories', [])]
        log(f'  páginas listadas: {len(pages)}')
    # 2) wikitext em lotes de 50
    ids = sorted(pages)
    for i in range(0, len(ids), 50):
        lote = ids[i:i + 50]
        j = call({'action': 'query', 'prop': 'revisions', 'rvprop': 'content|timestamp', 'rvslots': 'main',
                  'pageids': '|'.join(map(str, lote))}, method='post')
        for p in j['query']['pages']:
            rev = (p.get('revisions') or [{}])[0]
            pages[p['pageid']]['timestamp'] = rev.get('timestamp')
            pages[p['pageid']]['wikitext'] = rev.get('slots', {}).get('main', {}).get('content', '')
        if (i // 50) % 20 == 0:
            log(f'  wikitext: {min(i + 50, len(ids))}/{len(ids)}')
        time.sleep(0.2)
    with open(os.path.join(pasta, 'dump.jsonl'), 'w', encoding='utf-8') as f:
        for pid in ids:
            p = pages[pid]
            p.setdefault('wikitext', '')
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    log(f'  dump.jsonl salvo ({len(ids)} páginas)')
    # 3) redirects
    titles = [p['title'] for ch in paginate({'action': 'query', 'list': 'allpages', 'apnamespace': 0,
                                             'apfilterredir': 'redirects', 'aplimit': 500}, 'allpages') for p in ch]
    red = {}
    for i in range(0, len(titles), 50):
        j = call({'action': 'query', 'redirects': 1, 'titles': '|'.join(titles[i:i + 50])}, method='post')
        for x in j.get('query', {}).get('redirects', []):
            red[x['from']] = x['to']
    json.dump(red, open(os.path.join(pasta, 'redirects.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    log(f'  redirects.json salvo ({len(red)})')
    # 4) URLs reais das imagens
    if imagens:
        img = {}
        for ch in paginate({'action': 'query', 'list': 'allimages', 'aiprop': 'url', 'ailimit': 500}, 'allimages'):
            for x in ch:
                img[x['name']] = x['url']
            if len(img) % 20000 < 500:
                log(f'  imagens: {len(img)}')
        json.dump(img, open(os.path.join(pasta, 'images.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        log(f'  images.json salvo ({len(img)})')
    return pasta


if __name__ == '__main__':
    baixar(sys.argv[1] if len(sys.argv) > 1 else 'dados')
