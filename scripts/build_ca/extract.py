#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并两部 OCR JSON → 产出完整有序文本流 (page, type, text)。"""
import json, os, re

SRC = [
    "/Users/zhulv/Documents/共有的历史1.json",
    "/Users/zhulv/Documents/共有的历史2.json",
]

def blocks(fn):
    d = json.load(open(fn, encoding='utf-8'))
    res = []
    for p in d.get('pdf_info', []):
        for b in p.get('para_blocks', []):
            lines = b.get('lines', [])
            if not lines:
                continue
            txt = ''.join(s.get('content', '') for l in lines for s in l.get('spans', []))
            res.append((p.get('page_idx', 0) + 1, b.get('type', 'text'), txt))
    return res

def main():
    stream = []
    for fn in SRC:
        stream += blocks(fn)
    # write raw stream
    import io
    out = []
    for pg, typ, txt in stream:
        out.append({"page": pg, "type": typ, "text": txt})
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "stream_raw.json"), "w", encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print("blocks:", len(out))
    # quick stats
    from collections import Counter
    print("types:", dict(Counter(x['type'] for x in out)))
    tot = sum(len(x['text']) for x in out)
    print("total chars:", tot)

if __name__ == '__main__':
    main()