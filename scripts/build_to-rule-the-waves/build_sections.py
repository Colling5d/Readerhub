#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PDF 文本 + 图片页 OCR -> en_data.json：分节、去页眉页码、合行、抽标题
import json, os, re, sys
from collections import Counter
from extract import OCR, NO_TEXT_PAGES, PDF

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'en_data.json')

# pdf 索引区间（含端点），据 Contents 与实际章首页核对
SECTIONS = [
    ('front',    'Front Matter',                                    (0, 11)),
    ('prologue', 'Prologue · A Box in the Jungle',                  (12, 27)),
    ('ch1',      'Chapter 1 · Secrets of the High North',           (28, 39)),
    ('ch2',      'Chapter 2 · The Outer Perimeter',                 (40, 62)),
    ('ch3',      'Chapter 3 · Charting Today’s World',              (63, 103)),
    ('ch4',      'Chapter 4 · Western Tide Rising',                 (104, 120)),
    ('ch5',      'Chapter 5 · Taipans of Globalization',            (121, 134)),
    ('ch6',      'Chapter 6 · The Great Closing',                   (135, 144)),
    ('ch7',      'Chapter 7 · Global Supply Ships',                 (145, 177)),
    ('ch8',      'Chapter 8 · Pirates of the Twenty-First Century', (178, 189)),
    ('ch9',      'Chapter 9 · The Near Seas',                       (190, 207)),
    ('ch10',     'Chapter 10 · America’s Lake',                     (208, 226)),
    ('ch11',     'Chapter 11 · To Conquer the Seas',                (227, 253)),
    ('ch12',     'Chapter 12 · The Salt of the Oceans',             (254, 275)),
    ('ch13',     'Chapter 13 · Oceanography and Power',             (276, 296)),
    ('ch14',     'Chapter 14 · Hot Waters Rising',                  (297, 312)),
    ('concl',    'Conclusion · Come Hell and High Water',           (314, 323)),
    ('ack',      'Acknowledgments',                                 (324, 328)),
    ('notes',    'Notes',                                           (330, 364)),
    ('biblio',   'Bibliography',                                    (366, 381)),
    ('index',    'Index',                                           (382, 400)),
]


def ocr_lines(i):
    p = os.path.join(OCR, f'p{i:03d}.json')
    if not os.path.exists(p):
        return []
    L = json.load(open(p))
    for r in L:          # OCR 低分辨率页：行高偏窄，放宽高度估计
        r['h'] = max(r['h'], 0.020)
    return L


def pdf_lines_fast(pdf, i):
    pg = pdf[i]
    H, W = pg.rect.height, pg.rect.width
    out = []
    for b in pg.get_text('dict')['blocks']:
        if b.get('type') != 0:
            continue
        for ln in b['lines']:
            txt = ''.join(s['text'] for s in ln['spans'])
            if not txt.strip():
                continue
            x0, y0, x1, y1 = ln['bbox']
            out.append({'x': x0 / W, 'y': 1 - y1 / H, 'w': (x1 - x0) / W,
                        'h': (y1 - y0) / H, 'text': txt})
    out.sort(key=lambda l: (round(l['y'], 3), l['x']))
    return out


def get_lines(pdf, i):
    # 以 Vision OCR 为主（版面/行序可靠）；缺 OCR 时退回 PDF 文字层
    oc = ocr_lines(i)
    if oc:
        return oc
    return pdf_lines_fast(pdf, i)


KEEP_HYPHEN = set("""ship-to-ship just-in-time up-to-date state-of-the-art

anti-access anti-ship anti-piracy anti-submarine anti-terror anti-trust
counter-insurgency counter-terrorism self-defense self-determination well-being
twenty-first twenty-second nineteenth eighteenth mid-twentieth
sea-lanes sea-lane sea-power sea-based sea-level sea-floor sea-water sea-bed
land-based carrier-based state-owned state-run state-led state-building
policy-makers policy-making decision-makers decision-making
long-term long-standing long-range long-distance long-run
cold-war post-war pre-war inter-war post-cold-war
free-trade free-market free-traders
high-tech high-end low-cost low-income high-income high-value high-speed
supply-chain supply-chains value-chain
zero-sum one-way two-way three-part two-part four-part
ship-borne shore-based oil-fired coal-fired nuclear-powered diesel-powered
coast-guard coast-guards maritime-based
""".split())


