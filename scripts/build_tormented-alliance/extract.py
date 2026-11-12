#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The Tormented Alliance (Zach Fredman, UNC Press 2022) —— 原生文字层抽取 + 分节。

本书 PDF 有完整文字层（Quartz 生成，无 OCR 噪声），故不走 MinerU/OCR：
  1) 取每页文字，丢掉页眉（running head）与页码；
  2) 按段落 break 拼接（行尾连字符合并）；
  3) 按 SECTIONS 切节，抽小标题与注释编号。

输出：
  stream_raw.json   [{page, type, text, lvl}]
  en_data.json      [{id,title,paras:[{type,text}]}]
  work/pages.json   页面诊断
"""
import json, os, re, sys
import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.join(HERE, 'book.pdf')
if not os.path.exists(BOOK):
    BOOK = ('/Users/zhulv/Documents/2026年秋-中美关系史研究课程材料/2026中美关系专题'
            '（阅读书目）/Zach Fredman，The Tormented Alliance- American Servicemen and the-- '
            '2022 -- Univ of North Carolina Pr.pdf')
WORK = os.path.join(HERE, 'work')
os.makedirs(WORK, exist_ok=True)

# 0 基页索引（含），据 Contents 与实际章首页核对
SECTIONS = [
    ('front',   'Front Matter',                       (0, 23),   'front'),
    ('intro',   'Introduction',                       (24, 45),  ''),
    ('ch1',     'Chapter 1 · Making Our Friends at Home', (46, 75),  ''),
    ('ch2',     'Chapter 2 · Communicating without Understanding', (76, 111), ''),
    ('ch3',     'Chapter 3 · Unequal Partners',       (112, 143), ''),
    ('ch4',     'Chapter 4 · Living with the U.S. Military', (144, 176), ''),
    ('ch5',     'Chapter 5 · GIs and Jeep Girls',     (177, 209), ''),
    ('ch6',     'Chapter 6 · Everything Comes Undone', (210, 248), ''),
    ('epilogue', 'Epilogue · The Occupation of China’s Long Shadow', (249, 261), ''),
    ('notes',   'Notes',                              (262, 369), 'notes'),
    ('biblio',  'Bibliography',                       (370, 415), 'nofn'),
    ('index',   'Index',                              (416, 447), 'nofn'),
]

NOTES_SUBHEADS = {"Introduction", "1 Making Our Friends at Home",
                  "2 Communicating without Understanding", "3 Unequal Partners",
                  "4 Living with the U.S. Military", "5 GIs and Jeep Girls",
                  "6 Everything Comes Undone", "Epilogue"}

RUNNING_HEADS = {"the tormented alliance"}


def is_page_no(s):
    s = s.strip()
    return bool(re.fullmatch(r'[ivxlcdm]{1,7}|\d{1,3}', s, re.I))


def norm(s):
    return ' '.join(s.split())


def join_hyph(prev, nxt):
    """页内/跨页断字：'inter-'+'preters' → 'interpreters'。"""
    if prev.endswith('-') and re.match(r'^[a-z]', nxt):
        return prev[:-1] + nxt
    return prev + ' ' + nxt


def page_blocks(pdf, i):
    """返回该页文字块（已去页眉/页码），块内已拼行、已合并断字。"""
    d = pdf[i].get_text('dict')
    lines = []
    for b in d.get('blocks', []):
        if b.get('type') != 0:
            continue
        for ln in b.get('lines', []):
            txt = ''.join(s.get('text', '') for s in ln.get('spans', []))
            txt = txt.replace('\u00ad', '')
            if not txt.strip():
                continue
            y0 = ln['bbox'][1]
            size = max((s.get('size', 0) for s in ln.get('spans', [])), default=0)
            bold = any('Bold' in s.get('font', '') or s.get('flags', 0) & 16
                       for s in ln.get('spans', []))
            lines.append({'text': txt.rstrip(), 'y': y0, 'size': size, 'bold': bold,
                          'x': ln['bbox'][0], 'page': i})
    lines.sort(key=lambda z: z['y'])
    out = []
    for ln in lines:
        t = ln['text'].strip()
        if not t:
            continue
        if is_page_no(t):
            continue
        if t.lower() in RUNNING_HEADS:
            continue
        out.append(ln)
    return out


SUP_CHARS = '⁰¹²³⁴⁵⁶⁷⁸⁹'
SUP_MAP = {c: str(i) for i, c in enumerate(SUP_CHARS)}
SUP_RE = re.compile('[' + SUP_CHARS + ']+')


def sup_to_tag(s):
    """Unicode 上标数字（¹²³…）→ <sup>N</sup>，供阅读器脚注悬浮识别。"""
    if not isinstance(s, str):
        return s
    return SUP_RE.sub(lambda m: '<sup>' + ''.join(SUP_MAP[c] for c in m.group(0)) + '</sup>', s)


SENT_END = re.compile(r'[.!?\u201d\u2019")]\s*$')


def section_lines(pages, a, b):
    """把 [a,b] 页码范围的所有行串成连续流，并标出页边界。
    页首行若上一页末行未以句末标点结束（正文被分页切断），则强制续接。"""
    out = []
    for pi in range(a, b + 1):
        lines = pages[pi]['lines']
        for k, ln in enumerate(lines):
            rec = dict(ln)
            rec['page_start'] = (k == 0)
            out.append(rec)
    return out


def paragraphs_from_stream(lines, gap_thr=24.0, marks=None, crosspage=True):
    """按行间空隙断段；跨页时用句末标点判断是否续段。
    marks 若给出，则记录每个段落的起始行与是否加粗（用于识别小标题）。"""
    paras = []
    cur = None
    start_info = None
    prev_y = None
    prev_page = None
    for ln in lines:
        t = ln['text']
        if cur is None:
            cur = t
            start_info = (ln.get('bold', False), ln.get('y', 0), ln.get('page'))
        else:
            if ln['page_start'] and ln.get('page') != prev_page:
                # 跨页：上一段未以句末标点收尾 → 视为同一段（去掉页首残余，直接续）
                cont = crosspage and not SENT_END.search(cur.strip())
            else:
                cont = (ln['y'] - prev_y) <= gap_thr
            if cont:
                cur = join_hyph(cur, t)
            else:
                paras.append(cur)
                if marks is not None:
                    marks.append({'bold': start_info[0], 'y': start_info[1],
                                  'page': start_info[2]})
                cur = t
                start_info = (ln.get('bold', False), ln.get('y', 0), ln.get('page'))
        prev_y = ln['y']
        prev_page = ln.get('page')
    if cur:
        paras.append(cur)
        if marks is not None:
            marks.append({'bold': start_info[0], 'y': start_info[1], 'page': start_info[2]})
    return [norm(p) for p in paras]


def finalize_front(results, pages, section_lines, paragraphs_from_stream):
    """front matter（0–23 页段落流）按内容锚点顺序切分：
       扉页/版权 → front；To my family Contents … Figures/Maps 清单 → figs；
       Acknowledgments → ack；Chronology … → chrono。"""
    byid = {s['id']: s for s in results}
    front = byid.get('front')
    if not front:
        return results
    # 重新从页块生成 front matter 段落流（不依赖已处理过的 front['paras']）
    lines = section_lines(pages, 0, 23)
    blocks = paragraphs_from_stream(lines, 24.0, crosspage=False)
    paras = []
    for t in blocks:
        if not t or re.fullmatch(r'[\d\.\-\s]+', t):
            continue
        paras.append({'type': 'text', 'text': t})
    texts = [p['text'].strip() for p in paras]

    def find_all(val):
        return [i for i, t in enumerate(texts) if t == val]

    # 目录区：'Contents' 之后到 'Index' 之后（目录清单）
    i_contents = texts.index('Contents')
    toc_end = max(find_all('Index'))
    # 图表清单：目录里第二个 'Figures and Maps' 起，到 'Maps' 段清单结束
    i_figlist = [i for i in find_all('Figures and Maps') if i > toc_end][0]
    last_map = max(i for i, t in enumerate(texts)
                   if t in ('China, December 1941', 'The U.S. military in Southwest China',
                            'Chinese retreat from Burma, 1942', 'North China, 1945'))
    # 致谢：最后一个 'Acknowledgments'（正文致谢标题）
    i_ack = max(find_all('Acknowledgments'))
    i_chr = max(i for i, t in enumerate(texts) if t.startswith('Chronology of Wartime'))
    i_tofamily = texts.index('To my family')

    head = paras[:i_tofamily]
    toc = [{'type': 'h', 'text': 'Contents'}] + paras[i_contents + 1:toc_end + 1]
    figs = [{'type': 'subh', 'text': 'Figures and Maps'}] + paras[i_figlist + 1:i_ack]
    # 去掉 figs 里夹的 'Figures' 小标题重复与目录残余
    figs = [p for p in figs if p['text'].strip() not in ('Figures', 'Maps', 'Contents')]
    ack = paras[i_ack:i_chr]
    ack[0] = {'type': 'h', 'text': 'Acknowledgments'}
    chrono = [{'type': 'h',
               'text': 'Chronology of Wartime Sino-American Relations and the U.S. Military Presence in China'}] \
        + chrono_entries(pages, 17, 20)
    # 年表尾部的两张地图名残留
    chrono = [p for p in chrono if p['text'].strip() not in
              ('China, December 1941', 'The U.S. military in Southwest China',
               'Chinese retreat from Burma, 1942', 'North China, 1945', 'Maps', 'Figures')]
    # 年份后无事件的孤立块（如只含 '1941'）并入相邻块
    merged = []
    for p in chrono:
        if (merged and p['type'] == 'text' and re.fullmatch(r'19\d{2}', p['text'].strip())):
            merged[-1]['text'] = merged[-1]['text'] + ' ' + p['text']
            continue
        merged.append(p)
    chrono = merged

    head.insert(0, {'type': 'h', 'text': 'The Tormented Alliance'})
    front['paras'] = head
    def put(sid, title, arr):
        node = byid.get(sid)
        if node is None:
            node = {'id': sid, 'title': title, 'paras': []}
            results.append(node); byid[sid] = node
        node['paras'] = arr
    put('figs', 'Figures and Maps', figs)
    put('ack', 'Acknowledgments', ack)
    put('chrono', 'Chronology of Wartime Sino-American Relations and the U.S. Military Presence in China', chrono)
    return results


YEAR_RE = re.compile(r'\b(19[0-9]{2})\b')
MONTH_RE = re.compile(r'^(January|February|March|April|May|June|July|August|September|'
                      r'October|November|December|September to|October to)')


def chrono_entries(pages, a, b):
    """年表页是两栏版式：左栏日期（x<150），右栏事件（x>=150）。
    按 y 聚行，同一行的日期与事件配成一条。"""
    rows = []
    for pi in range(a, b + 1):
        for ln in pages[pi]['lines']:
            rows.append(ln)
    rows.sort(key=lambda z: (z['page'], round(z['y'], 1)))
    # 按 (page, y) 聚成行
    lines = []
    for ln in rows:
        if lines and lines[-1][0] == ln['page'] and abs(lines[-1][1] - ln['y']) < 4:
            lines[-1][2].append(ln)
        else:
            lines.append([ln['page'], ln['y'], [ln]])
    out = []
    cur_year = ''
    for _pg, _y, group in lines:
        group.sort(key=lambda z: z.get('x', 0))
        left = [g for g in group if g.get('x', 0) < 170]
        right = [g for g in group if g.get('x', 0) >= 170 and len(g['text'].strip()) > 1]
        ltxt = ' '.join(g['text'].strip() for g in left).strip()
        ltxt = re.sub(r'^C\s+', '', ltxt)
        rtxt = ' '.join(g['text'].strip() for g in right).strip()
        if not ltxt and not rtxt:
            continue
        if re.fullmatch(r'19\d{2}', ltxt):
            cur_year = ltxt
            if rtxt:
                out.append({'type': 'text', 'text': f'{cur_year}\n{rtxt}'})
            continue
        if ltxt.startswith('Chronology'):
            continue
        if MONTH_RE.match(ltxt) or re.match(r'^(January|February|March|April|May|June|July|'
                                            r'August|September|October|November|December)', ltxt):
            entry = f'{cur_year} · {ltxt}'
            if rtxt:
                entry += f' — {rtxt}'
            out.append({'type': 'text', 'text': entry})
        elif rtxt:
            # 事件续行，接到上一条
            if out:
                out[-1]['text'] += ' ' + rtxt
        elif re.match(r'^(China, December|The U\.S\. military in Southwest|'
                      r'Chinese retreat from Burma|North China, 1945)', ltxt):
            continue
    return out


def split_chronology(paras):
    """年表页 PDF 把日期与事件挤成大段，这里尽量按 '年份 月日 事件' 切开。"""
    out = []
    for p in paras:
        if p['type'] == 'h':
            out.append(p); continue
        t = p['text']
        # 在 "19XX" 前插入分隔，便于阅读（不改变内容）
        parts = re.split(r'(?=\b(?:19[0-9]{2})\b)', t)
        for seg in parts:
            seg = seg.strip()
            if seg:
                out.append({'type': 'text', 'text': seg})
    return out


def main():
    pdf = fitz.open(BOOK)
    n = pdf.page_count
    print('pages', n, flush=True)
    pages = []
    for i in range(n):
        lines = page_blocks(pdf, i)
        pages.append({'page': i, 'nlines': len(lines), 'lines': lines})
    json.dump([{'page': p['page'], 'nlines': p['nlines']} for p in pages],
              open(os.path.join(WORK, 'pages.json'), 'w'), ensure_ascii=False)

    results = []
    for sid, title, (a, b), kind in SECTIONS:
        gap = 24.0
        lines = section_lines(pages, a, b)
        marks = []
        blocks = paragraphs_from_stream(lines, gap, marks,
                                        crosspage=(kind == ''))
        paras = []
        for bi, t in enumerate(blocks):
            if not t or re.fullmatch(r'[\d\.\-\s]+', t):
                continue
            if kind == 'notes':
                if t in NOTES_SUBHEADS:
                    paras.append({'type': 'subh', 'text': t}); continue
                if re.match(r'^\d{1,3}\.\s', t) or re.match(r'^[a-z]\.\s', t):
                    paras.append({'type': 'note', 'text': t}); continue
                if paras and paras[-1]['type'] == 'note':
                    paras[-1]['text'] = norm(join_hyph(paras[-1]['text'], t))
                else:
                    paras.append({'type': 'note', 'text': t})
                continue
            # 编辑插入语 / 断页残片：方括号片段、以标点起头、以标点/方括号收尾的短句
            frag = (('[' in t and len(t) < 90) or
                    (len(t) < 70 and re.match(r'^[\[(\)\],.;“”\u2019\u201d]', t) and not t[:1].isupper()) or
                    (len(t) < 45 and re.search(r'[\[\u201c,(]$', t)) or
                    (len(t) < 45 and re.search(r'^[a-z\u201d\u2019.,;]', t) and not re.match(r'^[a-z]+ ', t)))
            if kind != 'front' and frag and paras and paras[-1]['type'] in ('text',):
                paras[-1]['text'] = norm(paras[-1]['text'] + ' ' + t)
                continue
            mk = marks[bi] if bi < len(marks) else {}
            ishead = (kind != 'front' and mk.get('bold') and len(t) < 80 and not t.endswith('.')
                      and not t.endswith('.”') and not re.match(r'^\d+\.', t))
            paras.append({'type': 'subh' if ishead else 'text', 'text': t})
        # 后向修补：段落以残缺片段起头则并回前段
        fixed = []
        for p in paras:
            if (kind != 'front' and fixed and p['type'] == 'text' and len(p['text']) < 70 and
                    re.match(r'^[\[\u2019\u201d,.;)]', p['text']) and
                    fixed[-1]['type'] == 'text'):
                fixed[-1]['text'] = norm(fixed[-1]['text'] + ' ' + p['text'])
                continue
            fixed.append(p)
        paras = fixed
        dedup = []
        for p in paras:
            if p['type'] == 'text' and dedup and dedup[-1]['type'] == 'text' and dedup[-1]['text'] == p['text']:
                continue
            dedup.append(p)
        if kind == '' and dedup and dedup[0]['type'] == 'text':
            first = dedup[0]['text']
            head = title.split('·')[-1].strip()
            num = title.split('·')[0].strip()
            if first.startswith(head) or (num and first.startswith(num)):
                body = first
                for pre in (num, head):
                    if pre and body.startswith(pre):
                        body = body[len(pre):].strip()
                if body and len(first) - len(body) < 90:
                    dedup[0]['text'] = body
                    dedup.insert(0, {'type': 'h', 'text': (num + '  ' + head).replace('  ', ' ').strip()})
        if kind == 'nofn' and dedup and dedup[0]['type'] == 'text':
            dedup.insert(0, {'type': 'h', 'text': title.split('·')[-1].strip()})
        results.append({'id': sid, 'title': title, 'paras': dedup})
        print(f"{sid:10s} paras={len(dedup):4d} chars={sum(len(p['text']) for p in dedup):7d} | "
              f"{(dedup[0]['text'][:50] if dedup else '')}", flush=True)

    results = finalize_front(results, pages, section_lines, paragraphs_from_stream)
    for sec in results:
        for p in sec['paras']:
            p['text'] = sup_to_tag(p['text'])
    json.dump(results, open(os.path.join(HERE, 'en_data.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('TOTAL sections', len(results), 'paras',
          sum(len(s['paras']) for s in results), flush=True)


if __name__ == '__main__':
    main()
