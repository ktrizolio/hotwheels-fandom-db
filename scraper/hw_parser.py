# -*- coding: utf-8 -*-
"""
hw_parser.py  -  Parser do wikitext da Hot Wheels Fandom (v6)

Trabalha sobre o WIKITEXT (fonte) das páginas, obtido pela API oficial do
MediaWiki, e não sobre o HTML renderizado. Vantagens:
  * rowspan/colspan são expandidos corretamente (wikitextparser span=True);
  * textos com links ([[Spectraflame]] Aqua) não são truncados;
  * o tipo de página é identificado pelo template ({{Casting}}, {{Disambig}}...).

Tipos de página tratados:
  casting       -> página de modelo (carro, moto, monster truck, avião...) com
                   tabela de versões. FONTE PRINCIPAL de linhas da DB.
  pack          -> 5-Packs, 3-Packs, 10-Packs, gift packs, box sets.
  trackset      -> pistas / playsets que trazem um carro exclusivo.
  list          -> "List of YYYY Hot Wheels" (toy #, col #, série, nº na série).
  series        -> páginas de série/linha (Mainline segments, Car Culture...).
  monster_list  -> listas anuais de Monster Jam / Monster Trucks.
  disambig / designer / other -> ignoradas para releases.
"""
import re
import html
import hashlib
import urllib.parse

import wikitextparser as wtp

WIKI = 'https://hotwheels.fandom.com/wiki/'

# ---------------------------------------------------------------- limpeza ---
_REF = re.compile(r'<ref[^>/]*/>|<ref[^>]*>.*?</ref>', re.S | re.I)
_COMMENT = re.compile(r'<!--.*?-->', re.S)
_BR = re.compile(r'<br\s*/?>', re.I)
_FILE = re.compile(r'\[\[\s*(?:File|Image|Arquivo)\s*:\s*([^|\]]+)', re.I)
_PLACEHOLDER = re.compile(r'image[ _]not[ _]available|no[ _]image|noimage|placeholder', re.I)
_YEAR = re.compile(r'\b(19[5-9]\d|20[0-4]\d)\b')
_LINK = re.compile(r'\[\[\s*([^|\]#]+)(?:#[^|\]]*)?(?:\|[^\]]*)?\]\]')


def clean(cell):
    """Converte uma célula de wikitext em texto simples."""
    if cell is None:
        return ''
    s = _COMMENT.sub('', cell)
    s = _REF.sub('', s)
    s = re.sub(r'\[\[\s*(?:File|Image|Category)\s*:[^\]]*\]\]', '', s, flags=re.I)
    s = _BR.sub(' / ', s)
    # templates (inclusive aninhados): remove de dentro para fora
    for _ in range(4):
        n = re.sub(r'\{\{[^{}]*\}\}', '', s)
        if n == s:
            break
        s = n
    s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', s)          # [[a|b]] -> b
    s = re.sub(r'\[(?:https?:)?//[^\s\]]+\s*([^\]]*)\]', r'\1', s)    # [url texto]
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s).replace('\xa0', ' ')
    s = re.sub(r"'{2,}", '', s)
    s = re.sub(r'\s*/\s*(/\s*)+', ' / ', s)
    s = re.sub(r'\s+', ' ', s).strip(' /|')
    return s


def first_link(cell):
    """Título da primeira página linkada na célula (ignora File/Image)."""
    for m in _LINK.finditer(cell or ''):
        t = m.group(1).strip()
        if not re.match(r'(file|image|category|arquivo)\s*:', t, re.I):
            return t.replace('_', ' ')
    return ''


def image_of(cell):
    m = _FILE.search(cell or '')
    if not m:
        return ''
    f = m.group(1).strip().replace(' ', '_')
    return '' if _PLACEHOLDER.search(f) else f


def file_url(fname):
    """URL direta da imagem no CDN da Fandom (caminho = md5 do nome, padrão MediaWiki)."""
    if not fname:
        return ''
    f = fname.strip().replace(' ', '_')
    f = f[:1].upper() + f[1:]
    h = hashlib.md5(f.encode('utf-8')).hexdigest()
    return f"https://static.wikia.nocookie.net/hotwheels/images/{h[0]}/{h[:2]}/{urllib.parse.quote(f)}/revision/latest"