# OCR 丢了行首字符留下的断字残片：残片 -> 完整词
MISSING_HEAD = {
    'merican': 'American', 'inese': 'Chinese', 'uropean': 'European',
    'urope': 'Europe', 'ndoPacific': 'Indo-Pacific', 'ingapore': 'Singapore',
    'acific': 'Pacific', 'idden': 'hidden', 'ordon': 'Gordon',
    'ashington': 'Washington', 'hiladelphia': 'Philadelphia', 'hilip': 'Philip',
}
# 合并后（无连字符）的修复
REPAIR = {
    'shiptoshore': 'ship-to-shore', 'shiptoship': 'ship-to-ship',
    'justintime': 'just-in-time', 'uptodate': 'up-to-date',
    'astforward': 'fast-forward', 'stateoftheart': 'state-of-the-art',
    'egisclass': 'Aegis-class', 'systemessentially': 'system—essentially',
    'shiptoshore': 'ship-to-shore',
}


GLUED = {
    'yearround': 'year-round', 'oldschool': 'old-school', 'fullblown': 'full-blown',
    'twentyfive': 'twenty-five', 'thirtythree': 'thirty-three', 'onethird': 'one-third',
    'secondlargest': 'second-largest', 'thirdlargest': 'third-largest',
    'everlarger': 'ever-larger', 'ultralarge': 'ultra-large', 'betterknown': 'better-known',
    'farflung': 'far-flung', 'shortrange': 'short-range', 'fortyfoot': 'forty-foot',
    'thirtyfive': 'thirty-five', 'mineralrich': 'mineral-rich', 'flatscreen': 'flat-screen',
    'twentythree': 'twenty-three', 'eightfoot': 'eight-foot', 'redbrick': 'red-brick',
    'citystate': 'city-state', 'counterpiracy': 'counter-piracy',
    'purposedesigned': 'purpose-designed', 'animalsourced': 'animal-sourced',
    'landbased': 'land-based', 'seabased': 'sea-based', 'stateowned': 'state-owned',
    'policywonks': 'policy-wonks', 'toplevel': 'top-level', 'highlevel': 'high-level',
    'lowlevel': 'low-level', 'firstever': 'first-ever', 'longstanding': 'long-standing',
    'sealevel': 'sea-level', 'sealanes': 'sea-lanes', 'seaborn': 'sea-borne',
    'oceangoing': 'ocean-going', 'oceangoing': 'ocean-going',
}


def fix_glued(t):
    for bad, good in GLUED.items():
        t = re.sub(r'\b' + bad + r'\b', good, t)
    return t


def dewraptext(t):
    # 合并行内断字 ex-ample -> example，保留真连字符 anti-access、1970s-1980s
    def rep(m):
        a, b = m.group(1), m.group(2)
        joined = a + b
        if joined in MISSING_HEAD:                  # meri-can -> American
            return MISSING_HEAD[joined]
        if a + '-' + b in KEEP_HYPHEN:
            return a + '-' + b
        if re.fullmatch(r'\d+', a) or re.fullmatch(r'\d+', b):
            return a + '-' + b          # 数字-数字 / 页码
        return a + b
    # 行内空格断字：词- 空格 小写词
    t = re.sub(r'\b([A-Za-z]{2,})-\s+([a-z]{2,})', rep, t)
    # OCR 行拼接遗留：同一段落里 词-小写词（行尾断字被直接粘住）
    t = re.sub(r'\b([A-Za-z]{2,})-([a-z]{2,})\b', lambda m: rep(m), t)
    t = fix_glued(t)
    for bad, good in REPAIR.items():
        t = re.sub(r'\b' + bad + r'\b', good, t, flags=re.I)
    return t


def strip_heads(lines):
    lines = [l for l in lines if l['y'] <= 0.955]
    if len(lines) < 6:
        return lines
    gaps = [(k, lines[k]['y'] - lines[k - 1]['y']) for k in range(1, len(lines))]
    big = [k for k, d in gaps if d > 0.05 and lines[k]['y'] < 0.5]
    if big:                                # 标题区→正文：取最后一处大空隙（跳过副标题块）
        return lines[big[-1]:]
    return [l for l in lines if l['y'] >= 0.31]


def norm(s):
    return ' '.join(s.split())


def is_pagenum(t):
    t = t.strip()
    return re.fullmatch(r'[ivxlcdm]{1,6}|_?\s*\d{1,3}', t, re.I) is not None


