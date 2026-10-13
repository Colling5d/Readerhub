#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按 new_book.py 的逻辑，为 kodak-china 生成 slots.py 与 build_reader.py。"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOKS = os.path.join(ROOT, 'books')
TEMPLATES = os.path.join(ROOT, 'scripts', 'templates')

CFG = {
    'id': 'kodak-china',
    'title': 'When Kodak Came to China, 1900-1937',
    'author_en': 'Qiuzi Guo',
    'author_cn': '郭秋孜',
    'base_book': 'chinese-americans-shared-history',
    # (sid, 英文短标签, 中文短标签) 用于 TOC；中文先留英文，翻译后人工再定可选
    'labels': {
        'intro':  ['Introduction', '导论'],
        'ch1':    ['Ch.1 The Ubiquitous Gaze', '第一章 无所不在的凝视'],
        'ch2':    ['Ch.2 Revisiting the "Kodak Moment"', '第二章 重访“柯达时刻”'],
        'ch3':    ['Ch.3 Democratization of the Images', '第三章 影像的民主化'],
        'ch4':    ['Ch.4 Portable Landscapes', '第四章 便携的风景'],
        'ch5':    ['Ch.5 Reconfiguring Realism', '第五章 重构现实主义'],
        'concl':  ['Conclusion', '结论'],
        'notes':  ['Notes', '注释'],
        'biblio': ['Bibliography', '参考文献'],
        'figs':   ['List of Figures', '插图目录'],
    },
}
ORDER = ['intro', 'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'concl', 'notes', 'biblio', 'figs']


def read(p):
    return open(p, encoding='utf-8').read()


def inject(text, mapping):
    for k, v in mapping.items():
        text = text.replace(k, str(v))
    return text


def main():
    labels = CFG['labels']
    tocl = {sid: labels[sid] for sid in ORDER}
    titm = {sid: f"{labels[sid][1]} · {labels[sid][0]}" for sid in ORDER}
    sect = {sid: labels[sid][1] for sid in ORDER}

    slots = read(os.path.join(TEMPLATES, 'slots.py'))
    slots = inject(slots, {
        '__TOC_ORDER__': "[" + ", ".join(repr(x) for x in ORDER) + "]",
        '__TOC_LABEL__': json.dumps(tocl, ensure_ascii=False, indent=4),
        '__TITLE_MAP__': json.dumps(titm, ensure_ascii=False, indent=4),
        '__SECTITLE__': json.dumps(sect, ensure_ascii=False, indent=4),
    })
    open(os.path.join(HERE, 'slots.py'), 'w', encoding='utf-8').write(slots)

    BASE_INFO = {'chinese-americans-shared-history': ('Chinese and Americans: A Shared History', 'Xu Guoqi · 徐国琦')}
    bt, ba = BASE_INFO[CFG['base_book']]
    author_attr = f"{CFG['author_en']} · {CFG['author_cn']}"
    br = read(os.path.join(TEMPLATES, 'build_reader.py'))
    br = inject(br, {
        '__BOOK_DIR__': repr(os.path.join(BOOKS, CFG['id'])),
        '__TITLE__': CFG['title'],
        '__BASE_TITLE__': bt,
        '__AUTHOR_ATTR__': author_attr,
        '__BASE_AUTHOR__': re.escape(ba),
        '__POSKEY__': f"readerhub_pos_{CFG['id']}",
        '__BOOKKEY__': f"readerhub_notes_{CFG['id']}",
    })
    open(os.path.join(HERE, 'build_reader.py'), 'w', encoding='utf-8').write(br)
    print('wrote slots.py and build_reader.py')


if __name__ == '__main__':
    main()