def page_url(title):
    return WIKI + urllib.parse.quote(title.replace(' ', '_'), safe="/'(),!:&-.")


def norm_header(h):
    h = clean(h or '').lower().replace('.', ' ').replace('_', ' ').replace(':', '')
    h = re.sub(r'(center|left|right)\|\d+px', '', h)
    return re.sub(r'\s+', ' ', h).strip()


def slug(s):
    return re.sub(r'_+', '_', re.sub(r'[\s/]+', '_', (s or '').strip().lower()))


# --------------------------------------------------------- cabeçalhos ------
HEADER_MAP = {
    'year': ['year', 'years', 'year released', 'release year'],
    'series': ['series', 'series / card', 'series/card', 'line', 'debut series', 'segment'],
    'series_num': ['series #', '# in series', 'series number', 'series no'],
    'col_num': ['col #', 'col#', 'coll #', 'col', 'collector #', 'collector number', 'col no', '#'],
    'toy_num': ['toy #', 'toy#', 'toy number', 'number', 'toy no', 'sku', 'tool #'],
    'name': ['name', 'casting name', 'casting', 'model name', 'model', 'truck name', 'vehicle'],
    'color': ['color', 'body color', 'color / tampo', 'colour', 'body colour'],
    'tampo': ['tampo', 'tampos', 'sticker', 'stickers', 'graphic', 'graphics', 'deco'],
    'base': ['base color / type', 'base color/type', 'base color', 'base color / types',
             'base / type', 'base color + type', 'base color /type', 'chassis color / type',
             'chassis type / color', 'base color /', 'base'],
    'window': ['window color', 'window', 'windows', 'canopy color'],
    'interior': ['interior color', 'interior', 'interior / engine color'],
    'wheel': ['wheel type', 'wheels', 'wheel'],
    'country': ['country', 'made in'],
    'notes': ['notes', 'notes / variations', 'notes/variations', 'note', 'variations'],
    'subset': ['subset', 'mini collection', 'theme'],
    'photo': ['photo', 'image', 'photo loose', 'picture', 'pic'],
    'photo_carded': ['photo carded', 'carded'],
    'set_num': ['set #'],
}
_H = {v: k for k, vs in HEADER_MAP.items() for v in vs}


def map_headers(row):
    out = {}
    for i, h in enumerate(row):
        k = _H.get(norm_header(h))
        if k and k not in out:
            out[k] = i
    return out


# ------------------------------------------------------ tipo de página -----
def first_template(s):
    m = re.match(r'\s*(?:\{\{\s*DISPLAYTITLE[^}]*\}\}\s*)?\{\{\s*([^|}\n]+)', s or '', re.I)
    return m.group(1).strip().lower().replace('_', ' ') if m else ''


def casting_params(s):
    for t in wtp.parse(s).templates:
        if t.normal_name().lower() == 'casting':
            return {a.name.strip().lower(): a.value for a in t.arguments}
    return {}


PACK_RE = re.compile(r'\b(\d+|two|three|five|ten|nine|six|eight)[- ]?(car )?pack\b|gift pack|box set|multi-?pack|collector set', re.I)
TRACK_RE = re.compile(r'track|play ?set|playset|launcher|garage|city|race ?(set|track)|stunt|loop|crash', re.I)


