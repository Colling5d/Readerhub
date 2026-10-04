#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 translated.json + en_data.json 生成 SENT_ALIGN，并基于 reader_base.html 拼装新书阅读器。
产出新书的 index.html / metadata.json（在仓储目标位置）。
"""
import json, os, re, sys
import slots

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = "/Users/zhulv/ReaderHub/books/winning-third-world"
os.makedirs(BOOK_DIR, exist_ok=True)

EN_DATA = os.path.join(HERE, 'en_data.json')
TRANS = os.path.join(HERE, 'work', 'translated.json')
BASE_HTML = os.path.join(HERE, 'reader_base.html')
OUT_HTML = os.path.join(BOOK_DIR, 'index.html')

# ---------------- 1. 构建 EN / ZH 数组 ----------------
def build_arrays():
    data = json.load(open(EN_DATA, encoding='utf-8'))
    trans = json.load(open(TRANS, encoding='utf-8'))
    def get(key):
        return trans.get(key)
    en_arr = []
    zh_arr = []
    for sec in data:
        sid = sec['id']
        en_paras = []
        zh_paras = []
        for i, p in enumerate(sec['paras']):
            key = f"{sid}/{i}"
            t = get(key)
            ptype = p['type']
            # 映射：h / subh -> title（阅读器支持 title 子标题）
            out_type = 'title' if ptype in ('h', 'subh') else ('note' if ptype == 'note' else 'text')
            if t:
                en_text = t.get('en') or p['text']
                zh_text = t.get('zh') or ''
            else:
                en_text = p['text']
                zh_text = ''
            en_paras.append({"type": out_type, "text": en_text})
            zh_paras.append({"type": out_type, "text": zh_text})
        en_arr.append({"id": sid, "title": sec['title'], "paras": en_paras})
        zh_arr.append({"id": sid, "title": sec['title'], "paras": zh_paras})
    return en_arr, zh_arr

# ---------------- 2. 句子 -> 字符区间 ----------------
def compute_ranges(sents, text):
    """把 sents 列表映射为 [[s,e],...]（字符区间）；定位失败返回 [0,0]，尽力而为。
    与现有 embed 逻辑一致：宽容空白、逐句定位并在原文中消掉已用区域。"""
    if not sents or not text:
        return None
    ranges = []
    cursor = 0
    textlen = len(text)
    for sn in sents:
        fs = re.sub(r'\s+', ' ', sn)
        lo = text.find(sn, cursor)
        if lo == -1:
            # 尝试宽容空白定位
            lo = tolerant_find(text, fs, cursor)
        if lo == -1:
            ranges.append([0, 0])
            continue
        end = lo + len(sn)
        # 允许越界裁剪
        end = min(end, textlen)
        ranges.append([lo, end])
        cursor = end if end > cursor else cursor + 1
    return ranges

def tolerant_find(text, flat_needle, cursor):
    """宽容空白：把原文游标附近压平为空单空格后再 find。"""
    window = text[cursor: cursor + len(flat_needle) * 2 + 40]
    flat = re.sub(r'\s+', ' ', window)
    pos = flat.find(flat_needle)
    if pos == -1:
        return -1
    # 把 flat 下标映射回原文下标（统计非空白字符+首个空白）
    ci = 0
    prev_ws = False
    flat_idx = 0
    for i, ch in enumerate(window):
        if ch.isspace():
            if prev_ws:
                continue
            if flat_idx >= pos:
                return cursor + i
            flat_idx += 1
            prev_ws = True
        else:
            if flat_idx >= pos:
                return cursor + i
            flat_idx += 1
            prev_ws = False
    return cursor

def build_sent_align(en_arr, align_sources):
    """align_sources: dict key->translated obj"""
    out = {}
    for sec in en_arr:
        sid = sec['id']
        for i, p in enumerate(sec['paras']):
            if p['type'] == 'text':
                key = f"{sid}/{i}"
                t = align_sources.get(key)
                if not t:
                    continue
                en_ranges = compute_ranges(t.get('en_sents', []), p['text'])
                zh_ranges = compute_ranges(t.get('zh_sents', []), t.get('zh') or '')
                al = t.get('align') or []
                if not en_ranges or not zh_ranges:
                    continue
                pairs = []
                for pair in al:
                    if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                        pairs.append([int(pair[0]), int(pair[1])])
                out[key] = {"en": en_ranges, "zh": zh_ranges, "m": pairs}
    return out

# ---------------- 3. slot 替换 ----------------
def slot_replace(html):
    # 1) title
    html = re.sub(r"<title>[^<]*</title>",
                  "<title>Winning the Third World — 中英对照在线阅读</title>", html, count=1)
    # 2) 侧栏品牌（书名用英文名，作者行跨换行匹配；base 复自《共有的历史》，匹配其真实书名/作者）
    html = re.sub(r'<h1>[^<]*Chinese and Americans: A Shared History[^<]*</h1>', '<h1>Winning the Third World</h1>', html, count=1)
    html = re.sub(r'<p>中英对照版 · Bilingual Edition\s*<br>\s*Xu Guoqi · 徐国琦</p>',
                  '<p>中英对照版 · Bilingual Edition<br>Gregg A. Brazinsky · 格雷格·A·布拉金斯基</p>', html, count=1, flags=re.S)
    # 3) EN / ZH 数据（去掉原 /*__EN__*/ 等标记与数组）——按唯一标记索引替换
    en_start = html.index('const EN = /*__EN__*/')
    zh_start = html.index('const ZH = /*__ZH__*/')
    # ZH 数组从 zh_start 处 '[' 开始，找其匹配的 ']'（数组内部可能嵌套，用深度扫描）
    boom = html.index('[', zh_start)
    depth = 0
    p = boom
    while p < len(html):
        c = html[p]
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                break
        p += 1
    zh_end = p + 1
    html = html[:en_start] + '__ENZH_DATA__' + html[zh_end:]
    # 4) SENT_ALIGN
    html = re.sub(r"var SENT_ALIGN=\{.*?\};", "var SENT_ALIGN=__SENT_ALIGN__;", html, count=1, flags=re.S)
    # 5) POS_KEY + BOOK_KEY（笔记存储键，必须随书独立）
    html = re.sub(r"var POS_KEY = 'readerhub_pos_[^']*'",
                  "var POS_KEY = 'readerhub_pos_winning-third-world'", html, count=1)
    html = re.sub(r"var BOOK_KEY = 'readerhub_notes_[^']*'",
                  "var BOOK_KEY = 'readerhub_notes_winning-third-world'", html, count=1)
    # 6) 默认启动章节 introduction -> intro
    html = html.replace(": 'introduction';", ": 'intro';")
    # 7) TOC 顺序
    html = re.sub(r"const tocOrder = \[.*?\];", "const tocOrder = " + json.dumps(slots.TOC_ORDER) + ";", html, count=1, flags=re.S)
    # 8) tocLabel 映射（锚定函数签名）
    html = replace_map(html, 'function tocLabel(s){', '  return map[s.id];', slots.TOC_LABEL_BODY)
    # 9) goTo 里的 titleMap（锚定 'const titleMap='）
    html = replace_map(html, 'const titleMap=', "\n\n  // Section title", slots.TITLE_MAP_BODY)
    # 10) secTitle 映射（锚定函数签名）
    html = replace_map(html, 'function secTitle(id){', '  return map[id] || id;', slots.SECTITLE_BODY)
    # 11) TOC 分隔符条件：introduction -> intro
    html = html.replace("if(id==='introduction' || id==='notes'){", "if(id==='intro' || id==='notes'){")
    return html

def replace_map(html, lead_anchor, tail_anchor, body):
    """在 lead_anchor 之后、tail_anchor 之前，把  'const map|titleMap = {...};' 替换为新 body。
    lead_anchor: 锚定起点（含），沿此往后的第一个 'const map = {' 被替换。
    """
    li = html.find(lead_anchor)
    if li == -1:
        raise RuntimeError('lead anchor not found: ' + lead_anchor)
    # 在 lead 之后找 'const map = {' 或 'const titleMap='
    mp = html.find('const map = {', li)
    mp2 = html.find('const titleMap=', li)
    if mp2 != -1 and (mp == -1 or mp2 < mp):
        start = mp2 + len('const titleMap=')
    elif mp != -1:
        start = mp + len('const map = ')
    else:
        raise RuntimeError('map body start not found after: ' + lead_anchor)
    # 找对应闭合的 '};'（非嵌套简单处理——这些 map 无嵌套花括号）
    end = html.find('};', start)
    if end == -1:
        raise RuntimeError('map closing not found after ' + lead_anchor)
    # 去掉 body 尾部自带的花括号，交给原 '};' 提供闭合 → 避免 '}};'。
    body = body.rstrip()
    if body.endswith('}'):
        body = body[:-1].rstrip() + ' '
    # start 恰在 'const map/titleMap =' 之后、'...};' 之前 → 直接替换身体，不重复前缀
    return html[:start] + body + html[end:]


def inject_data(html, en_arr, zh_arr, sent_align):
    en_js = json.dumps(en_arr, ensure_ascii=False)
    zh_js = json.dumps(zh_arr, ensure_ascii=False)
    enzh = f"const EN = /*__EN__*/{en_js};\nconst ZH = /*__ZH__*/{zh_js};"
    sa = json.dumps(sent_align, ensure_ascii=False)
    html = html.replace("__ENZH_DATA__", enzh)
    html = html.replace("__SENT_ALIGN__", sa)
    return html

def main():
    en_arr, zh_arr = build_arrays()
    trans = json.load(open(TRANS, encoding='utf-8'))
    align_sources = {k: v for k, v in trans.items() if v.get('type') == 'C'}
    sent_align = build_sent_align(en_arr, align_sources)
    print("sections:", len(en_arr), "| aligned paragraphs:", len(sent_align))
    total_text = sum(1 for s in en_arr for p in s['paras'] if p['type'] == 'text')
    print("total text paras:", total_text)
    # 未翻译计数
    missing = [f"{s['id']}/{i}" for s in en_arr for i, p in enumerate(s['paras'])
               if p['type'] == 'text' and f"{s['id']}/{i}" not in trans]
    print("missing translations:", len(missing))
    if missing:
        print("  first 10:", missing[:10])
    html = open(BASE_HTML, encoding='utf-8').read()
    html = slot_replace(html)
    html = inject_data(html, en_arr, zh_arr, sent_align)
    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print("wrote", OUT_HTML, os.path.getsize(OUT_HTML), "bytes")

if __name__ == '__main__':
    main()