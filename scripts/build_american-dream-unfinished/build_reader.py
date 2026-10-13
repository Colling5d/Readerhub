#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_reader.py — 單語（繁體中文）版本。
本書為中文原著，無需雙語對照。把中文放進 EN 資料槽（閱讀器主欄），
隱藏 ZH 欄，並將欄頭/標題改為單語樣式。
"""
import json, os, re, sys
import slots

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = '/Users/zhulv/ReaderHub/books/american-dream-unfinished'
os.makedirs(BOOK_DIR, exist_ok=True)

EN_DATA = os.path.join(HERE, 'en_data.json')
TRANS = os.path.join(HERE, 'work', 'translated.json')
BASE_HTML = os.path.join(HERE, 'reader_base.html')
OUT_HTML = os.path.join(BOOK_DIR, 'index.html')


def build_arrays():
    data = json.load(open(EN_DATA, encoding='utf-8'))
    trans = json.load(open(TRANS, encoding='utf-8'))
    en_arr, zh_arr = [], []
    for sec in data:
        sid = sec['id']
        en_paras, zh_paras = [], []
        for i, p in enumerate(sec['paras']):
            key = f"{sid}/{i}"
            t = trans.get(key)
            if p['type'] == 'table':
                out_type = 'table'
            elif p['type'] in ('h', 'subh'):
                out_type = 'title'
            elif p['type'] == 'note':
                out_type = 'note'
            else:
                out_type = 'text'
            # 中文書：正文放入主欄（en）。zh 留空。
            zh_text = (t.get('zh') if t else '') or p['text']
            en_paras.append({"type": out_type, "text": zh_text})
            zh_paras.append({"type": out_type, "text": ""})
        en_arr.append({"id": sid, "title": sec['title'], "paras": en_paras})
        zh_arr.append({"id": sid, "title": sec['title'], "paras": zh_paras})
    return en_arr, zh_arr


def slot_replace(html):
    html = re.sub(r"<title>[^<]*</title>", "<title>美國人未竟的中國夢：企業、技術與關係網</title>", html, count=1)
    html = re.sub(r'<h1>[^<]*</h1>', '<h1>美國人未竟的中國夢</h1>', html, count=1)
    html = re.sub(r'<p>[^<]*Bilingual Edition[^<]*<br>\s*[^<]*</p>',
                  '<p>繁體中文原著 · 吳翎君 著<br>聯經出版，2020</p>', html, count=1, flags=re.S)
    en_start = html.index('const EN = /*__EN__*/')
    zh_start = html.index('const ZH = /*__ZH__*/')
    boom = html.index('[', zh_start); depth = 0; p = boom
    while p < len(html):
        if html[p] == '[':
            depth += 1
        elif html[p] == ']':
            depth -= 1
            if depth == 0:
                break
        p += 1
    zh_end = p + 1
    html = html[:en_start] + '__ENZH_DATA__' + html[zh_end:]
    html = re.sub(r"var SENT_ALIGN=\{.*?\};", "var SENT_ALIGN=__SENT_ALIGN__;", html, count=1, flags=re.S)
    html = re.sub(r"var POS_KEY = 'readerhub_pos_[^']*'", "var POS_KEY = 'readerhub_pos_american-dream-unfinished'", html, count=1)
    html = re.sub(r"var BOOK_KEY = 'readerhub_notes_[^']*'", "var BOOK_KEY = 'readerhub_notes_american-dream-unfinished'", html, count=1)
    html = html.replace(": 'introduction';", ": 'intro';")
    _first = json.dumps(slots.TOC_ORDER[0] if slots.TOC_ORDER else 'intro')
    html = html.replace("? SAVED_POS.section : 'intro';", "? SAVED_POS.section : " + _first + ";")
    html = html.replace("? SAVED_POS.section : 'introduction';", "? SAVED_POS.section : " + _first + ";")
    html = re.sub(r"const tocOrder = \[.*?\];", "const tocOrder = " + json.dumps(slots.TOC_ORDER) + ";", html, count=1, flags=re.S)
    html = replace_map(html, 'function tocLabel(s){', '  return map[s.id];', slots.TOC_LABEL_BODY)
    html = replace_map(html, 'const titleMap=', "\n\n  // Section title", slots.TITLE_MAP_BODY)
    html = replace_map(html, 'function secTitle(id){', '  return map[id] || id;', slots.SECTITLE_BODY)
    html = html.replace("if(id==='introduction' || id==='notes'){", "if(id==='intro' || id==='notes'){")
    return html


def replace_map(html, lead_anchor, tail_anchor, body):
    if not isinstance(body, str):
        body = json.dumps(body, ensure_ascii=False, indent=4)
    li = html.find(lead_anchor)
    if li == -1:
        raise RuntimeError('lead anchor not found: ' + lead_anchor)
    mp = html.find('const map = {', li)
    mp2 = html.find('const titleMap=', li)
    if mp2 != -1 and (mp == -1 or mp2 < mp):
        start = mp2 + len('const titleMap=')
    elif mp != -1:
        start = mp + len('const map = ')
    else:
        raise RuntimeError('map body start not found')
    end = html.find('};', start)
    if end == -1:
        raise RuntimeError('map closing not found')
    body = body.rstrip()
    if body.endswith('}'):
        body = body[:-1].rstrip() + ' '
    return html[:start] + body + html[end:]


def mono_patch(html):
    """單語化：隱藏 ZH 欄，讓主欄佔滿，並改欄頭文案；表格以圖片呈現。"""
    css = """