def classify(page):
    s, t = page['wikitext'], page['title']
    cats = set(page.get('categories') or [])
    ft = first_template(s)
    if ft == 'casting' or re.search(r'\{\{\s*casting\s*\|', s[:3000], re.I):
        return 'casting'
    if ft in ('disambig',) or 'Disambiguation' in cats:
        return 'disambig'
    if ft == 'designer' or 'Designers' in cats:
        return 'designer'
    if re.match(r'list of \d{4}', t, re.I):
        return 'list'
    if re.search(r'monster (jam|trucks?)', t, re.I) and re.search(r'\d{4}', t):
        return 'monster_list'
    if PACK_RE.search(t) or (cats & {'2-Packs', '3-Packs', '5-Packs', '9-Packs', '10-Packs', 'Multipacks', 'Multi-Packs', 'Gift Pack', 'Gift Packs', 'Box Sets'}):
        return 'pack'
    if cats & {'Track Sets', 'Playsets'}:
        return 'trackset'
    if 'Hot Wheels by Series' in cats or re.search(r'series|segment|first editions|new models|treasure hunts|collection', t, re.I):
        return 'series'
    return 'other'


def year_from_page(page):
    m = _YEAR.search(page['title'])
    if m:
        return m.group(1)
    ys = sorted({c[:4] for c in page.get('categories') or [] if re.fullmatch(r'\d{4} Hot Wheels', c)})
    return ys[0] if len(ys) == 1 else ''


# ----------------------------------------------------------- tabelas -------
def iter_tables(s):
    """Gera (seção, tabela-expandida) para cada wikitable da página."""
    parsed = wtp.parse(s)
    for sec in parsed.get_sections(include_subsections=False):
        title = clean(sec.title) if sec.title else ''
        for tb in sec.get_tables():
            if tb.nesting_level > 1:
                continue
            try:
                data = tb.data(span=True)
            except Exception:
                continue
            if data and len(data) > 1:
                yield title, data


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return ''
    return row[idx] or ''


def make_id(year, model, toy, color):
    """Mesmo formato de ID usado pelo Hotwheels Manager (compatível)."""
    return f"{year}-{slug(model)}-{(toy or '').strip().lower()}-{slug(color)}"


def uid_of(*parts):
    return hashlib.sha1('|'.join(parts).encode('utf-8')).hexdigest()[:12]


def parse_casting(page, strict=False):
    """Linhas de versões de uma página {{Casting}}."""
    s, title = page['wikitext'], page['title']
    prm = casting_params(s)
    model = clean(prm.get('name', '')) or title
    designer = clean(prm.get('designer', ''))
    base_series = clean(prm.get('series', ''))
    default_img = image_of('[[File:' + prm['image'] + ']]') if prm.get('image') else ''
    rows = []
    for t_idx, (section, data) in enumerate(iter_tables(s)):
        hm = map_headers(data[0])
        if 'year' not in hm:
            continue
        # tabelas de descrição de cartela, minigames etc.
        if len(hm) < 2:
            continue
        # páginas sem {{Casting}}: só aceita tabela típica de versões
        if strict and ('color' not in hm or 'name' in hm):
            continue
        for r_idx, row in enumerate(data[1:]):
            raw = {k: _cell(row, i) for k, i in hm.items()}
            year_txt = clean(raw.get('year'))
            ym = _YEAR.search(year_txt)
            # linha de cabeçalho repetida ou vazia
            if not ym:
                if not any(clean(v) for v in raw.values()):
                    continue
            year = ym.group(1) if ym else ''
            row_model = clean(raw.get('name')) if 'name' in raw else ''
            rec = {
                'model_name': row_model or model,
                'casting': title,
                'release_year': year,
                'year_raw': year_txt if year_txt != year else '',
                'series': clean(raw.get('series')),
                'series_page': first_link(raw.get('series')),
                'series_#': clean(raw.get('series_num')),
                'col_#': clean(raw.get('col_num')),
                'toy_#': clean(raw.get('toy_num')),
                'color': clean(raw.get('color')),
                'tampo': clean(raw.get('tampo')),
                'base': clean(raw.get('base')),
                'window': clean(raw.get('window')),
                'interior': clean(raw.get('interior')),
                'wheel': clean(raw.get('wheel')),
                'country': clean(raw.get('country')),
                'notes': clean(raw.get('notes')),
                'subset': clean(raw.get('subset')),
                'image_file': image_of(raw.get('photo')) or image_of(raw.get('photo_carded')),
                'section': section,
                'designer': designer,
                'page_url': page_url(title),
                'source': 'casting',
                'pageid': page['pageid'],
            }
            if 'series' in hm and rec['subset'] and rec['subset'].lower() not in ('standard', rec['series'].lower()):
                rec['series'] = f"{rec['series']} - {rec['subset']}" if rec['series'] else rec['subset']
            if 'series' not in hm:
                # Monster trucks: o ano linka para a página da série ("2011 Monster Jam Series")
                yl = first_link(raw.get('year'))
                ser = yl if yl and not re.fullmatch(r'\d{4}', yl) else ''
                if not ser and section and section.lower() not in ('versions', 'releases'):
                    ser = section
                ser = ser or base_series
                if rec['subset'] and rec['subset'].lower() != 'standard':
                    ser = f"{ser} - {rec['subset']}" if ser else rec['subset']
                rec['series'] = ser
                rec['series_page'] = rec['series_page'] or yl
            rec['photo_url'] = file_url(rec['image_file'])
            rec['id'] = make_id(year, rec['model_name'], rec['toy_#'], rec['color'])
            rec['uid'] = uid_of(str(page['pageid']), str(t_idx), str(r_idx))
            rows.append(rec)
    return rows, {'title': title, 'model_name': model, 'designer': designer,
                  'first_series': base_series, 'number': clean(prm.get('number', '')),
                  'years': clean(prm.get('years', '')), 'image_file': default_img,
                  'categories': page.get('categories') or [], 'page_url': page_url(title),
                  'pageid': page['pageid']}


