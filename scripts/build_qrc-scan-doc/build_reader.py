#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_reader.py (custom, for samoylov-russia-china-lecture)
基于模板 build_reader.py，额外把双语标签改为「俄汉对照」/「俄文原文」/「中文翻译」。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = '/Users/zhulv/ReaderHub/docs/samoylov-russia-china-lecture'
os.makedirs(BOOK_DIR, exist_ok=True)

EN_DATA = os.path.join(HERE, 'en_data.json')
TRANS = os.path.join(HERE, 'work', 'translated.json')
BASE_HTML = os.path.join(HERE, 'reader_base.html')
OUT_HTML = os.path.join(BOOK_DIR, 'index.html')

TITLE = 'РОССИЯ И КИТАЙ: ДИАЛОГ КУЛЬТУР · ЛЕКЦИЯ 1'
AUTHOR_ATTR = 'Н.А. Самойлов · 尼·阿·萨莫伊洛夫'
POS_KEY = 'readerhub_pos_samoylov-russia-china-lecture'
BOOK_KEY = 'readerhub_notes_samoylov-russia-china-lecture'

import slots


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
            out_type = 'title' if p['type'] in ('h', 'subh') else ('note' if p['type'] == 'note' else 'text')
            if t:
                en_text = t.get('en') or p['text']
                zh_text = t.get('zh') or ''
            else:
                en_text = p['text']; zh_text = ''
            en_paras.append({"type": out_type, "text": en_text})
            zh_paras.append({"type": out_type, "text": zh_text})
        en_arr.append({"id": sid, "title": sec['title'], "paras": en_paras})
        zh_arr.append({"id": sid, "title": sec['title'], "paras": zh_paras})
    return en_arr, zh_arr


def compute_ranges(sents, text):
    if not sents or not text:
        return None
    ranges = []; cursor = 0; textlen = len(text)
    for sn in sents:
        lo = text.find(sn, cursor)
        if lo == -1:
            lo = tolerant_find(text, re.sub(r'\s+', ' ', sn), cursor)
        if lo == -1:
            ranges.append([0, 0]); continue
        end = min(lo + len(sn), textlen)
        ranges.append([lo, end]); cursor = end if end > cursor else cursor + 1
    return ranges


def tolerant_find(text, flat_needle, cursor):
    window = text[cursor: cursor + len(flat_needle) * 2 + 40]
    flat = re.sub(r'\s+', ' ', window)
    pos = flat.find(flat_needle)
    if pos == -1:
        return -1
    fidx = 0; prev_ws = False
    for i, ch in enumerate(window):
        if ch.isspace():
            if prev_ws: continue
            if fidx >= pos: return cursor + i
            fidx += 1; prev_ws = True
        else:
            if fidx >= pos: return cursor + i
            fidx += 1; prev_ws = False
    return cursor


def build_sent_align(en_arr, align_sources):
    out = {}
    for sec in en_arr:
        sid = sec['id']
        for i, p in enumerate(sec['paras']):
            if p['type'] != 'text':
                continue
            key = f"{sid}/{i}"; t = align_sources.get(key)
            if not t:
                continue
            en_ranges = compute_ranges(t.get('en_sents', []), p['text'])
            zh_ranges = compute_ranges(t.get('zh_sents', []), t.get('zh') or '')
            if not en_ranges or not zh_ranges:
                continue
            pairs = [[int(pj[0]), int(pj[1])] for pj in (t.get('align') or []) if isinstance(pj, (list, tuple)) and len(pj) >= 2]
            out[key] = {"en": en_ranges, "zh": zh_ranges, "m": pairs}
    return out


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


def slot_replace(html):
    html = re.sub(r"<title>[^<]*</title>", "<title>" + TITLE + " — 俄汉对照在线阅读</title>", html, count=1)
    html = re.sub(r'<h1>[^<]*</h1>', '<h1>' + TITLE + '</h1>', html, count=1)
    html = re.sub(r'<p>中英对照版 · Bilingual Edition\s*<br>[^<]*</p>',
                  '<p>俄汉对照版 · Russian–Chinese Edition<br>' + AUTHOR_ATTR + '</p>', html, count=1, flags=re.S)
    # 栏头：俄文原文 / 中文翻译
    html = html.replace('<header class="col-head">English · 英文原文</header>',
                        '<header class="col-head">Русский · 俄文原文</header>')
    html = html.replace('<header class="col-head">中文翻译 · Chinese</header>',
                        '<header class="col-head">中文翻译 · Китайский</header>')
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
    html = re.sub(r"var POS_KEY = 'readerhub_pos_[^']*'", "var POS_KEY = '" + POS_KEY + "'", html, count=1)
    html = re.sub(r"var BOOK_KEY = 'readerhub_notes_[^']*'", "var BOOK_KEY = '" + BOOK_KEY + "'", html, count=1)
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


def inject_data(html, en_arr, zh_arr, sent_align):
    enzh = ("const EN = /*__EN__*/" + json.dumps(en_arr, ensure_ascii=False) +
            ";\nconst ZH = /*__ZH__*/" + json.dumps(zh_arr, ensure_ascii=False) + ";")
    html = html.replace("__ENZH_DATA__", enzh)
    html = html.replace("__SENT_ALIGN__", json.dumps(sent_align, ensure_ascii=False))
    return html


def main():
    en_arr, zh_arr = build_arrays()
    trans = json.load(open(TRANS, encoding='utf-8'))
    align_sources = {k: v for k, v in trans.items() if v.get('type') == 'C'}
    sent_align = build_sent_align(en_arr, align_sources)
    print("sections:", len(en_arr), "| aligned paragraphs:", len(sent_align))
    total_text = sum(1 for s in en_arr for p in s['paras'] if p['type'] == 'text')
    print("total text paras:", total_text)
    missing = [f"{s['id']}/{i}" for s in en_arr for i, p in enumerate(s['paras'])
               if p['type'] == 'text' and f"{s['id']}/{i}" not in trans]
    print("missing translations:", len(missing))
    html = open(BASE_HTML, encoding='utf-8').read()
    html = slot_replace(html)
    html = inject_data(html, en_arr, zh_arr, sent_align)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print('wrote', OUT_HTML, os.path.getsize(OUT_HTML), 'bytes')


if __name__ == '__main__':
    main()