/* ==== MONOLINGUAL (zh-only) ==== */
.main{display:block !important}
.col.zh{display:none !important}
.col.en{border-right:none !important;max-width:840px;margin:0 auto}
.col.en .col-head{display:none !important}
.p.table{margin:1.2em 0;text-align:center}
.p.table img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:6px}
"""
    html = html.replace('</style>', css + '</style>', 1)
    # 讓 paraHTML 支援 table 型別（顯示表格圖片）
    old = ("function paraHTML(p, lang){\n"
           "  const t = p.text || '';\n"
           "  const cls = p.type==='title' ? 'p title' : (p.type==='note' ? 'note' : 'p');\n"
           "  return `<p class=\"${cls}\" data-lang=\"${lang}\">${t}</p>`;\n"
           "}")
    new = ("function paraHTML(p, lang){\n"
           "  const t = p.text || '';\n"
           "  if(p.type==='table'){ return `<figure class=\"p table\" data-lang=\"${lang}\"><img loading=\"lazy\" src=\"${t}\" alt=\"表格\"></figure>`; }\n"
           "  const cls = p.type==='title' ? 'p title' : (p.type==='note' ? 'note' : 'p');\n"
           "  return `<p class=\"${cls}\" data-lang=\"${lang}\">${t}</p>`;\n"
           "}")
    if old in html:
        html = html.replace(old, new, 1)
    else:
        raise RuntimeError('paraHTML anchor not found')
    return html


def inject_data(html, en_arr, zh_arr, sent_align):
    enzh = ("const EN = /*__EN__*/" + json.dumps(en_arr, ensure_ascii=False) +
            ";\nconst ZH = /*__ZH__*/" + json.dumps(zh_arr, ensure_ascii=False) + ";")
    html = html.replace("__ENZH_DATA__", enzh)
    html = html.replace("__SENT_ALIGN__", json.dumps(sent_align, ensure_ascii=False))
    return html


def main():
    en_arr, zh_arr = build_arrays()
    sent_align = {}
    html = open(BASE_HTML, encoding='utf-8').read()
    html = slot_replace(html)
    html = inject_data(html, en_arr, zh_arr, sent_align)
    html = mono_patch(html)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print('sections:', len(en_arr))
    print('wrote', OUT_HTML, os.path.getsize(OUT_HTML), 'bytes')


if __name__ == '__main__':
    main()