def parse_member_tables(page, kind):
    """Tabelas de packs / pistas / listas / séries: quem está em quê."""
    s, title = page['wikitext'], page['title']
    pyear = year_from_page(page)
    out = []
    for t_idx, (section, data) in enumerate(iter_tables(s)):
        hm = map_headers(data[0])
        if 'name' not in hm:
            continue
        for r_idx, row in enumerate(data[1:]):
            raw = {k: _cell(row, i) for k, i in hm.items()}
            name = clean(raw.get('name'))
            if not name or norm_header(name) in _H:
                continue
            year_txt = clean(raw.get('year'))
            ym = _YEAR.search(year_txt) or _YEAR.search(section)
            out.append({
                'container': title, 'container_type': kind, 'section': section,
                'year': ym.group(1) if ym else pyear,
                'model_name': name, 'casting': first_link(raw.get('name')),
                'series': clean(raw.get('series')) or (section if kind in ('series', 'list') else ''),
                'series_#': clean(raw.get('series_num')),
                'col_#': clean(raw.get('col_num')),
                'toy_#': clean(raw.get('toy_num')),
                'color': clean(raw.get('color')),
                'tampo': clean(raw.get('tampo')),
                'base': clean(raw.get('base')),
                'window': clean(raw.get('window')),
                'interior': clean(raw.get('interior')),
                'wheel': clean(raw.get('wheel')),
                'country': clean(raw.get('country')),
                'notes': clean(raw.get('notes')),
                'subset': clean(raw.get('subset')),
                'image_file': image_of(raw.get('photo')) or image_of(raw.get('photo_carded')),
                'page_url': page_url(title),
                'uid': uid_of(str(page['pageid']), 'm', str(t_idx), str(r_idx)),
            })
    return out


def product_type(categories, title='', has_versions=True):
    """Tipo do produto. Categorias como '5-Packs' também marcam CARROS que saíram
    em 5-packs, então pack/pista só vale para páginas sem tabela de versões."""
    c = set(categories or [])
    mt = any(re.search(r'monster (trucks|jam)', x, re.I) for x in c)
    if has_versions:
        return 'monster_truck' if mt else 'vehicle'
    if PACK_RE.search(title or '') or c & {'Gift Pack', 'Gift Packs', 'Box Sets', '100% Hot Wheels Box Sets'}:
        return 'pack'
    if c & {'Track Sets', 'Playsets'} or TRACK_RE.search(title or ''):
        return 'trackset'
    return 'monster_truck' if mt else 'vehicle'