def running_heads(pages):
    c = Counter()
    for i, lines in pages.items():
        for l in lines[:2] + lines[-2:]:
            t = norm(l['text'])
            if 0 < len(t) < 60 and not is_pagenum(t):
                c[t.upper()] += 1
    return {t for t, n in c.items() if n >= 8}


def join_lines(lines, running):
    # 把页内行合并成段落。断段：行距明显大于正文行距，或首行缩进
    lines = [l for l in lines
             if norm(l['text']) and not is_pagenum(norm(l['text']))
             and norm(l['text']).upper() not in running]
    if not lines:
        return []
    ys = [l['y'] for l in lines]
    gaps = [round(b - a, 4) for a, b in zip(ys, ys[1:]) if 0 < b - a < 0.06]
    gaps.sort()
    pitch = gaps[len(gaps) // 2] if gaps else 0.023      # 正文行距（中位数）
    left = min(l['x'] for l in lines)
    paras, cur, prev_y = [], None, None
    for l in lines:
        t = norm(l['text'])
        y = l['y']
        new = cur is None
        if cur is not None:
            d = y - prev_y
            if d > pitch * 1.28:                        # 行距加大 → 新段
                new = True
            elif d < 0:                                  # 换栏/异常
                new = True
            elif l['x'] > left + 0.012 and not cur['text'].rstrip().endswith(('-', ',')):
                new = True                               # 缩进 → 新段
        if new:
            if cur:
                paras.append(cur)
            cur = {'text': t, 'y': y, 'lines': 1}
        else:
            sep = '' if cur['text'].endswith('-') and t[:1].islower() else ' '
            cur['text'] += sep + t
            cur['lines'] += 1
        prev_y = y
    if cur:
        paras.append(cur)
    for p in paras:
        p['text'] = dewraptext(p['text'])
        p['text'] = re.sub(r'\s+', ' ', p['text'])
    return paras


SUBH_PAT = re.compile(
    r'^([A-Z0-9 \-\'’.,:&!?—]+|How .+|What .+|Why .+|Where .+|The [A-Z].+|A [A-Z].+|'
    r'In [A-Z].+|China’?s? .+|America’?s? .+|Chinese .+|Blockading .+|Drilling .+)$')


def main():
    import fitz
    pdf = fitz.open(PDF)
    pages = {i: get_lines(pdf, i) for i in range(pdf.page_count)}
    running = running_heads(pages)
    print('running heads:', len(running))

    results = []
    for sid, title, (a, b) in SECTIONS:
        paras = []
        for i in range(a, b + 1):
            lines = pages.get(i, [])
            if lines and i == a and sid not in ('front', 'notes', 'biblio', 'index'):
                # 仅该节首页：标题区（part/章号/章名/副标题）与正文之间有明显疏排空隙，
                # 取第一个“行距 > 正文行距”的空隙之后的行作为正文起点
                lines = strip_heads(lines)
            for p in join_lines(lines, running):
                txt = p['text']
                is_sub = (p['lines'] == 1 and len(txt) < 60 and SUBH_PAT.match(txt)
                          and not re.search(r'[.,;:]', txt)
                          and (txt.isupper() or txt[0].isupper() or txt[0].isdigit()))
                if sid != 'front' and is_sub and p['y'] > 0.15:
                    paras.append({'type': 'subh', 'text': txt.title() if txt.isupper() else txt})
                else:
                    paras.append({'type': 'text', 'text': txt})
        merged = []
        for p in paras:
            if merged and merged[-1]['type'] == p['type'] and p['type'] in ('text', 'subh') \
                    and not re.search(r'[.!?"”’)]$', merged[-1]['text']) \
                    and merged[-1]['text'].upper() != merged[-1]['text']:
                merged[-1]['text'] = merged[-1]['text'].rstrip('-') + ' ' + p['text']
            else:
                merged.append(p)
        merged = [m for m in merged if len(m['text']) > 2]
        merged.insert(0, {'type': 'h', 'text': title})
        results.append({'id': sid, 'title': title, 'paras': merged})
        print(f'{sid:9s} paras={len(merged):4d} words={sum(len(p["text"].split()) for p in merged):6d} | '
              f'{(merged[1]["text"][:70] if len(merged) > 1 else "")}')
    json.dump(results, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
