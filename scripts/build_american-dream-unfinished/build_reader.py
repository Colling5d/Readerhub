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
            elif p['type'] == 'h1':
                out_type = 'h1'
            elif p['type'] == 'h1sub':
                out_type = 'h1sub'
            elif p['type'] in ('h2', 'h', 'subh'):
                out_type = 'h2'
            elif p['type'] == 'cap':
                out_type = 'cap'
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
    """單語化（隐藏 ZH 栏）+ 中文专著排版层级美化。"""
    css = """
/* ==== MONOLINGUAL (zh-only) ==== */
.main{display:flex !important;flex-direction:column !important;overflow:hidden}
.col.zh{display:none !important}
.col.en{flex:1 1 auto;min-height:0;height:100%;overflow-y:auto;border-right:none !important;max-width:840px;width:100%;margin:0 auto;box-sizing:border-box;padding:0 56px 140px}
.col.en .col-head{display:none !important}
.p.table{margin:1.6em 0;text-align:center}
.p.table img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:6px}

/* ==== 排版层级（中文专著）==== */
.col.en{font-size:17px;line-height:1.95;color:#1f1f1f;text-align:justify}
.col.en .p.p{margin:0 0 1.1em;text-indent:2em}
.col.en .p.p.h1,.col.en .p.p.h1sub,.col.en .p.p.h2,.col.en .p.p.cap{text-indent:0}

/* 章标题（第X章 / 緒章 / 結論 …）*/
.p.h1{
  font-size:27px;font-weight:800;letter-spacing:.06em;text-align:center;
  margin:2.6em 0 1.4em;color:var(--accent);text-indent:0;
  line-height:1.5;
}
.p.h1::after{
  content:"";display:block;width:56px;height:3px;border-radius:2px;
  background:linear-gradient(90deg,var(--accent),transparent);margin:.7em auto 0;
}
/* 章副题 */
.p.h1sub{
  font-size:19px;font-weight:600;letter-spacing:.08em;text-align:center;
  margin:-1em 0 1.8em;color:#5a5a5a;text-indent:0;line-height:1.6;
}
/* 节标题（一、 / （一） / 前言 …）*/
.p.h2{
  font-size:20px;font-weight:700;margin:2.2em 0 .9em;color:#2a2a2a;
  text-align:left;text-indent:0;line-height:1.6;letter-spacing:.02em;
  padding-left:14px;border-left:4px solid var(--accent);
}
/* 表格题注 */
.p.cap{
  font-size:15px;font-weight:600;color:var(--ink-soft,#8a8a8a);
  text-align:center;text-indent:0;margin:2em 0 .6em;letter-spacing:.02em;
}
/* 脚注 */
.note{font-size:13.5px;line-height:1.75;margin:0 0 .5em;color:#5a5a5a;text-indent:0}

/* 首字下沉（每章正文第一段）*/
.p.body-lead{text-indent:0}
.p.body-lead::first-letter{
  float:left;font-size:3.1em;line-height:.86;font-weight:800;
  margin:.06em .12em 0 0;color:var(--accent);
}

@media (max-width:760px){
  .col.en{padding:0 18px 120px;font-size:16px}
  .p.h1{font-size:22px;margin:2em 0 1em}
  .p.h2{font-size:18px}
}
"""
    if 'MONOLINGUAL (zh-only)' not in html:
        html = html.replace('</style>', css + '</style>', 1)

    # --- paraHTML：支持 h1/h1sub/h2/cap/table ---
    old_ph = ("  const cls = p.type==='title' ? 'p title' : (p.type==='note' ? 'note' : 'p');\n"
              "  return `<p class=\"${cls}\" data-lang=\"${lang}\">${t}</p>`;")
    new_ph = ("  if(p.type==='table'){ return `<figure class=\"p table\" data-lang=\"${lang}\"><img loading=\"lazy\" src=\"${t}\" alt=\"表格\"></figure>`; }\n"
              "  if(p.type==='h1'){ return `<p class=\"p h1\" data-lang=\"${lang}\">${t}</p>`; }\n"
              "  if(p.type==='h1sub'){ return `<p class=\"p h1sub\" data-lang=\"${lang}\">${t}</p>`; }\n"
              "  if(p.type==='h2'){ return `<p class=\"p h2\" data-lang=\"${lang}\">${t}</p>`; }\n"
              "  if(p.type==='cap'){ return `<p class=\"p cap\" data-lang=\"${lang}\">${t}</p>`; }\n"
              "  const cls = p.type==='note' ? 'note' : 'p';\n"
              "  return `<p class=\"${cls}\" data-lang=\"${lang}\">${t}</p>`;")
    if old_ph in html:
        html = html.replace(old_ph, new_ph, 1)
    else:
        raise RuntimeError('paraHTML anchor not found')

    # --- 连续滚动渲染 ---
    old_en = ("      var enCls = p.type==='title' ? 'p title' : (p.type==='note' ? 'note' : 'p');\n"
              "      var enHtml = '<p class=\"'+enCls+'\" data-lang=\"en\" data-sec=\"'+id+'\" data-i=\"'+i+'\" data-gi=\"'+myGi+'\">'+(p.text||'')+'</p>';")
    new_en = ("      var enHtml;\n"
              "      var base=' data-lang=\"en\" data-sec=\"'+id+'\" data-i=\"'+i+'\" data-gi=\"'+myGi+'\">';\n"
              "      if(p.type==='table'){\n"
              "        enHtml = '<figure class=\"p table\"'+base+'<img loading=\"lazy\" src=\"'+(p.text||'')+'\" alt=\"表格\"></figure>';\n"
              "      } else if(p.type==='h1'){\n"
              "        enHtml = '<p class=\"p h1\"'+base+(p.text||'')+'</p>';\n"
              "      } else if(p.type==='h1sub'){\n"
              "        enHtml = '<p class=\"p h1sub\"'+base+(p.text||'')+'</p>';\n"
              "      } else if(p.type==='h2'){\n"
              "        enHtml = '<p class=\"p h2\"'+base+(p.text||'')+'</p>';\n"
              "      } else if(p.type==='cap'){\n"
              "        enHtml = '<p class=\"p cap\"'+base+(p.text||'')+'</p>';\n"
              "      } else {\n"
              "        var enCls = p.type==='note' ? 'note' : 'p';\n"
              "        enHtml = '<p class=\"'+enCls+'\"'+base+(p.text||'')+'</p>';\n"
              "      }")
    if old_en in html:
        html = html.replace(old_en, new_en, 1)
    else:
        raise RuntimeError('continuous-scroll anchor not found')

    # --- 每章正文首段首字下沉 ---
    old_loop = "    sec.paras.forEach(function(p, i){\n      var myGi = gi++;"
    new_loop = "    var _leadDone = false;\n    sec.paras.forEach(function(p, i){\n      var myGi = gi++;\n      var _isLead = false;\n      if(!_leadDone && p.type==='text'){ _isLead = true; _leadDone = true; }"
    if old_loop in html:
        html = html.replace(old_loop, new_loop, 1)
    html = html.replace("        var enCls = p.type==='note' ? 'note' : 'p';\n        enHtml = '<p class=\"'+enCls+'\"'+base+(p.text||'')+'</p>';",
                        "        var enCls = p.type==='note' ? 'note' : 'p';\n        if(_isLead && p.type==='text') enCls += ' body-lead';\n        enHtml = '<p class=\"'+enCls+'\"'+base+(p.text||'')+'</p>';", 1)
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
