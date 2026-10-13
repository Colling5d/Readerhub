#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本地 pages.json（ReaderHub-local 抽好的版面块）转成 en_data.json。

约定（与既有书一致）：
- 正文各节只有 h(节标题) + text(段落) + subh(小标题)
- 所有脚注（foot）抽出来，放到末尾独立的 notes 节，按章分组（subh + note）
- 页眉（重复出现的 head）丢弃；page/marginal/toc 丢弃
"""
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    '~/ReaderHub-local/books/kodak-china/build/pages.json')

# sid, 显示标题, (起始 img 页, 结束 img 页, 含)
SECTIONS = [
    ('ack',    'Acknowledgments',              (3, 4)),
    ('intro',  'Introduction',                 (5, 16)),
    ('ch1',    'Chapter 1 · The Ubiquitous Gaze', (17, 45)),
    ('ch2',    'Chapter 2 · Revisiting the "Kodak Moment"', (46, 90)),
    ('ch3',    'Chapter 3 · Democratization of the Images', (91, 114)),
    ('ch4',    'Chapter 4 · Portable Landscapes', (115, 152)),
    ('ch5',    'Chapter 5 · Reconfiguring Realism', (153, 177)),
    ('concl',  'Conclusion',                   (178, 182)),
    ('biblio', 'Bibliography',                 (183, 200)),
    ('figs',   'List of Figures',              (201, 208)),
]

# notes 节里每组的显示名
NOTE_GROUPS = {
    'ack': '\u81f4\u8c22', 'intro': '\u5bfc\u8bba',
    'ch1': 'Chapter 1', 'ch2': 'Chapter 2', 'ch3': 'Chapter 3',
    'ch4': 'Chapter 4', 'ch5': 'Chapter 5', 'concl': '\u7ed3\u8bba',
}

LATIN = re.compile(r'[A-Za-z0-9\)\]\u201d"\'\u2019]$')
LATIN_NEXT = re.compile(r'^[A-Za-z0-9\(\[\u201c"\'\u2018]')


def norm(s):
    return ' '.join(s.split())


def join(prev, nxt):
    if not prev:
        return nxt
    if LATIN.search(prev) and LATIN_NEXT.search(nxt):
        return prev + ' ' + nxt
    return prev + nxt


def find_running_heads(pages):
    c = Counter()
    for p in pages:
        for b in p['blocks']:
            if b['kind'] == 'head':
                c[norm(b['text'])] += 1
    return {t for t, n in c.items() if n >= 5}


def main():
    pages = json.load(open(PAGES, encoding='utf-8'))
    by_img = {p['img']: p for p in pages}
    running = find_running_heads(pages)
    print('running heads (dropped):', list(running), '\n')

    results = []
    note_groups = []   # [(sid, [note_text,...]), ...]

    for sid, title, (a, b) in SECTIONS:
        paras = []
        notes = []
        for img in range(a, b + 1):
            pg = by_img.get(img)
            if not pg:
                continue
            for blk in pg['blocks']:
                k = blk['kind']
                t = norm(blk['text'])
                if not t:
                    continue
                if k in ('body', 'para'):
                    if not paras or paras[-1]['type'] != 'text' or k == 'para':
                        paras.append({'type': 'text', 'text': t})
                    else:
                        paras[-1]['text'] = join(paras[-1]['text'], t)
                elif k == 'subhead':
                    if t not in running:
                        paras.append({'type': 'subh', 'text': t})
                elif k == 'head':
                    if t not in running:
                        paras.append({'type': 'h', 'text': t})
                elif k == 'foot':
                    if notes and re.match(r'^[\d\u3010\u3014\[]', t) is None:
                        notes[-1] = join(notes[-1], t)
                    else:
                        notes.append(t)
        # 首段设为 h（节标题）
        if paras and paras[0]['type'] != 'h':
            paras.insert(0, {'type': 'h', 'text': title})
        elif not paras:
            paras.insert(0, {'type': 'h', 'text': title})
        # 去重相邻重复
        dedup = []
        for p in paras:
            if dedup and dedup[-1]['text'] == p['text'] and dedup[-1]['type'] == p['type']:
                continue
            dedup.append(p)
        results.append({'id': sid, 'title': title, 'paras': dedup})
        if notes:
            note_groups.append((sid, notes))
        print(f"{sid:8s} paras={len(dedup):4d} notes={len(notes):4d} | "
              f"{(dedup[1]['text'][:45] if len(dedup) > 1 else '')}", flush=True)

    # 组装 notes 节
    if note_groups:
        nparas = [{'type': 'subh', 'text': 'Notes'}]
        for sid, notes in note_groups:
            nparas.append({'type': 'subh', 'text': NOTE_GROUPS.get(sid, sid)})
            for nt in notes:
                nparas.append({'type': 'note', 'text': nt})
        results.append({'id': 'notes', 'title': 'Notes', 'paras': nparas})
        print(f"\nnotes section: groups={len(note_groups)} "
              f"notes={sum(len(n) for _, n in note_groups)}")

    out = os.path.join(HERE, 'en_data.json')
    json.dump(results, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"TOTAL sections={len(results)} paras={sum(len(s['paras']) for s in results)}")
    print('wrote', out)


if __name__ == '__main__':
    main()
