#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并三个 part 的 content_list.json → stream_raw.json（按全书页码有序）。
过滤 footer/page_number/header/image 噪声；保留 text/ref_text/table。
每个元素: {page, type, text, lvl(可选)}
page 为全书页码(1-based)。
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OFFSET = {'part1': 0, 'part2': 200}   # part page_idx -> 0-based 全书页

def norm(s):
    return ' '.join(s.split())

def main():
    items = []
    for part, off in OFFSET.items():
        files = glob.glob(f'unzip/{part}/*_content_list.json')
        if not files:
            print(f'!! no content_list for {part}')
            continue
        d = json.load(open(files[0], encoding='utf-8'))
        for e in d:
            t = norm(e.get('text',''))
            typ = e.get('type','')
            if typ in ('footer','page_number','header','image'):
                continue
            if not t:
                continue
            page_start = e['page_idx'] + off + 1   # 1-based 全书页
            items.append({
                'page': page_start,
                'type': typ,
                'text': t,
                'lvl': e.get('text_level') if 'text_level' in e else None,
            })
    # 排序（按 sort 保持 content_list 顺序基本即页码序，但稳妥按 page+index）
    # content_list 本身按页顺序排列，跨 part 时需按 part1,part2,part3 顺序
    items.sort(key=lambda x: x['page'])
    with open(os.path.join(HERE,'stream_raw.json'),'w',encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False)
    from collections import Counter
    print('total items:', len(items))
    print('types:', dict(Counter(x['type'] for x in items)))
    lvls = Counter(str(x['lvl']) for x in items if x['lvl'] is not None)
    print('text_levels:', dict(lvls))
    # 显示所有带 lvl 的标题（供章节划分参考）
    print('\n=== 所有标记了 text_level 的标题 ===')
    for x in items:
        if x['lvl'] is not None:
            print(f"  pg{x['page']} lvl{x['lvl']} [{x['type']}]: {x['text'][:55]}")
    totc = sum(len(x['text']) for x in items)
    print('\ntotal chars:', totc)

if __name__=='__main__':
    main()