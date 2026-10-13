#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把附录页的表格图片抽出，复制到 books/<id>/tables/，生成 appendix_items.json。
表格在正文流中作为 <img> 嵌入附录章节。"""
import json, glob, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_DIR = '/Users/zhulv/ReaderHub/books/american-dream-unfinished'
TBL_DIR = os.path.join(BOOK_DIR, 'tables')
os.makedirs(TBL_DIR, exist_ok=True)

# 附录页码范围（PDF 1-based page）
APDX_A, APDX_B = 220, 228


def collect():
    items = []
    for part in sorted(os.listdir(os.path.join(HERE, 'unzip'))):
        pdir = os.path.join(HERE, 'unzip', part)
        cl = glob.glob(os.path.join(pdir, '*_content_list.json'))
        if not cl:
            continue
        d = json.load(open(cl[0], encoding='utf-8'))
        # 推断该 part 的页偏移
        off = 0 if part.startswith('part1') else 200
        for e in d:
            pg = e.get('page_idx', 0) + off + 1
            if pg < APDX_A or pg > APDX_B:
                continue
            typ = e.get('type')
            cap = e.get('table_caption') or e.get('image_caption') or []
            if isinstance(cap, list):
                cap = ' '.join(cap)
            img = e.get('img_path') or ''
            if typ in ('table', 'image'):
                items.append({'page': pg, 'type': 'table', 'caption': cap.strip(), 'img': img})
    return items


def main():
    items = collect()
    out = []
    n = 0
    for it in items:
        rec = {'page': it['page'], 'caption': it['caption']}
        if it['img']:
            src = None
            for part in os.listdir(os.path.join(HERE, 'unzip')):
                cand = os.path.join(HERE, 'unzip', part, it['img'])
                if os.path.isfile(cand):
                    src = cand
                    break
            if src:
                n += 1
                name = 'tbl_%02d_%s' % (n, os.path.basename(src))
                shutil.copy(src, os.path.join(TBL_DIR, name))
                rec['img'] = 'tables/' + name
        out.append(rec)
    json.dump(out, open(os.path.join(HERE, 'appendix_items.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('appendix 表格/图片:', len(out), '| 复制图片:', n)
    for r in out[:6]:
        print('  p%d %s | %s' % (r['page'], r.get('img', '(无图)'), r['caption'][:40]))


if __name__ == '__main__':
    main()
